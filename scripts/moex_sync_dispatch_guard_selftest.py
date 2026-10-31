#!/usr/bin/env python3
"""Fail-closed contract for write-capable MOEX Actions triggers, without API calls."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PRIVILEGED = ROOT / ".github/workflows/moex-social-worker-sync.yml"
READONLY = ROOT / ".github/workflows/full-corpus-qa.yml"


def get_event_section(document: str) -> str:
    found = re.search(r"(?ms)^on:\s*\n(.*?)(?=^[a-zA-Z][\w-]*:\s*$)", document)
    if not found:
        raise AssertionError("workflow has no unambiguous events block")
    return found.group(1)


def test_contract():
    live = PRIVILEGED.read_text(encoding="utf-8")
    checks = READONLY.read_text(encoding="utf-8")
    events = get_event_section(live)
    triggers = re.findall(r"^  ([a-z_]+):(?:\s|$)", events, flags=re.MULTILINE)
    assert sorted(triggers) == ["schedule", "workflow_dispatch"], triggers
    assert "35 2 * * 1" in events, "weekly free official monitor must remain"
    assert "  push:" not in events and "  pull_request:" not in events
    assert "github.ref == 'refs/heads/main'" in live
    assert "github.event_name == 'schedule'" in live
    assert "github.event_name == 'workflow_dispatch'" in live
    assert "contents: write" in live and "id-token: write" in live
    assert "Import only changed verified exams to Supabase with GitHub OIDC" in live
    assert "Sync essay teaching enrichment to Supabase with GitHub OIDC" in live
    assert "git push origin HEAD:main" in live
    assert "  push:" in get_event_section(checks)
    assert "  pull_request:" in get_event_section(checks)
    for path in (
        "scripts/moex_sync.py",
        ".github/workflows/moex-social-worker-sync.yml",
        "scripts/moex_sync_dispatch_guard_selftest.py",
    ):
        assert checks.count("      - '" + path + "'") == 2, (
            path, "read-only CI must run on PR and main push"
        )
    assert "python scripts/moex_sync_dispatch_guard_selftest.py" in checks
    # GitHub's event filter is NOT the authorization boundary by itself.
    # The three deployed Edge Function source policies must agree and fail
    # closed on the old push token even if a workflow is later misconfigured.
    only_events = 'allowedEvents: new Set(["schedule", "workflow_dispatch"])'
    forbidden = 'allowedEvents: new Set(["schedule", "workflow_dispatch", "push"])'
    for relative in (
        "supabase/functions/import-moex-social-worker/index.ts",
        "supabase/functions/sync-essay-enrichment/index.ts",
        "supabase/functions/sync-legal-watch/index.ts",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert source.count(only_events) == 1, (relative, "MOEX OIDC event restriction missing")
        assert forbidden not in source, (relative, "push OIDC still authorized")
        assert "moex-social-worker-sync.yml@refs/heads/main" in source
        assert "verifyGitHubActionsOidcToken" in source
    oidc_test = (ROOT / "supabase/functions/_shared/github_actions_oidc_test.ts").read_text(
        encoding="utf-8"
    )
    assert "MOEX legal-watch policy allows main schedule/manual but rejects push" in oidc_test
    print("MOEX WRITE-CAPABLE SYNC TRIGGER GUARD OK: no push/import, main-only scheduled/manual; PR QA retained")


if __name__ == "__main__":
    test_contract()
