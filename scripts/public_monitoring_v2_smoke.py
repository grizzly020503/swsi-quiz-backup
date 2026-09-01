#!/usr/bin/env python3
"""Cheap fail-closed contract checks for SWSI Monitoring V2.

No network, model call, database write, or secrets are required.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    news = read_json("auto/current_affairs.json")
    laws = read_json("auto/legal_watch.json")
    health = read_json("auto/health.json")
    sync = read_json("auto/sync_state.json")

    assert news.get("schema_version") == 2
    items = news.get("items") or []
    assert items, "current-affairs snapshot is empty"
    for row in items:
        assert str(row.get("title") or "").strip()
        assert str(row.get("source_url") or "").startswith("https://")
        assert row.get("category")

    assert laws.get("schema_version") == 1
    assert int(laws.get("watch_count") or 0) >= 20
    assert int(laws.get("matched_count") or 0) >= 20
    assert int(laws.get("changed_count") or 0) == len(laws.get("changes") or [])
    for row in (laws.get("changes") or []) + (laws.get("recently_modified") or []):
        url = str(row.get("official_url") or "")
        assert url.startswith("https://law.moj.gov.tw/"), url
        forbidden = {"question_count", "lookup_errors", "error", "client_id", "contact"}
        assert not forbidden.intersection(row), row

    assert health.get("status") == "ok"
    assert int(health.get("expected_total_questions") or 0) == 4800
    assert isinstance(sync.get("included_exams"), list)

    owner = (ROOT / "monthly_patch_parts/89.public-branding-info.part").read_text(encoding="utf-8")
    assert "Monitoring Center V2" in owner
    assert "2026-09-01.monitoring-v2" in owner
    for key in ("news", "law", "questions", "system", "feedback"):
        assert f'data-monitor-key="{key}"' in owner, key
    assert "/auto/current_affairs.json" in owner
    assert "/auto/legal_watch.json" in owner
    assert "/auto/health.json" in owner
    assert "/auto/sync_state.json" in owner
    assert "不自動改答案" in owner

    for rel in ("current_affairs.json", "legal_watch.json", "health.json", "sync_state.json"):
        public = ROOT / "cdn/auto" / rel
        if public.exists():
            assert json.loads(public.read_text(encoding="utf-8")) == read_json("auto/" + rel), rel

    print(
        "PUBLIC MONITORING V2 CONTRACT OK: "
        f"news={len(items)}, laws={laws['matched_count']}/{laws['watch_count']}, questions=4800, five-radar-ui=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
