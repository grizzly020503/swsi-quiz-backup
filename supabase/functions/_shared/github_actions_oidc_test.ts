import { assertEquals, assertThrows } from "jsr:@std/assert";
import { assertGitHubActionsOidcClaims, type GitHubActionsOidcPolicy } from "./github_actions_oidc.ts";

const HISTORICAL = "grizzly020503/swsi-quiz-backup/.github/workflows/historical-law-runtime-sync.yml@refs/heads/main";
const BOOTSTRAP = "grizzly020503/swsi-quiz-backup/.github/workflows/historical-law-runtime-bootstrap-once.yml@refs/heads/main";
const LEGAL = "grizzly020503/swsi-quiz-backup/.github/workflows/moex-social-worker-sync.yml@refs/heads/main";

const historicalPolicy: GitHubActionsOidcPolicy = {
  allowedWorkflowRefs: new Set([HISTORICAL, BOOTSTRAP]),
  allowedEvents: new Set(["workflow_dispatch", "push"]),
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

Deno.test("historical OIDC claims accept approved workflow on main", () => {
  assertEquals(assertGitHubActionsOidcClaims(payload(), historicalPolicy), undefined);
});

Deno.test("historical OIDC claims accept one-shot bootstrap push", () => {
  assertEquals(
    assertGitHubActionsOidcClaims(payload({ workflow_ref: BOOTSTRAP, event_name: "push" }), historicalPolicy),
    undefined,
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
