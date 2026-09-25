#!/usr/bin/env python3
"""Fail-closed ownership contract for the MOEX sync workflow.

MOEX owns official exam payloads, question backup payloads, health/sync state,
and internal MOJ legal-watch state. Public current-affairs snapshots are owned
by Public Monitoring Feed and must never be staged by the MOEX bot.
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

    assert "python scripts/current_affairs_watch.py --output /tmp/current_affairs_payload.json" in text
    assert "--data-binary @/tmp/current_affairs_payload.json" in text
    assert "Sync current-affairs candidates to Supabase" in text

    print(
        "MOEX WORKFLOW OWNERSHIP OK: official payload/state only; "
        "public current-affairs snapshots owned by Public Monitoring Feed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
