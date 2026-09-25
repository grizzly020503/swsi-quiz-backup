#!/usr/bin/env python3
"""Mutation regressions for deployed history checks; no public network calls."""
from copy import deepcopy

from public_history_contract import validate_history_contract


def fixture(raw=1):
    years = [115] if raw else []
    stats = {
        "matching_method": "event-evidence-v2.2", "matched_question_count": raw,
        "weighted_match_count": raw * 0.5,
        "match_breakdown": {"strong": 0, "medium": raw, "concept": 0},
        "matched_years": years, "matched_year_count": len(years),
        "latest_exam_year": 115 if raw else None, "corpus_latest_year": 115,
        "years_since_last_exam": 0 if raw else None,
        "law_match_count": 10, "law_match_years": [114, 115], "law_match_year_count": 2,
    }
    trend = {
        "canonical_event_id": "event-1", "historical_question_count": raw,
        "historical_weighted_match_count": raw * 0.5,
        "historical_match_breakdown": deepcopy(stats["match_breakdown"]),
        "historical_exam_years": years, "historical_law_match_count": 10,
        "historical_law_match_years": [114, 115],
        "latest_related_exam_year": stats["latest_exam_year"],
        "corpus_latest_exam_year": 115, "years_since_last_related_exam": stats["years_since_last_exam"],
        "factors": dict.fromkeys(("historical_frequency", "historical_year_breadth", "recent_exam_support", "historical_subject_breadth"), 0.0),
    }
    return (
        {"questions_loaded": 4800, "items": [{"id": "signal-1", "historical_exam_stats": deepcopy(stats)}]},
        {"events": [{"canonical_event_id": "event-1", "historical_exam_stats": stats}]},
        {"method": "deterministic-v2.2", "trends": [trend]},
    )


def main():
    for raw in (0, 1):
        assert validate_history_contract(*fixture(raw)) == "trend-history-v2.2"
    mutations = [
        lambda s,e,t: t.update(method="deterministic-v2.1"),
        lambda s,e,t: s.update(questions_loaded=200),
        lambda s,e,t: s["items"][0].pop("historical_exam_stats"),
        lambda s,e,t: e["events"][0]["historical_exam_stats"].update(matching_method="related-question-fallback"),
        lambda s,e,t: e["events"][0]["historical_exam_stats"].update(weighted_match_count=float("nan")),
        lambda s,e,t: e["events"][0]["historical_exam_stats"].update(weighted_match_count=2),
        lambda s,e,t: e["events"][0]["historical_exam_stats"]["match_breakdown"].update(strong=1),
        lambda s,e,t: e["events"][0]["historical_exam_stats"].update(years_since_last_exam=3),
        lambda s,e,t: t["trends"][0].update(historical_law_match_count=1),
        lambda s,e,t: t["trends"][0].update(canonical_event_id="orphan"),
        lambda s,e,t: t["trends"].append(deepcopy(t["trends"][0])),
        lambda s,e,t: t["trends"][0]["factors"].update(historical_frequency=float("inf")),
    ]
    for i, mutate in enumerate(mutations):
        payloads = fixture()
        mutate(*payloads)
        try:
            validate_history_contract(*payloads)
        except AssertionError:
            continue
        raise AssertionError(f"corruption {i} was accepted")
    print(f"PUBLIC HISTORY CONTRACT OK: zero/matched history, separate law history, {len(mutations)} rejected corruptions")


if __name__ == "__main__":
    main()
