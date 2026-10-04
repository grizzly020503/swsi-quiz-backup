#!/usr/bin/env python3
"""Static safety contract for the one-shot Stage7 production bootstrap workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/historical-law-runtime-bootstrap-once.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")

    require("\n  push:" in text, "one-shot bootstrap must be push-triggered")
    require("branches:" in text and "- main" in text, "one-shot bootstrap must be main-only")
    require("paths:" in text, "one-shot bootstrap must be path-scoped")
    require("'.github/workflows/historical-law-runtime-bootstrap-once.yml'" in text, "one-shot path gate missing")
    require("pull_request:" not in text, "one-shot bootstrap must not run on pull_request")
    require("schedule:" not in text, "one-shot bootstrap must never be scheduled")
    require("workflow_dispatch:" not in text, "one-shot bootstrap must not add a second manual activation path")
    require("github.repository == 'grizzly020503/swsi-quiz-backup'" in text, "repository identity gate missing")
    require("github.ref == 'refs/heads/main'" in text, "main ref gate missing")

    require("contents: read" in text, "bootstrap only needs repository read access")
    require("id-token: write" in text, "GitHub OIDC permission missing")
    require("contents: write" not in text, "bootstrap must not require repository write permission")
    require("ACTIONS_ID_TOKEN_REQUEST_TOKEN" in text, "OIDC request token wiring missing")
    require("ACTIONS_ID_TOKEN_REQUEST_URL" in text, "OIDC request URL wiring missing")
    require("audience=swsi-supabase-sync" in text, "OIDC audience binding missing")
    require("GH_REPO_TOKEN" not in text, "legacy GitHub repository token auth must be removed")
    require("SUPABASE_SERVICE_ROLE_KEY" not in text, "service-role secret must not enter bootstrap workflow")
    require("sync-historical-law-evidence" in text, "historical sync endpoint missing")

    for marker in (
        "github_actions_oidc_test.ts",
        "github_actions_oidc.ts",
        "historical_law_evidence_adjudication.py",
        "historical_law_runtime_evidence_contract_smoke.py",
        "runtime_evidence_test.ts",
        "normalizeRegistry",
        "materializeRegistry",
        "registry_sha256",
        "record_count",
        "machine_verified_count",
        "evidence_adjudicated_count",
        "sync_status') != 'complete'",
        "HISTORICAL LAW PRODUCTION BOOTSTRAP CONFIRMED",
    ):
        require(marker in text, f"bootstrap verification marker missing: {marker}")

    print("HISTORICAL LAW ONE-SHOT PRODUCTION BOOTSTRAP OIDC CONTRACT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
