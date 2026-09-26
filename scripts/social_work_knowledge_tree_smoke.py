#!/usr/bin/env python3
"""Regression smoke for the SWSI social-work knowledge tree."""
from social_work_knowledge_tree import (
    EXAM_SUBJECTS,
    KNOWLEDGE_MODEL,
    KNOWLEDGE_ROOT,
    MANAGEMENT_DOMAINS,
    classify_event_knowledge,
)


def main() -> int:
    assert KNOWLEDGE_ROOT == "社會工作管理"
    assert KNOWLEDGE_MODEL == "management-hierarchy-over-five-exam-subjects-v3"
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
    assert "兒少保護風險評估" in child["subject_topics"]["社會工作直接服務"], child
    assert any(
        path.startswith("社會工作管理 > 品質與風險管理 > 社會工作直接服務 > ")
        for path in child["knowledge_paths"]
    ), child
    assert not any("五科整合" in path for path in child["knowledge_paths"]), child

    wage = classify_event_knowledge(
        "最低工資審議會決定自116年起調升月薪與時薪，並討論消費者物價指數與產業發展，調整案陳報行政院核定。",
        category="勞動與社會保障",
        exam_tags=["最低工資", "社會保障"],
    )
    assert "規劃與政策執行" in wage["management_domains"], wage
    assert "倫理與權利保障" in wage["management_domains"], wage
    assert "社會政策與社會立法" in wage["exam_subject_axes"], wage
    assert "人類行為與社會環境" not in wage["exam_subject_axes"], wage
    assert "社會工作研究方法" not in wage["exam_subject_axes"], wage
    assert "人力與督導" not in wage["management_domains"], wage
    assert "成效評估與證據" not in wage["management_domains"], wage
    assert "方案與資源管理" not in wage["management_domains"], wage

    survey = classify_event_knowledge(
        "政府公布身心障礙者生活需求調查結果與統計資料，作為後續政策成效評估依據。",
        category="身障與人權",
        exam_tags=["身障權利"],
    )
    assert "成效評估與證據" in survey["management_domains"], survey
    assert "社會工作研究方法" in survey["exam_subject_axes"], survey
    assert "倫理與權利保障" in survey["management_domains"], survey

    workforce = classify_event_knowledge(
        "社工人力不足與高案量造成留任困難，機構提出專業督導制度與職場安全改善。",
        category="社工專業與社福制度",
        exam_tags=["社工", "督導"],
    )
    assert "人力與督導" in workforce["management_domains"], workforce
    assert "組織治理與責信" in workforce["management_domains"], workforce
    assert "社會工作" in workforce["exam_subject_axes"], workforce

    misconduct = classify_event_knowledge(
        "社工涉嫌侵占服務對象財產，司法機關裁定羈押，機構啟動內控與責信檢討。",
        category="社工專業與社福制度",
        exam_tags=["社工"],
    )

    role_title = classify_event_knowledge(
        "前北市社會局社工督導涉嫌盜領受監護宣告老人存款，法院裁定羈押禁見。",
        category="社工專業與社福制度",
        exam_tags=["社工"],
    )
    assert "組織治理與責信" in misconduct["management_domains"], misconduct
    assert "倫理與權利保障" in misconduct["management_domains"], misconduct
    assert "人力與督導" not in misconduct["management_domains"], misconduct
    assert "社會工作直接服務" not in misconduct["exam_subject_axes"], misconduct
    assert "人力與督導" not in role_title["management_domains"], role_title

    assert "統計與資料解讀" in survey["subject_topics"]["社會工作研究方法"], survey
    assert "方案與成效評估" in survey["subject_topics"]["社會工作研究方法"], survey
    assert any(
        path.startswith("社會工作管理 > 成效評估與證據 > 社會工作研究方法 > ")
        for path in survey["knowledge_paths"]
    ), survey

    for payload in (child, wage, survey, workforce, misconduct, role_title):
        assert payload["knowledge_root"] == "社會工作管理"
        assert set(payload["management_domains"]).issubset(set(MANAGEMENT_DOMAINS))
        assert set(payload["exam_subject_axes"]).issubset(set(EXAM_SUBJECTS))
        assert payload["management_domains"]
        assert payload["exam_subject_axes"]
        assert isinstance(payload["subject_topics"], dict)
        assert isinstance(payload["knowledge_paths"], list) and payload["knowledge_paths"]

    print(
        "SOCIAL WORK KNOWLEDGE TREE SMOKE OK: "
        "management-root=yes, five-subject axes=yes, subject-topics=yes, child/wage/research/workforce/misconduct fixtures=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
