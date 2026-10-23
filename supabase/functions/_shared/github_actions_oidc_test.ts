import { assertEquals, assertRejects, assertThrows } from "jsr:@std/assert";
import { exportJWK, generateKeyPair, SignJWT } from "npm:jose@6.1.0";
import { assertGitHubActionsOidcClaims, verifyGitHubActionsOidcToken, type GitHubActionsOidcPolicy } from "./github_actions_oidc.ts";

const HISTORICAL = "grizzly020503/swsi-quiz-backup/.github/workflows/historical-law-runtime-sync.yml@refs/heads/main";
const BOOTSTRAP = "grizzly020503/swsi-quiz-backup/.github/workflows/historical-law-runtime-bootstrap-once.yml@refs/heads/main";
const LEGAL = "grizzly020503/swsi-quiz-backup/.github/workflows/moex-social-worker-sync.yml@refs/heads/main";

const historicalPolicy: GitHubActionsOidcPolicy = {
  allowedWorkflowRefs: new Set([HISTORICAL]),
  allowedEvents: new Set(["workflow_dispatch"]),
};

function payload(overrides: Record<string, unknown> = {}) {
  return {
    repository: "grizzly020503/swsi-quiz-backup",
    repository_id: "1345053575",
    repository_visibility: "public",
    ref: "refs/heads/main",
    ref_type: "branch",
    runner_environment: "github-hosted",
    workflow_ref: HISTORICAL,
    event_name: "workflow_dispatch",
    ...overrides,
  };
}

Deno.test("historical OIDC claims accept only approved manual workflow on main", () => {
  assertEquals(assertGitHubActionsOidcClaims(payload(), historicalPolicy), undefined);
  assertThrows(() =>
    assertGitHubActionsOidcClaims(
      payload({ workflow_ref: BOOTSTRAP, event_name: "push" }),
      historicalPolicy,
    )
  );
});

Deno.test("OIDC claims reject repository, repo id, ref, runner, workflow and event drift", () => {
  for (const changed of [
    { repository: "someone/else" },
    { repository_id: "1" },
    { repository_visibility: "private" },
    { ref: "refs/heads/feature" },
    { ref_type: "tag" },
    { runner_environment: "self-hosted" },
    { workflow_ref: LEGAL },
    { event_name: "push" },
    { event_name: "pull_request" },
  ]) {
    assertThrows(() => assertGitHubActionsOidcClaims(payload(changed), historicalPolicy));
  }
});

Deno.test("legal-watch policy is workflow- and event-specific", () => {
  const policy: GitHubActionsOidcPolicy = {
    allowedWorkflowRefs: new Set([LEGAL]),
    allowedEvents: new Set(["schedule", "workflow_dispatch", "push"]),
  };
  assertEquals(
    assertGitHubActionsOidcClaims(payload({ workflow_ref: LEGAL, event_name: "schedule" }), policy),
    undefined,
  );
  assertThrows(() => assertGitHubActionsOidcClaims(payload({ workflow_ref: HISTORICAL }), policy));
});

const CURRENT_AFFAIRS = "grizzly020503/swsi-quiz-backup/.github/workflows/public-monitoring-feed.yml@refs/heads/main";

