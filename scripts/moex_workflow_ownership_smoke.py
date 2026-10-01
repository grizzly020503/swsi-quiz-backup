#!/usr/bin/env python3
"""Fail-closed ownership contract for the MOEX sync workflow.

MOEX owns official exam payloads, question backup payloads, health/sync state,
and internal MOJ legal-watch state. Current-affairs scan/sync/public snapshots
are owned by Public Monitoring Feed and must never be duplicated here.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "moex-social-worker-sync.yml"

REQUIRED_OWNED = {
    "incoming/",
    "auto/questions_auto.json",
    "auto/essays_auto.json",
    "auto/sync_state.json",
    "auto/health.json",
}
FORBIDDEN_PUBLIC = {
    "auto/current_affairs.json",
    "auto/current_affairs_signals.json",
    "auto/current_affairs_events.json",
    "auto/current_affairs_trends.json",
    "auto/legal_watch.json",
    "cdn/auto/current_affairs.json",
    "cdn/auto/current_affairs_signals.json",
    "cdn/auto/current_affairs_events.json",
    "cdn/auto/current_affairs_trends.json",
}


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "git add incoming/ auto/" not in text, "MOEX must not stage the whole auto/ directory"
    assert "--output auto/current_affairs.json" not in text, (
        "MOEX must not generate the public current-affairs snapshot"
    )

    marker = "      - name: Commit verified official payloads and owned state\n"
    assert marker in text, "MOEX owned-state commit step missing"
    block = text.split(marker, 1)[1].split("\n      - name:", 1)[0]

    for rel in REQUIRED_OWNED:
        assert rel in block, f"MOEX owned path missing from commit step: {rel}"
    for rel in FORBIDDEN_PUBLIC:
        assert rel not in block, f"MOEX must not stage public monitoring path: {rel}"

    for rel in (
        "data/legal_watch_state.json",
        "data/legal_watch_report.json",
        "data/legal_watch_attempt.json",
    ):
        assert rel in block, f"MOEX legal-watch state path missing: {rel}"

    for forbidden in (
        "scripts/current_affairs_watch.py",
        "Scan social-work current affairs",
        "Sync current-affairs candidates to Supabase",
        "--data-binary @/tmp/current_affairs_payload.json",
        "sync-current-affairs",
    ):
        assert forbidden not in text, f"MOEX must not own current-affairs runtime work: {forbidden}"

    print(
        "MOEX WORKFLOW OWNERSHIP OK: exam/law payload-state only; "
        "all current-affairs runtime work owned by Public Monitoring Feed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
