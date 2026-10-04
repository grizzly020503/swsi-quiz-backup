#!/usr/bin/env python3
"""Static safety contract for the manual historical-law production sync workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/historical-law-runtime-sync.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")

    require("workflow_dispatch:" in text, "manual workflow_dispatch gate missing")
    require("pull_request:" not in text, "production sync must not run on pull_request")
    require("schedule:" not in text, "production sync must not be scheduled yet")
    require("\n  push:" not in text, "production sync must not run automatically on push yet")
    require("confirm_production_sync:" in text, "explicit production confirmation input missing")
    require("default: false" in text, "production confirmation must default false")
    require("github.ref == 'refs/heads/main'" in text, "production sync must be main-only")
    require("inputs.confirm_production_sync == true" in text, "confirmation boolean gate missing")

    require("contents: read" in text, "manual sync only needs repository read access")
    require("id-token: write" in text, "GitHub OIDC permission missing")
    require("contents: write" not in text, "manual sync must not require repository write permission")
    require("ACTIONS_ID_TOKEN_REQUEST_TOKEN" in text, "OIDC request token wiring missing")
    require("ACTIONS_ID_TOKEN_REQUEST_URL" in text, "OIDC request URL wiring missing")
    require("audience=swsi-supabase-sync" in text, "OIDC audience binding missing")
    require("GH_REPO_TOKEN" not in text, "legacy GitHub repository token auth must be removed")
    require("SUPABASE_SERVICE_ROLE_KEY" not in text, "service-role secret must not enter workflow")
    require("sync-historical-law-evidence" in text, "historical sync endpoint missing")

    for marker in (
        "github_actions_oidc_test.ts",
        "github_actions_oidc.ts",
        "scripts/historical_law_evidence_adjudication.py",
        "scripts/historical_law_runtime_evidence_contract_smoke.py",
        "runtime_evidence_test.ts",
        "normalizeRegistry",
        "materializeRegistry",
        "registry_sha256",
        "record_count",
        "machine_verified_count",
        "evidence_adjudicated_count",
        "sync_status') != 'complete'",
    ):
        require(marker in text, f"historical sync verification marker missing: {marker}")

    print("HISTORICAL LAW MANUAL PRODUCTION SYNC OIDC CONTRACT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