// Test the production verifier with ephemeral keys and a mocked JWKS response.
// No network permission, real credentials or injectable production trust anchor.
Deno.test("OIDC signed-token verification fails closed", async (t) => {
  const trusted = await generateKeyPair("RS256");
  const attacker = await generateKeyPair("RS256");
  const jwk = { ...await exportJWK(trusted.publicKey), kid: "synthetic-key", alg: "RS256" };
  const realFetch = globalThis.fetch;
  let jwksRequests = 0;
  globalThis.fetch = (input) => {
    assertEquals(String(input), "https://token.actions.githubusercontent.com/.well-known/jwks");
    jwksRequests++;
    return Promise.resolve(Response.json({ keys: [jwk] }));
  };
  const policy: GitHubActionsOidcPolicy = {
    allowedWorkflowRefs: new Set([CURRENT_AFFAIRS]),
    allowedEvents: new Set(["schedule", "workflow_dispatch", "workflow_run", "push"]),
  };
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    ...payload({ workflow_ref: CURRENT_AFFAIRS, event_name: "schedule" }),
    iss: "https://token.actions.githubusercontent.com",
    aud: "swsi-supabase-sync", iat: now, nbf: now - 5, exp: now + 300,
  };
  async function signed(overrides: Record<string, unknown> = {}, key = trusted.privateKey) {
    return await new SignJWT({ ...claims, ...overrides })
      .setProtectedHeader({ alg: "RS256", kid: jwk.kid }).sign(key);
  }
  const encode = (value: unknown) => btoa(JSON.stringify(value))
    .replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  try {
    await t.step("valid signature and approved claims", async () => {
      assertEquals((await verifyGitHubActionsOidcToken(await signed(), policy)).repository_id, claims.repository_id);
      assertEquals(jwksRequests, 1);
    });
    for (const [label, overrides] of [
      ["issuer", { iss: "https://attacker.invalid" }],
      ["audience", { aud: "another-service" }],
      ["expiry", { exp: now - 60 }],
      ["not yet valid", { nbf: now + 3600 }],
      ["repository", { repository: "attacker/swsi-quiz-backup" }],
      ["repository ID", { repository_id: "1" }],
      ["visibility", { repository_visibility: "private" }],
      ["branch", { ref: "refs/heads/feature" }],
      ["ref type", { ref_type: "tag" }],
      ["workflow", { workflow_ref: HISTORICAL }],
      ["PR event", { event_name: "pull_request" }],
      ["PR target event", { event_name: "pull_request_target" }],
      ["runner", { runner_environment: "self-hosted" }],
    ] as const) {
      await t.step(`reject signed ${label} drift`, async () => {
        const token = await signed(overrides);
        await assertRejects(() => verifyGitHubActionsOidcToken(token, policy));
      });
    }
    await t.step("reject untrusted signing key", async () => {
      const token = await signed({}, attacker.privateKey);
      await assertRejects(() => verifyGitHubActionsOidcToken(token, policy));
    });
    await t.step("reject payload tampering", async () => {
      const parts = (await signed()).split(".");
      parts[1] = encode({ ...claims, repository_id: "1" });
      await assertRejects(() => verifyGitHubActionsOidcToken(parts.join("."), policy));
    });
    await t.step("reject unsigned token", async () => {
      const token = `${encode({ alg: "none" })}.${encode(claims)}.`;
      await assertRejects(() => verifyGitHubActionsOidcToken(token, policy));
    });
    await t.step("reject symmetric algorithm", async () => {
      const token = await new SignJWT(claims).setProtectedHeader({ alg: "HS256" }).sign(new Uint8Array(32));
      await assertRejects(() => verifyGitHubActionsOidcToken(token, policy));
    });
    await t.step("reject empty token", async () => {
      await assertRejects(() => verifyGitHubActionsOidcToken(" ", policy));
    });
  } finally {
    globalThis.fetch = realFetch;
  }
});

Deno.test("current-affairs OIDC policy permits only trusted main workflow and event types", () => {
  const policy: GitHubActionsOidcPolicy = {
    allowedWorkflowRefs: new Set([CURRENT_AFFAIRS]),
    allowedEvents: new Set(["schedule", "workflow_dispatch", "workflow_run", "push"]),
  };
  for (const event_name of ["schedule", "workflow_dispatch", "workflow_run", "push"]) {
    assertEquals(
      assertGitHubActionsOidcClaims(payload({ workflow_ref: CURRENT_AFFAIRS, event_name }), policy),
      undefined,
    );
  }
  for (const drift of [
    { workflow_ref: HISTORICAL, event_name: "schedule" },
    { workflow_ref: LEGAL, event_name: "workflow_run" },
    { workflow_ref: CURRENT_AFFAIRS, event_name: "pull_request" },
    { workflow_ref: CURRENT_AFFAIRS, event_name: "pull_request_target" },
    { workflow_ref: CURRENT_AFFAIRS, ref: "refs/heads/untrusted" },
    { workflow_ref: CURRENT_AFFAIRS, repository_id: "0" },
    { workflow_ref: CURRENT_AFFAIRS, runner_environment: "self-hosted" },
  ]) {
    assertThrows(() => assertGitHubActionsOidcClaims(payload(drift), policy));
  }
});
