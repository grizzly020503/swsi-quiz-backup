#!/usr/bin/env python3
"""Regression smoke for the SWSI social-work knowledge tree."""
from social_work_knowledge_tree import (
    EXAM_SUBJECTS,
    KNOWLEDGE_ROOT,
    MANAGEMENT_DOMAINS,
    classify_event_knowledge,
)


def main() -> int:
    assert KNOWLEDGE_ROOT == "社會工作管理"
    assert len(EXAM_SUBJECTS) == 5
    assert "社會工作管理" not in EXAM_SUBJECTS

    child = classify_event_knowledge(
        "重大兒虐事件引發兒少保護風險評估、責任通報與跨網絡合作檢討，並涉及兒童最佳利益。",
        category="兒少保護",
        exam_tags=["兒少保護", "責任通報"],
    )
    assert child["knowledge_root"] == KNOWLEDGE_ROOT
    assert "品質與風險管理" in child["management_domains"], child
    assert "服務輸送與跨網絡" in child["management_domains"], child
    assert "倫理與權利保障" in child["management_domains"], child
    assert "社會工作直接服務" in child["exam_subject_axes"], child
    assert "人類行為與社會環境" in child["exam_subject_axes"], child
    assert "社會政策與社會立法" in child["exam_subject_axes"], child
    assert "兒少保護" in child["knowledge_topics"], child

    wage = classify_event_knowledge(
        "最低工資新制自明年生效，調升月薪與時薪並公告相關政策。",
        category="勞動與社會保障",
        exam_tags=["最低工資", "社會保障"],
    )
    assert "規劃與政策執行" in wage["management_domains"], wage
    assert "社會政策與社會立法" in wage["exam_subject_axes"], wage

    survey = classify_event_knowledge(
        "政府公布身心障礙者生活需求調查結果與統計資料，作為後續政策成效評估依據。",
        category="身障與人權",
        exam_tags=["身障權利"],
    )
    assert "成效評估與證據" in survey["management_domains"], survey
    assert "社會工作研究方法" in survey["exam_subject_axes"], survey
    assert "倫理與權利保障" in survey["management_domains"], survey

    workforce = classify_event_knowledge(
        "社工人力不足與高案量造成留任困難，機構提出督導與職場安全改善。",
        category="社工專業與社福制度",
        exam_tags=["社工", "督導"],
    )
    assert "人力與督導" in workforce["management_domains"], workforce
    assert "組織治理與責信" in workforce["management_domains"], workforce
    assert "社會工作" in workforce["exam_subject_axes"], workforce

    for payload in (child, wage, survey, workforce):
        assert payload["knowledge_root"] == "社會工作管理"
        assert set(payload["management_domains"]).issubset(set(MANAGEMENT_DOMAINS))
        assert set(payload["exam_subject_axes"]).issubset(set(EXAM_SUBJECTS))
        assert payload["management_domains"]
        assert payload["exam_subject_axes"]

    print(
        "SOCIAL WORK KNOWLEDGE TREE SMOKE OK: "
        "management-root=yes, five-subject axes=yes, child/wage/research/workforce fixtures=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
