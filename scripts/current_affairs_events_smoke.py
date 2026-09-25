#!/usr/bin/env python3
"""Synthetic regression tests for SWSI current-affairs V2 clustering/trends."""
from __future__ import annotations

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
        ),
        row(
            "b",
            "獨老服務擴大 70萬名長者將接受關懷訪查",
            "中央社生活",
            "https://example.test/b",
            "2026-09-24T05:00:00Z",
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
    events = cluster_items(same + [different])
    assert len(events) == 2, events
    merged = next(x for x in events if x["source_count"] == 3)
    assert merged["official_source_count"] == 2, merged
    assert len(merged["evidence"]) == 3, merged
    assert len({x["source_url"] for x in merged["evidence"]}) == 3

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

    print(
        "CURRENT AFFAIRS V2 EVENT/TREND SMOKE OK: "
        "3-source event deduped, bilingual event merged only with independent anchor, "
        "unrelated event separated, identity persisted, trend score not driven by source count alone"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
