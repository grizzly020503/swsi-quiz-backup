#!/usr/bin/env python3
"""Regression smoke for current-affairs policy/history semantics."""

from analyze_current_affairs_signals import analyze_item


def main() -> int:
    # Naming an existing act/regulation is not evidence that policy changed.
    existing_rule = "依勞工保險條例說明既有老年給付與投保規定"
    existing = analyze_item({
        "title": "勞保權益提醒",
        "summary": existing_rule,
        "category": "勞動與社會保障",
        "subjects": ["社會政策與社會立法"],
        "exam_tags": ["勞保"],
    }, [])
    if existing["policy_signal"] == "high":
        raise SystemExit("plain 條例 mention must not imply a high policy-change signal")

    changed = analyze_item({
        "title": "院會通過修正勞工保險相關規定",
        "summary": "修正後新制正式上路。",
        "category": "勞動與社會保障",
        "subjects": ["社會政策與社會立法"],
        "exam_tags": ["勞保"],
    }, [])
    if changed["policy_signal"] != "high":
        raise SystemExit("explicit amendment/new-system language must remain high signal")

    # Generic retirement-life wording must not bridge into pension history.
    retirement_event = {
        "id": "fixture-retirement",
        "title": "老年年金給付制度說明",
        "summary": "說明勞保老年年金給付條件。",
        "category": "勞動與社會保障",
        "subjects": ["社會政策與社會立法"],
        "exam_tags": ["勞保"],
    }
    questions = [
        {
            "id": "Q-PENSION",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "1",
            "major": "社會保險", "topic": "老年年金",
            "keywords": ["老年年金"], "question": "勞保老年年金制度", "law": "",
        },
        {
            "id": "Q-GENERIC-RETIREMENT",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "2",
            "major": "志願服務", "topic": "退休後生活",
            "keywords": ["退休"], "question": "退休後參與志願服務", "law": "",
        },
    ]
    retirement_out = analyze_item(retirement_event, questions)
    ids = {q["id"] for q in retirement_out["related_exam_questions"]}
    if "Q-PENSION" not in ids:
        raise SystemExit("specific pension concept should still match pension history")
    if "Q-GENERIC-RETIREMENT" in ids:
        raise SystemExit("generic 退休 wording must not create a pension-history match")

    # Serious professional incidents may be important even without policy change.
    incident = analyze_item({
        "title": "社工涉嫌侵占服務對象財產遭羈押",
        "summary": "事件涉及專業倫理、權利保障與機構責信。",
        "category": "社工專業與社福制度",
        "subjects": ["社會工作", "社會政策與社會立法"],
        "exam_tags": ["社工", "倫理"],
    }, [])
    summary = str(incident["exam_point_summary"])
    if "偏宣導或活動訊息" in summary:
        raise SystemExit("serious incident must not be described as promotion/activity noise")
    if "尚未見明確制度變動" not in summary:
        raise SystemExit("low policy signal should use neutral no-change wording")

    print("CURRENT AFFAIRS POLICY SEMANTICS SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
