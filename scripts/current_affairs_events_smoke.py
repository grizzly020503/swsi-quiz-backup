#!/usr/bin/env python3
"""Synthetic regression tests for SWSI current-affairs V2 clustering/trends."""
from __future__ import annotations

from build_current_affairs_events_snapshot import attach_event_knowledge
from build_current_affairs_trends_snapshot import trend_for
from current_affairs_event_cluster import cluster_items


def row(
    item_id: str,
    title: str,
    source_name: str,
    source_url: str,
    published_at: str,
    *,
    source_type: str = "news",
    tags=None,
    laws=None,
    policy="medium",
    essay="medium",
    mcq="medium",
    related=None,
    history=None,
):
    return {
        "id": item_id,
        "title": title,
        "summary": title,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,
        "published_at": published_at,
        "category": "長照與高齡",
        "exam_tags": tags or ["老人", "高齡", "政策"],
        "subjects": ["社會政策與社會立法"],
        "policy_signal": policy,
        "essay_value": essay,
        "mcq_fact_density": mcq,
        "signal_confidence": "medium",
        "signal_score": 7,
        "related_laws": laws or [],
        "related_exam_questions": related or [],
        "historical_exam_stats": history or {},
        "knowledge_root": "社會工作管理",
        "knowledge_model": "management-hierarchy-over-five-exam-subjects-v3",
        "management_domains": ["服務輸送與跨網絡", "規劃與政策執行"],
        "exam_subject_axes": ["社會政策與社會立法", "社會工作直接服務"],
        "subject_topics": {
            "社會政策與社會立法": ["長照制度、老人福利與社會保障"],
            "社會工作直接服務": ["長照個案管理與家庭照顧者支持"],
        },
        "knowledge_topics": ["長照與高齡"],
        "knowledge_paths": [
            "社會工作管理 > 服務輸送與跨網絡",
            "社會工作管理 > 服務輸送與跨網絡 > 社會工作直接服務 > 長照個案管理與家庭照顧者支持",
        ],
    }


