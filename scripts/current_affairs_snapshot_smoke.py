#!/usr/bin/env python3
"""Regression smoke for current-affairs snapshot dedupe and source semantics."""
from build_current_affairs_snapshot import build


def row(item_id, title, published, fact, url):
    return {
        "id": item_id,
        "title": title,
        "summary": "北市社會局女社工涉嫌盜領5名個案老人存款，法院裁定羈押禁見。",
        "source_name": "中天新聞社會",
        "source_url": url,
        "source_type": "news",
        "published_at": published,
        "region": "taiwan",
        "category": "社工專業與社福制度",
        "relevance_score": 5,
        "exam_tags": ["社工"],
        "subjects": ["社會工作", "社會工作直接服務"],
        "concept_keys": [],
        "agency_keys": [],
        "fact_keys": [fact],
        "knowledge_root": "社會工作管理",
        "management_domains": ["人力與督導", "組織治理與責信"],
        "exam_subject_axes": ["社會工作", "社會工作直接服務"],
        "primary_exam_subject_axes": ["社會工作"],
        "supporting_exam_subject_axes": ["社會工作直接服務"],
        "knowledge_topics": ["社工專業與社福制度", "社工"],
    }


def main() -> int:
    items = [
        row("a", "涉侵占1200萬買名牌包 社工羈押禁見", "2026-09-24T00:28:16Z", "num:12000000", "https://example.test/a"),
        row("b", "北市女社工盜領個案千萬老本遭羈押", "2026-09-23T11:58:41Z", "num:12000000", "https://example.test/b"),
        row("c", "北市女社工盜領老人1200萬 法官裁定羈押", "2026-09-23T07:45:25Z", "num:12000000", "https://example.test/c"),
        row("d", "另一社工涉侵占3000萬遭偵辦", "2026-09-23T09:00:00Z", "num:30000000", "https://example.test/d"),
    ]
    topics = build(items)
    assert len(topics) == 2, topics

    merged = next(x for x in topics if x.get("clustered"))
    assert merged["source_count"] == 1, merged
    assert merged["article_count"] == 3, merged
    assert len(merged["sources"]) == 3, merged
    assert merged["source_name"] == "中天新聞社會", merged
    assert merged["relevance_score"] == 5, merged
    assert merged["primary_exam_subject_axes"] == ["社會工作"], merged
    assert merged["supporting_exam_subject_axes"] == ["社會工作直接服務"], merged

    separate = next(x for x in topics if not x.get("clustered"))
    assert separate["article_count"] == 1, separate
    assert separate["fact_keys"] == ["num:30000000"], separate

    print("CURRENT AFFAIRS SNAPSHOT SMOKE OK: same-publisher same-case deduped without cross-source inflation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
