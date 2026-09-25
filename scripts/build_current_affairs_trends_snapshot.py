#!/usr/bin/env python3
"""Build event-level exam-trend snapshot for SWSI current-affairs V2."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from current_affairs_event_cluster import parse_dt

LEVEL = {"low": 1, "medium": 2, "high": 3}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def days_between(a: str | None, b: str | None) -> float:
    da, db = parse_dt(a), parse_dt(b)
    if not da or not db:
        return 0.0
    return abs((db - da).total_seconds()) / 86400.0


def trend_for(event: dict, generated_at: str) -> dict:
    source_count = int(event.get("source_count") or 0)
    official_count = int(event.get("official_source_count") or 0)
    observation_count = int(event.get("observation_count") or 1)
    policy = LEVEL.get(str(event.get("policy_signal") or "low"), 1)
    essay = LEVEL.get(str(event.get("essay_value") or "low"), 1)
    mcq = LEVEL.get(str(event.get("mcq_fact_density") or "low"), 1)
    related_q = len(event.get("related_exam_questions") or [])
    laws = len(event.get("related_laws") or [])
    age_days = days_between(event.get("last_seen"), generated_at)
    span_days = days_between(event.get("first_seen"), event.get("last_seen"))

    factors = {
        "cross_source": min(2.0, max(0.0, source_count - 1) * 0.8),
        "official_evidence": min(1.6, official_count * 0.8),
        "policy_change": max(0.0, policy - 1) * 1.25,
        "historical_questions": min(1.6, related_q * 0.35),
        "law_relevance": min(1.2, laws * 0.6),
        "persistence": min(1.4, max(0, observation_count - 1) * 0.45 + min(span_days, 10) * 0.05),
        "essay_value": max(0.0, essay - 1) * 0.55,
        "mcq_density": max(0.0, mcq - 1) * 0.45,
        "recency": 1.2 if age_days <= 3 else (0.7 if age_days <= 7 else 0.2),
    }
    raw = sum(factors.values())
    trend_score = round(clamp(raw / 12.0 * 10.0, 0.0, 10.0), 1)

    if age_days > 10:
        state = "cooling"
    elif observation_count >= 3 or span_days >= 4:
        state = "sustained"
    elif source_count >= 2 and (official_count >= 1 or policy >= 2):
        state = "rising"
    else:
        state = "one-off"

    why = []
    if source_count >= 2:
        why.append(f"{source_count} 個來源交叉確認")
    if official_count:
        why.append(f"{official_count} 個官方來源")
    if policy >= 2:
        why.append("有政策／制度訊號")
    if laws:
        why.append(f"涉及 {laws} 項法規／公約")
    if related_q:
        why.append(f"關聯 {related_q} 題歷屆題")
    if observation_count >= 2:
        why.append(f"已連續觀察 {observation_count} 次")
    if not why:
        why.append("目前證據仍偏單次事件")

    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "title": event.get("title"),
        "category": event.get("category"),
        "subjects": event.get("subjects") or [],
        "trend_state": state,
        "trend_score": trend_score,
        "why": why,
        "factors": {k: round(v, 2) for k, v in factors.items()},
        "source_count": source_count,
        "official_source_count": official_count,
        "observation_count": observation_count,
        "first_seen": event.get("first_seen"),
        "last_seen": event.get("last_seen"),
        "related_laws": event.get("related_laws") or [],
        "historical_question_count": related_q,
        "related_exam_questions": event.get("related_exam_questions") or [],
        "essay_direction": event.get("essay_direction"),
        "mcq_focus": event.get("mcq_focus") or [],
        "evidence": event.get("evidence") or [],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(root / "auto" / "current_affairs_events.json"))
    ap.add_argument("--output", default=str(root / "auto" / "current_affairs_trends.json"))
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    events_path, out_path = Path(args.events), Path(args.output)
    if not events_path.exists():
        raise SystemExit(f"Events snapshot not found: {events_path}")
    src = json.loads(events_path.read_text(encoding="utf-8"))
    if src.get("schema_version") != 1:
        raise SystemExit("Unsupported current_affairs_events schema")

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = [trend_for(x, generated_at) for x in (src.get("events") or []) if isinstance(x, dict)]
    rows.sort(key=lambda x: (-float(x.get("trend_score") or 0), str(x.get("last_seen") or "")))
    rows = rows[: max(1, args.limit)]

    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "event_count": len(rows),
        "method": "deterministic-v1",
        "note": "SWSI 命題趨勢訊號；用於安排複習優先順序，不代表命題保證。",
        "trends": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Current-affairs V2 trends: events={len(rows)} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
