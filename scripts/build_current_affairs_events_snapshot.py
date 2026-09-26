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
            "related_exam_questions", "historical_exam_stats",
        ):
            if key in sig:
                out[key] = sig[key]
        merged.append(out)
    return merged


def _ordered_union(rows, key, limit=30):
    seen = set()
    out = []
    for row in rows:
        for raw in (row.get(key) or []):
            value = str(raw or "").strip()
            if value and value not in seen:
                seen.add(value)
                out.append(value)
                if len(out) >= limit:
                    return out
    return out


def _item_source_urls(row: dict) -> set[str]:
    urls = set()
    direct = str(row.get("source_url") or "").strip()
    if direct:
        urls.add(direct)
    for source in (row.get("sources") or []):
        if not isinstance(source, dict):
            continue
        url = str(source.get("source_url") or "").strip()
        if url:
            urls.add(url)
    return urls


def attach_event_knowledge(events: list[dict], items: list[dict]) -> list[dict]:
    """Carry the management-first knowledge tree from source items to events."""
    item_urls = [(row, _item_source_urls(row)) for row in items]
    out = []
    for event in events:
        enriched = dict(event)
        evidence_urls = {
            str(e.get("source_url") or "").strip()
            for e in (event.get("evidence") or [])
            if isinstance(e, dict) and str(e.get("source_url") or "").strip()
        }
        members = [row for row, urls in item_urls if evidence_urls.intersection(urls)]
        if members:
            roots = [str(row.get("knowledge_root") or "").strip() for row in members]
            models = [str(row.get("knowledge_model") or "").strip() for row in members]
            subject_topics = {}
            for row in members:
                raw = row.get("subject_topics") or {}
                if not isinstance(raw, dict):
                    continue
                for subject, topics in raw.items():
                    bucket = subject_topics.setdefault(str(subject), [])
                    for topic in (topics or []):
                        value = str(topic or "").strip()
                        if value and value not in bucket:
                            bucket.append(value)
            enriched.update({
                "knowledge_root": next((x for x in roots if x), ""),
                "knowledge_model": next((x for x in models if x), ""),
                "management_domains": _ordered_union(members, "management_domains", 8),
                "exam_subject_axes": _ordered_union(members, "exam_subject_axes", 5),
                "subject_topics": {k: v[:6] for k, v in subject_topics.items()},
                "knowledge_topics": _ordered_union(members, "knowledge_topics", 20),
                "knowledge_paths": _ordered_union(members, "knowledge_paths", 30),
            })
        out.append(enriched)
    return out


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
    events = attach_event_knowledge(
        cluster_items(items, previous_events=previous_events),
        items,
    )
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
