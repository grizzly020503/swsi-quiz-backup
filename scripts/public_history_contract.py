#!/usr/bin/env python3
"""Read-only deployed history contract; no network, model calls, or writes."""
from __future__ import annotations

import math


def require(condition, message):
    if not condition:
        raise AssertionError("Current-affairs history: " + message)


def count(value, label):
    require(type(value) is int and 0 <= value <= 4800, label + " invalid count")
    return value


def validate_counts(raw, weighted, breakdown, label):
    raw = count(raw, label)
    require(type(weighted) in (int, float) and math.isfinite(weighted), label + " invalid weight")
    require(0 <= weighted <= raw, label + " weight exceeds raw count")
    require(isinstance(breakdown, dict) and set(breakdown) == {"strong", "medium", "concept"}, label + " missing quality breakdown")
    require(sum(count(v, label) for v in breakdown.values()) == raw, label + " quality sum mismatch")


def validate_stats(stats, label):
    require(isinstance(stats, dict), label + " missing statistics")
    require(stats.get("matching_method") == "event-evidence-v2.2", label + " old matching method")
    validate_counts(stats.get("matched_question_count"), stats.get("weighted_match_count"), stats.get("match_breakdown"), label)
    # Same-law history is intentionally separate and may exceed same-topic count.
    count(stats.get("law_match_count"), label + " law history")
    for prefix in ("matched", "law_match"):
        years = stats.get(prefix + "_years")
        require(isinstance(years, list) and all(type(y) is int and 1 <= y <= 999 for y in years), label + " invalid years")
        require(years == sorted(set(years)), label + " years not unique/sorted")
        require(stats.get(prefix + "_year_count") == len(years), label + " year count mismatch")
    years = stats["matched_years"]
    latest = stats.get("latest_exam_year")
    gap = stats.get("years_since_last_exam")
    require(latest == (max(years) if years else None), label + " latest exam mismatch")
    corpus = stats.get("corpus_latest_year")
    require(type(corpus) is int and 1 <= corpus <= 999, label + " missing corpus year")
    require(gap == (corpus - latest if latest is not None else None), label + " exam gap mismatch")
    require(gap is None or gap >= 0, label + " negative exam gap")


def validate_history_contract(signals, events, trends):
    require(trends.get("method") == "deterministic-v2.2", "old trend method")
    require(signals.get("questions_loaded") == 4800, "incomplete question corpus")
    for item in signals.get("items", []):
        validate_stats(item.get("historical_exam_stats"), "signal " + str(item.get("id")))
    event_rows = events.get("events", [])
    trend_rows = trends.get("trends", [])
    require(signals.get("items") and event_rows and trend_rows, "empty snapshots")
    by_id = {row.get("canonical_event_id"): row for row in event_rows}
    require(len(by_id) == len(event_rows), "duplicate event ID")
    seen = set()
    for event in event_rows:
        validate_stats(event.get("historical_exam_stats"), "event " + str(event.get("canonical_event_id")))
    for trend in trend_rows:
        event_id = trend.get("canonical_event_id")
        require(event_id in by_id and event_id not in seen, "orphan/duplicate trend")
        seen.add(event_id)
        stats = by_id[event_id]["historical_exam_stats"]
        validate_counts(trend.get("historical_question_count"), trend.get("historical_weighted_match_count"), trend.get("historical_match_breakdown"), "trend " + str(event_id))
        for public_key, stats_key in (
            ("historical_question_count", "matched_question_count"),
            ("historical_weighted_match_count", "weighted_match_count"),
            ("historical_match_breakdown", "match_breakdown"),
            ("historical_exam_years", "matched_years"),
            ("historical_law_match_count", "law_match_count"),
            ("historical_law_match_years", "law_match_years"),
            ("latest_related_exam_year", "latest_exam_year"),
            ("corpus_latest_exam_year", "corpus_latest_year"),
            ("years_since_last_related_exam", "years_since_last_exam"),
        ):
            require(trend.get(public_key) == stats.get(stats_key), public_key + " differs from event")
        factors = trend.get("factors") or {}
        for key in ("historical_frequency", "historical_year_breadth", "recent_exam_support", "historical_subject_breadth"):
            value = factors.get(key)
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "invalid factor " + key)
    require(seen == set(by_id), "event missing trend")
    return "trend-history-v2.2"
