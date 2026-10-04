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

    # Release gate: this workflow must never become an automatic production
    # writer merely because a PR is opened or main receives a push.
    require("workflow_dispatch:" in text, "manual workflow_dispatch gate missing")
    require("pull_request:" not in text, "production sync must not run on pull_request")
    require("schedule:" not in text, "production sync must not be scheduled yet")
    require("\n  push:" not in text, "production sync must not run automatically on push yet")
    require("confirm_production_sync:" in text, "explicit production confirmation input missing")
    require("default: false" in text, "production confirmation must default false")
    require("github.ref == 'refs/heads/main'" in text, "production sync must be main-only")
    require("inputs.confirm_production_sync == true" in text, "confirmation boolean gate missing")

    # The custom Edge Function auth checks GitHub repo write capability, so the
    # workflow token must explicitly carry contents:write. No service-role secret
    # may be copied into GitHub Actions.
    require("contents: write" in text, "GitHub token write capability missing")
    require("GH_REPO_TOKEN: ${{ github.token }}" in text, "sync must use ephemeral github.token")
    require("SUPABASE_SERVICE_ROLE_KEY" not in text, "service-role secret must not enter workflow")
    require("sync-historical-law-evidence" in text, "historical sync endpoint missing")

    # Source-of-truth must be regenerated from the durable Stage7 evidence chain,
    # then fingerprinted by the same runtime module used by the Edge Function.
    for marker in (
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

    print("HISTORICAL LAW MANUAL PRODUCTION SYNC WORKFLOW CONTRACT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
