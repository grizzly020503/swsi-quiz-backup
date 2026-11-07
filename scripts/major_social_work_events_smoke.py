#!/usr/bin/env python3
"""Offline fail-closed major-event admission and essay publication regression."""
from __future__ import annotations

from major_social_work_events import build, evaluate, public_record


def event(
    *, title="行政院核定強化社會安全網與家庭照顧支持新制",
    sources=None, category="社工專業與社福制度",
    policy="high", essay="high", confidence="high",
):
    sources = sources if sources is not None else [
        ("行政院", "official", "2026-11-01"),
        ("中央社", "news", "2026-11-01"),
    ]
    return {
        "canonical_event_id": "event-confirmed-001",
        "title": title,
        "summary": "社會安全網跨機關合作與家庭照顧支持，新制度涉及服務分工和社工工作。",
        "category": category,
        "subjects": ["社會工作", "社會政策與社會立法"],
        "exam_subject_axes": ["社會工作", "社會政策與社會立法"],
        "primary_exam_subject_axes": ["社會工作"],
        "essay_value": essay, "policy_signal": policy,
        "signal_confidence": confidence, "source_count": len(sources),
        "official_source_count": sum(t == "official" for _, t, _ in sources),
        "last_seen": sources[-1][2] + "T00:00:00Z",
        "evidence": [{
            "source_name": n, "source_type": t,
            "source_url": "https://example.test/" + str(i),
            "published_at": day + "T10:00:00Z",
        } for i, (n, t, day) in enumerate(sources)],
    }


def check() -> None:
    good = event()
    assert evaluate(good) == (True, "confirmed_cross_source_systemic_impact")
    record = public_record(good)
    assert len(record["practice_essays"]) == 2
    assert all("（25 分）" in q["question"] for q in record["practice_essays"])
    assert all(q["type"] == "practice_only" for q in record["practice_essays"])
    assert all("考選部" not in q["question"] for q in record["practice_essays"])
    assert len(record["evidence"]) == 2

    cases = [
        ({"title": "衛福部舉辦社會安全網工作坊說明會"}, "routine_activity"),
        ({"title": "強化社會安全網與家庭服務修正草案進入研議"}, "proposal_not_enacted_or_confidently_major"),
        ({"title": "內政部審議通過大林蒲都市計畫遷村草案"}, "no_explicit_social_work_anchor"),
        ({"essay_value": "low"}, "essay_value_not_high"),
        ({"signal_confidence": "low"}, "exam_context_unreliable"),
        ({"source_count": 3}, "inconsistent_or_single_source"),
    ]
    for changes, reason in cases:
        row = {**good, **changes}
        passed, got = evaluate(row)
        assert not passed and got == reason, (changes, got)

    same_press_cycle = event(title="社福機構服務制度啟動跨部會檢討")
    assert evaluate(same_press_cycle)[1] == "insufficient_time_or_formal_outcome"

    no_official = event(sources=[
        ("媒體甲", "news", "2026-11-01"),
        ("媒體乙", "news", "2026-11-02"),
    ])
    assert evaluate(no_official)[1] == "missing_official_or_cross_day_confirmation"
    triple = event(sources=[
        ("媒體甲", "news", "2026-11-01"),
        ("媒體乙", "news", "2026-11-02"),
        ("媒體丙", "news", "2026-11-02"),
    ])
    assert evaluate(triple)[0]
    isolated_case = event(title="兒虐致死事件引起民眾議論", sources=[
        ("媒體甲", "news", "2026-11-01"),
        ("媒體乙", "news", "2026-11-02"),
    ])
    assert not evaluate(isolated_case)[0]
    qualified_case = event(title="兒虐致死事件引發社工制度全面檢討", sources=[
        ("媒體甲", "news", "2026-11-01"),
        ("媒體乙", "news", "2026-11-02"),
        ("媒體丙", "news", "2026-11-03"),
    ], policy="medium")
    assert evaluate(qualified_case)[0]

    result = build([good], [], set())
    assert result["event_count"] == 1
    assert "非考選部官方" in result["note"]
    persisted = build([], result["events"], set())
    assert persisted == result, "archive should persist without timestamp-only drift"
    revoked = build([], result["events"], {good["canonical_event_id"]})
    assert revoked["event_count"] == 0
    failing_new_observation = {**good, "essay_value": "low"}
    assert build([failing_new_observation], result["events"], set())["event_count"] == 0
    assert build([good, good], [], set())["event_count"] == 1

    print("MAJOR SOCIAL WORK EVENTS SMOKE PASS: strict evidence gates, proposals, no rumors, two original essays, historical retention, blocklist")


if __name__ == "__main__":
    check()
