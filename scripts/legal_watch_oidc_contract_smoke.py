#!/usr/bin/env python3
"""Zero-network contract for legal-watch GitHub Actions OIDC authentication."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/moex-social-worker-sync.yml"
INDEX = ROOT / "supabase/functions/sync-legal-watch/index.ts"
OIDC = ROOT / "supabase/functions/_shared/github_actions_oidc.ts"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    oidc = OIDC.read_text(encoding="utf-8")

    for marker in (
        "contents: write",
        "id-token: write",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "audience=swsi-supabase-sync",
        "Send legal watch snapshot to Supabase with GitHub OIDC",
    ):
        require(marker in workflow, f"MOEX workflow OIDC marker missing: {marker}")
    require("GH_REPO_TOKEN: ${{ github.token }}\n          LEGAL_WATCH_URL" not in workflow,
            "legal-watch step must not use legacy github.token auth")
    require("SUPABASE_SERVICE_ROLE_KEY" not in workflow, "service-role secret must not enter workflow")

    for marker in (
        "verifyGitHubActionsOidcToken",
        "LEGAL_WATCH_SYNC_POLICY",
        "moex-social-worker-sync.yml@refs/heads/main",
        'new Set(["schedule", "workflow_dispatch", "push"])',
        "GitHub Actions OIDC authorization rejected",
    ):
        require(marker in index, f"legal-watch function OIDC marker missing: {marker}")
    for forbidden in (
        "verifyGitHubRepoWriteToken",
        "permissions?.push",
        "api.github.com/repos/${REPO}",
    ):
        require(forbidden not in index, f"legacy legal-watch auth remains: {forbidden}")

    for marker in (
        'GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com"',
        'SWSI_SYNC_AUDIENCE = "swsi-supabase-sync"',
        'SWSI_REPOSITORY_ID = "1345053575"',
        'algorithms: ["RS256"]',
        'claim(payload, "workflow_ref")',
        'claim(payload, "event_name")',
    ):
        require(marker in oidc, f"shared OIDC verifier marker missing: {marker}")

    print("LEGAL WATCH GITHUB ACTIONS OIDC CONTRACT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
