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


def _historical_factor(value: int) -> float:
    if value <= 0:
        return 0.0
    if value <= 2:
        return 0.35
    if value <= 5:
        return 0.70
    if value <= 10:
        return 1.00
    return 1.30


def _exam_recency_support(years_since_last) -> float:
    if years_since_last is None:
        return 0.0
    try:
        gap = int(years_since_last)
    except (TypeError, ValueError):
        return 0.0
    if gap <= 1:
        return 0.80
    if gap <= 3:
        return 0.60
    if gap <= 5:
        return 0.35
    return 0.15


def trend_for(event: dict, generated_at: str) -> dict:
    source_count = int(event.get("source_count") or 0)
    official_count = int(event.get("official_source_count") or 0)
    observation_count = int(event.get("observation_count") or 1)
    policy = LEVEL.get(str(event.get("policy_signal") or "low"), 1)
    essay = LEVEL.get(str(event.get("essay_value") or "low"), 1)
    mcq = LEVEL.get(str(event.get("mcq_fact_density") or "low"), 1)
    laws = len(event.get("related_laws") or [])
    age_days = days_between(event.get("last_seen"), generated_at)
    span_days = days_between(event.get("first_seen"), event.get("last_seen"))

    history = event.get("historical_exam_stats") or {}
    fallback_related = event.get("related_exam_questions") or []
    hist_count = int(history.get("matched_question_count") or len(fallback_related))
    matched_years = [
        int(y) for y in (history.get("matched_years") or [])
        if str(y).isdigit()
    ]
    matched_year_count = int(history.get("matched_year_count") or len(set(matched_years)))
    latest_exam_year = history.get("latest_exam_year")
    corpus_latest_year = history.get("corpus_latest_year")
    years_since_last_exam = history.get("years_since_last_exam")
    subject_counts = history.get("subject_counts") or {}
    subject_count = int(history.get("subject_count") or len(subject_counts))
    historical_law_matches = int(history.get("law_match_count") or 0)
    high_confidence_matches = int(history.get("high_confidence_match_count") or 0)

    factors = {
        "cross_source": min(1.2, max(0.0, source_count - 1) * 0.55),
        "official_evidence": min(1.4, official_count * 0.7),
        "policy_change": max(0.0, policy - 1) * 0.9,
        "historical_frequency": _historical_factor(hist_count),
        "historical_year_breadth": min(0.8, matched_year_count * 0.12),
        "recent_exam_support": _exam_recency_support(years_since_last_exam),
        "historical_subject_breadth": (
            0.45 if subject_count >= 3 else (0.25 if subject_count >= 2 else 0.0)
        ),
        "law_relevance": min(1.1, laws * 0.45 + min(historical_law_matches, 3) * 0.2),
        "persistence": min(
            1.4,
            max(0, observation_count - 1) * 0.45 + min(span_days, 10) * 0.05,
        ),
        "essay_value": max(0.0, essay - 1) * 0.55,
        "mcq_density": max(0.0, mcq - 1) * 0.45,
        "recency": 1.0 if age_days <= 3 else (0.6 if age_days <= 7 else 0.2),
    }
    max_raw = 13.25
    raw = sum(factors.values())
    trend_score = round(clamp(raw / max_raw * 10.0, 0.0, 10.0), 1)

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
    if hist_count:
        year_text = f"，跨 {matched_year_count} 個年度" if matched_year_count else ""
        why.append(f"歷屆完整匹配 {hist_count} 題{year_text}")
    if latest_exam_year is not None:
        if years_since_last_exam is None:
            why.append(f"最近相關題為 {latest_exam_year} 年")
        else:
            why.append(
                f"最近相關題為 {latest_exam_year} 年"
                f"（距題庫最新年度 {int(years_since_last_exam)} 年）"
            )
    if subject_count >= 2:
        why.append(f"歷屆分布 {subject_count} 個考科")
    if historical_law_matches:
        why.append(f"{historical_law_matches} 題有法規直接命中")
    if observation_count >= 2:
        why.append(f"已跨 {observation_count} 個證據日期持續觀察")
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
        "historical_question_count": hist_count,
        "historical_exam_years": sorted(set(matched_years)),
        "latest_related_exam_year": latest_exam_year,
        "corpus_latest_exam_year": corpus_latest_year,
        "years_since_last_related_exam": years_since_last_exam,
        "historical_subject_counts": subject_counts,
        "historical_subject_count": subject_count,
        "historical_law_match_count": historical_law_matches,
        "historical_high_confidence_match_count": high_confidence_matches,
        "historical_stats_method": history.get("aggregation_method") or "item-full-match-v1",
        "related_exam_questions": fallback_related,
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
        "method": "deterministic-v2.1",
        "note": "SWSI 命題趨勢訊號；用於安排複習優先順序，不代表命題保證。",
        "trends": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Current-affairs V2 trends: events={len(rows)} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
