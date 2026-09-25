#!/usr/bin/env python3
"""Build SWSI current-affairs V2 event clusters.

Inputs:
- auto/current_affairs.json (source items)
- auto/current_affairs_signals.json (exam-signal enrichment)

Output:
- auto/current_affairs_events.json

The builder preserves V1 contracts and only adds a new event-level snapshot.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from current_affairs_event_cluster import cluster_items


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_source_and_signals(news: dict, signals: dict) -> list[dict]:
    signal_map = {
        str(row.get("id")): row
        for row in (signals.get("items") or [])
        if isinstance(row, dict) and row.get("id")
    }
    merged = []
    for row in news.get("items") or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out = dict(row)
        sig = signal_map.get(str(row.get("id"))) or {}
        for key in (
            "policy_signal", "essay_value", "mcq_fact_density",
            "signal_confidence", "signal_score", "exam_point_summary",
            "essay_direction", "mcq_focus", "related_laws",
            "related_exam_questions",
        ):
            if key in sig:
                out[key] = sig[key]
        merged.append(out)
    return merged


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", default=str(root / "auto" / "current_affairs.json"))
    ap.add_argument("--signals", default=str(root / "auto" / "current_affairs_signals.json"))
    ap.add_argument("--output", default=str(root / "auto" / "current_affairs_events.json"))
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    news_path, sig_path, out_path = Path(args.news), Path(args.signals), Path(args.output)
    if not news_path.exists() or not sig_path.exists():
        raise SystemExit("V2 event builder requires current_affairs.json and current_affairs_signals.json")

    previous_events = []
    if out_path.exists():
        try:
            old = load_json(out_path)
            if old.get("schema_version") == 1:
                previous_events = old.get("events") or []
        except Exception:
            previous_events = []

    news, signals = load_json(news_path), load_json(sig_path)
    items = merge_source_and_signals(news, signals)
    events = cluster_items(items, previous_events=previous_events)
    public_events = events[: max(1, args.limit)]

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_item_count": len(items),
        "event_count": len(public_events),
        "note": "SWSI 時事事件聚類；同事件多來源只算一個事件。命題訊號不代表命題保證。",
        "events": public_events,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Current-affairs V2 events: source_items={len(items)}, "
        f"events={len(public_events)} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
