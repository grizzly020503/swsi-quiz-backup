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

    require("contents: write" in text, "ephemeral GitHub token requires repo write capability")
    require("GH_REPO_TOKEN: ${{ github.token }}" in text, "bootstrap must use ephemeral github.token")
    require("SUPABASE_SERVICE_ROLE_KEY" not in text, "service-role secret must not enter bootstrap workflow")
    require("sync-historical-law-evidence" in text, "historical sync endpoint missing")

    for marker in (
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

    print("HISTORICAL LAW ONE-SHOT PRODUCTION BOOTSTRAP CONTRACT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
