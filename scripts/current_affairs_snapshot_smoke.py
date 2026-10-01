#!/usr/bin/env python3
"""Regression smoke for current-affairs snapshot dedupe and publication quality."""
from build_current_affairs_snapshot import build, publishable_row


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


def fixture(item_id, title, summary, source_name, category):
    return {
        "id": item_id,
        "title": title,
        "summary": summary,
        "source_name": source_name,
        "source_url": f"https://example.test/{item_id}",
        "source_type": "official" if "移民署" in source_name else "news",
        "published_at": "2026-09-30T00:00:00Z",
        "region": "taiwan",
        "category": category,
        "relevance_score": 6,
        "exam_tags": ["新制"],
        "subjects": ["社會工作", "社會政策與社會立法"],
        "concept_keys": [],
        "agency_keys": [],
        "fact_keys": [],
        "knowledge_root": "社會工作管理",
        "management_domains": ["規劃與政策執行"],
        "exam_subject_axes": ["社會工作", "社會政策與社會立法"],
        "primary_exam_subject_axes": ["社會政策與社會立法"],
        "supporting_exam_subject_axes": ["社會工作"],
        "knowledge_topics": [category],
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

    # Real pollution pattern observed in the tracked snapshot: the Immigration
    # Agency feed leaked a road-traffic story that upstream scoring classified
    # as child protection because it mentioned minors plus a new system/reform.
    traffic_noise = fixture(
        "traffic-noise",
        "重大違規再犯講習3新制9/30上路 估2.8萬人適用",
        "公路局推動駕照管理改革，新增未滿18歲少年無照駕駛再犯班，並加強兒童交通安全宣導。",
        "移民署新住民政策法規",
        "兒少保護",
    )
    assert publishable_row(traffic_noise) is False, traffic_noise
    assert build([traffic_noise]) == []

    # The source-scope gate must not suppress genuinely relevant immigration
    # policy from the same feed.
    migration_policy = fixture(
        "migration-policy",
        "新住民居留與家庭團聚服務新制上路",
        "移民署說明新住民居留、家庭團聚與通譯服務調整。",
        "移民署新住民政策法規",
        "移工與新住民",
    )
    assert publishable_row(migration_policy) is True, migration_policy

    # Child protection must require substantive protection/harm/system evidence,
    # not merely generic age words such as 少年／兒童 plus 改革 or 新制.
    generic_minor_policy = fixture(
        "minor-traffic",
        "未滿18歲無照駕駛講習新制上路",
        "少年與兒童交通安全制度改革，延長違規講習時數。",
        "一般官方來源",
        "兒少保護",
    )
    assert publishable_row(generic_minor_policy) is False, generic_minor_policy

    # Kai-kai-type serious cases remain publishable even when the headline does
    # not literally say 兒虐／修法: harm + service-system evidence is enough.
    serious_child_system_failure = fixture(
        "child-system-failure",
        "男童遭保母不當對待死亡 社會局檢討訪視機制",
        "事件涉及安置前後訪視、社工通報與跨網絡保護流程。",
        "TVBS新聞社會",
        "兒少保護",
    )
    assert publishable_row(serious_child_system_failure) is True, serious_child_system_failure
    assert build([serious_child_system_failure]), serious_child_system_failure

    print("CURRENT AFFAIRS SNAPSHOT SMOKE OK: dedupe + publication quality gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
