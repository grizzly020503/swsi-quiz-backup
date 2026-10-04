import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "npm:jose@6.1.0";

export const GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com";
export const SWSI_SYNC_AUDIENCE = "swsi-supabase-sync";
export const SWSI_REPOSITORY = "grizzly020503/swsi-quiz-backup";
export const SWSI_REPOSITORY_ID = "1345053575";
export const SWSI_MAIN_REF = "refs/heads/main";

const GITHUB_ACTIONS_JWKS = createRemoteJWKSet(
  new URL("https://token.actions.githubusercontent.com/.well-known/jwks"),
);

export type GitHubActionsOidcPolicy = {
  allowedWorkflowRefs: ReadonlySet<string>;
  allowedEvents: ReadonlySet<string>;
};

function claim(payload: JWTPayload, key: string): string {
  return String((payload as Record<string, unknown>)[key] ?? "");
}

export function assertGitHubActionsOidcClaims(
  payload: JWTPayload,
  policy: GitHubActionsOidcPolicy,
): void {
  if (claim(payload, "repository") !== SWSI_REPOSITORY) {
    throw new Error("OIDC repository mismatch");
  }
  if (claim(payload, "repository_id") !== SWSI_REPOSITORY_ID) {
    throw new Error("OIDC repository_id mismatch");
  }
  if (claim(payload, "repository_visibility") !== "public") {
    throw new Error("OIDC repository visibility mismatch");
  }
  if (claim(payload, "ref") !== SWSI_MAIN_REF || claim(payload, "ref_type") !== "branch") {
    throw new Error("OIDC ref must be main branch");
  }
  if (claim(payload, "runner_environment") !== "github-hosted") {
    throw new Error("OIDC runner must be github-hosted");
  }

  const workflowRef = claim(payload, "workflow_ref");
  if (!policy.allowedWorkflowRefs.has(workflowRef)) {
    throw new Error(`OIDC workflow_ref rejected: ${workflowRef || "missing"}`);
  }

  const eventName = claim(payload, "event_name");
  if (!policy.allowedEvents.has(eventName)) {
    throw new Error(`OIDC event rejected: ${eventName || "missing"}`);
  }
}

export async function verifyGitHubActionsOidcToken(
  token: string,
  policy: GitHubActionsOidcPolicy,
): Promise<JWTPayload> {
  if (!token.trim()) throw new Error("missing GitHub Actions OIDC token");

  const { payload } = await jwtVerify(token, GITHUB_ACTIONS_JWKS, {
    issuer: GITHUB_ACTIONS_OIDC_ISSUER,
    audience: SWSI_SYNC_AUDIENCE,
    algorithms: ["RS256"],
  });
  assertGitHubActionsOidcClaims(payload, policy);
  return payload;
}