def main() -> int:
    same = [
        row(
            "a",
            "衛福部擴大獨居老人服務 啟動70萬名長者關懷訪查",
            "衛生福利部焦點新聞",
            "https://example.test/a",
            "2026-09-24T03:30:00Z",
            source_type="official",
            history={
                "matched_question_count": 8,
                "weighted_match_count": 6.25,
                "match_breakdown": {"strong": 5, "medium": 2, "concept": 1},
                "matched_year_count": 3,
                "matched_years": [109, 111, 114],
                "earliest_exam_year": 109,
                "latest_exam_year": 114,
                "corpus_latest_year": 115,
                "years_since_last_exam": 1,
                "subject_counts": {"社會政策與社會立法": 6, "社會工作": 2},
                "subject_count": 2,
                "law_match_count": 3,
                "law_match_year_count": 3,
                "law_match_years": [109, 111, 114],
                "matching_method": "event-evidence-v2.2",
                "high_confidence_match_count": 5,
            },
        ),
        row(
            "b",
            "獨老服務擴大 70萬名長者將接受關懷訪查",
            "中央社生活",
            "https://example.test/b",
            "2026-09-24T05:00:00Z",
            history={
                "matched_question_count": 5,
                "weighted_match_count": 2.75,
                "match_breakdown": {"strong": 2, "medium": 1, "concept": 1},
                "matched_year_count": 2,
                "matched_years": [110, 115],
                "earliest_exam_year": 110,
                "latest_exam_year": 115,
                "corpus_latest_year": 115,
                "years_since_last_exam": 0,
                "subject_counts": {"社會政策與社會立法": 3, "社會工作": 2},
                "subject_count": 2,
                "law_match_count": 1,
                "law_match_year_count": 1,
                "law_match_years": [115],
                "matching_method": "event-evidence-v2.2",
                "high_confidence_match_count": 2,
            },
        ),
        row(
            "c",
            "政府啟動獨居長者訪查 擴大老人服務",
            "行政院本院新聞",
            "https://example.test/c",
            "2026-09-25T01:00:00Z",
            source_type="official",
        ),
    ]
    different = row(
        "d",
        "長照機構評鑑制度修正草案公告",
        "衛生福利部公告訊息",
        "https://example.test/d",
        "2026-09-24T02:00:00Z",
        source_type="official",
        tags=["長照", "評鑑"],
        laws=["長期照顧服務法"],
        policy="high",
        mcq="high",
    )
    source_items = same + [different]
    events = attach_event_knowledge(cluster_items(source_items), source_items)
    assert len(events) == 2, events
    merged = next(x for x in events if x["source_count"] == 3)
    assert merged["official_source_count"] == 2, merged
    assert len(merged["evidence"]) == 3, merged
    assert len({x["source_url"] for x in merged["evidence"]}) == 3
    history = merged.get("historical_exam_stats") or {}
    assert history.get("matched_question_count") == 8, history
    assert history.get("matched_years") == [109, 110, 111, 114, 115], history
    assert history.get("latest_exam_year") == 115, history
    assert history.get("years_since_last_exam") == 0, history
    assert history.get("aggregation_method") == "max-quality-member-plus-year-union-v2.2", history
    assert history.get("weighted_match_count") == 6.25, history
    assert history.get("match_breakdown") == {"strong": 5, "medium": 2, "concept": 1}, history
    assert merged["knowledge_root"] == "社會工作管理", merged
    assert "服務輸送與跨網絡" in merged["management_domains"], merged
    assert "社會政策與社會立法" in merged["exam_subject_axes"], merged
    assert merged["subject_topics"]["社會工作直接服務"] == ["長照個案管理與家庭照顧者支持"], merged
    assert any(path.startswith("社會工作管理 >") for path in merged["knowledge_paths"]), merged

    bilingual_same = [
        {
            "id": "bi-zh",
            "title": "聯合國兒童基金會呼籲強化兒少保護與兒童權利保障",
            "summary": "UNICEF 推動兒少保護服務與兒童權利政策，影響100萬名兒童。",
            "source_name": "中央社國際",
            "source_url": "https://example.test/bi-zh",
            "source_type": "news",
            "published_at": "2026-09-25T02:00:00Z",
            "category": "兒少保護",
            "exam_tags": ["兒少保護", "兒童權利"],
            "subjects": ["社會政策與社會立法"],
            "concept_keys": ["child_protection", "child_rights"],
            "agency_keys": ["unicef"],
            "fact_keys": ["num:1000000"],
            "signal_score": 7,
        },
        {
            "id": "bi-en",
            "title": "UNICEF calls for stronger child protection and child rights safeguards",
            "summary": "UNICEF says the policy could strengthen services for 1 million children.",
            "source_name": "UNICEF",
            "source_url": "https://example.test/bi-en",
            "source_type": "international",
            "published_at": "2026-09-25T03:00:00Z",
            "category": "兒少保護",
            "exam_tags": ["兒少保護", "兒童權利"],
            "subjects": ["社會政策與社會立法"],
            "concept_keys": ["child_protection", "child_rights"],
            "agency_keys": ["unicef"],
            "fact_keys": ["num:1000000"],
            "signal_score": 7,
        },
    ]
    bilingual_events = cluster_items(bilingual_same)
    assert len(bilingual_events) == 1, bilingual_events
    assert bilingual_events[0]["source_count"] == 2, bilingual_events[0]
    assert set(bilingual_events[0]["concept_keys"]) == {"child_protection", "child_rights"}

    bilingual_unrelated = {
        **bilingual_same[1],
        "id": "bi-other",
        "title": "WHO expands child protection and child rights training guidance",
        "source_name": "WHO",
        "source_url": "https://example.test/bi-other",
        "agency_keys": ["who"],
        "fact_keys": ["num:2000000"],
    }
    separated = cluster_items([bilingual_same[0], bilingual_unrelated])
    assert len(separated) == 2, separated

    old_id = merged["canonical_event_id"]
    rerun_items = [
        row(
            "e",
            "獨居長者關懷訪查持續 擴大老人服務",
            "內政部新聞發布",
            "https://example.test/e",
            "2026-09-27T01:00:00Z",
            source_type="official",
        )
    ]
    rerun = cluster_items(rerun_items, previous_events=[merged])
    assert len(rerun) == 1
    assert rerun[0]["canonical_event_id"] == old_id
    assert merged["observation_count"] == 2
    assert rerun[0]["observation_count"] == 3

    chatter_event = {
        **merged,
        "official_source_count": 0,
        "policy_signal": "low",
        "essay_value": "low",
        "mcq_fact_density": "low",
        "related_laws": [],
        "related_exam_questions": [],
        "observation_count": 1,
    }
    official_policy = {
        **different,
        "canonical_event_id": "policy",
        "title": different["title"],
        "source_count": 1,
        "official_source_count": 1,
        "observation_count": 2,
        "first_seen": "2026-09-20T00:00:00Z",
        "last_seen": "2026-09-25T00:00:00Z",
        "related_laws": ["長期照顧服務法"],
        "related_exam_questions": [{"id": "SP114-1-23"}, {"id": "SP109-2-39"}],
        "historical_exam_stats": {
            "matched_question_count": 12,
            "weighted_match_count": 8.0,
            "match_breakdown": {"strong": 6, "medium": 3, "concept": 2},
            "matched_year_count": 6,
            "matched_years": [104, 106, 109, 111, 114, 115],
            "earliest_exam_year": 104,
            "latest_exam_year": 115,
            "corpus_latest_year": 115,
            "years_since_last_exam": 0,
            "subject_counts": {"社會政策與社會立法": 8, "社會工作": 4},
            "subject_count": 2,
            "law_match_count": 20,
            "law_match_year_count": 8,
            "law_match_years": [104, 105, 106, 107, 109, 111, 114, 115],
            "high_confidence_match_count": 6,
            "matching_method": "event-evidence-v2.2",
            "aggregation_method": "fixture",
        },
        "policy_signal": "high",
        "essay_value": "high",
        "mcq_fact_density": "high",
        "evidence": [{"source_url": "https://example.test/d"}],
    }
    now = "2026-09-25T12:00:00Z"
    chatter_trend = trend_for(chatter_event, now)
    policy_trend = trend_for(official_policy, now)
    assert policy_trend["trend_score"] > chatter_trend["trend_score"], (
        chatter_trend,
        policy_trend,
    )
    assert policy_trend["trend_state"] in {"rising", "sustained"}
    assert policy_trend["historical_question_count"] == 12
    assert policy_trend["historical_exam_years"] == [104, 106, 109, 111, 114, 115]
    assert policy_trend["years_since_last_related_exam"] == 0
    assert policy_trend["historical_subject_count"] == 2
    assert policy_trend["factors"]["historical_frequency"] > 0
    assert policy_trend["factors"]["recent_exam_support"] > 0
    assert policy_trend["knowledge_root"] == "社會工作管理"
    assert "服務輸送與跨網絡" in policy_trend["management_domains"]
    assert policy_trend["subject_topics"]["社會政策與社會立法"] == ["長照制度、老人福利與社會保障"]

    stale_history = {
        **official_policy,
        "historical_exam_stats": {
            **official_policy["historical_exam_stats"],
            "matched_years": [104, 105, 106],
            "matched_year_count": 3,
            "latest_exam_year": 106,
            "years_since_last_exam": 9,
        },
    }
    stale_trend = trend_for(stale_history, now)
    assert policy_trend["trend_score"] > stale_trend["trend_score"], (
        policy_trend,
        stale_trend,
    )
    assert stale_trend["years_since_last_related_exam"] == 9

    quality_base = {
        **official_policy,
        "related_laws": [],
        "historical_exam_stats": {
            **official_policy["historical_exam_stats"],
            "matched_question_count": 5,
            "matched_year_count": 2,
            "matched_years": [114, 115],
            "latest_exam_year": 115,
            "years_since_last_exam": 0,
            "law_match_count": 0,
            "law_match_year_count": 0,
            "law_match_years": [],
        },
    }
    weak_quality = {
        **quality_base,
        "historical_exam_stats": {
            **quality_base["historical_exam_stats"],
            "weighted_match_count": 1.0,
            "match_breakdown": {"strong": 0, "medium": 0, "concept": 5},
            "high_confidence_match_count": 0,
        },
    }
    strong_quality = {
        **quality_base,
        "historical_exam_stats": {
            **quality_base["historical_exam_stats"],
            "matched_question_count": 2,
            "weighted_match_count": 2.0,
            "match_breakdown": {"strong": 2, "medium": 0, "concept": 0},
            "high_confidence_match_count": 2,
        },
    }
    weak_trend = trend_for(weak_quality, now)
    strong_trend = trend_for(strong_quality, now)
    assert strong_trend["trend_score"] > weak_trend["trend_score"], (weak_trend, strong_trend)
    assert weak_trend["historical_match_breakdown"]["concept"] == 5
    assert strong_trend["historical_match_breakdown"]["strong"] == 2

    explicit_zero = {
        **quality_base,
        "historical_exam_stats": {
            **quality_base["historical_exam_stats"],
            "weighted_match_count": 0.0,
        },
    }
    zero_trend = trend_for(explicit_zero, now)
    assert zero_trend["historical_weighted_match_count"] == 0.0, "explicit zero replaced by raw count"
    assert zero_trend["factors"]["historical_frequency"] == 0.0

    print(
        "CURRENT AFFAIRS V2 EVENT/TREND SMOKE OK: "
        "3-source event deduped, bilingual event merged only with independent anchor, "
        "unrelated event separated, identity persisted, topic/law history separated, match quality weighted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
