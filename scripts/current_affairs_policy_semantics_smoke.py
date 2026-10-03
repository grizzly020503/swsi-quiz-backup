#!/usr/bin/env python3
"""Regression smoke for current-affairs policy/history semantics."""

from analyze_current_affairs_signals import analyze_item
from build_current_affairs_signals_snapshot import analyze_item_with_law_links


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

    # A population label in the vignette is context, not automatically the
    # tested concept. This reproduces the false positive where an empathy
    # question happened to use an older adult living alone as its case.
    elderly_event = {
        "id": "fixture-elderly-living-alone",
        "title": "擴大獨居老人服務",
        "summary": "強化獨居長者關懷與支持服務。",
        "category": "長照與高齡",
        "subjects": ["社會工作直接服務"],
        "exam_tags": ["獨居老人"],
    }
    elderly_questions = [
        {
            "id": "Q-EMPATHY-VIGNETTE",
            "subject": "社會工作直接服務",
            "year": "106", "round": "第一次", "qno": "28",
            "major": "會談技巧", "topic": "同理層次排序",
            "keywords": ["同理", "會談"],
            "question": "社工面對一位獨居長者時，下列何者最能展現同理？",
            "law": "",
        },
        {
            "id": "Q-ELDERLY-SERVICE",
            "subject": "社會工作直接服務",
            "year": "115", "round": "第一次", "qno": "29",
            "major": "老人社會工作", "topic": "獨居老人服務",
            "keywords": ["獨居老人", "支持服務"],
            "question": "下列何者屬於獨居老人支持服務？",
            "law": "",
        },
    ]
    elderly_out = analyze_item(elderly_event, elderly_questions)
    elderly_ids = {q["id"] for q in elderly_out["related_exam_questions"]}
    if "Q-ELDERLY-SERVICE" not in elderly_ids:
        raise SystemExit("structured elderly-service concept should remain a historical match")
    empathy = next(
        (q for q in elderly_out["related_exam_questions"] if q["id"] == "Q-EMPATHY-VIGNETTE"),
        None,
    )
    if empathy and float(empathy.get("match_score") or 0) >= 3.0:
        raise SystemExit("vignette-only population wording must not become a medium historical match")

    public_elderly = analyze_item_with_law_links(elderly_event, elderly_questions)
    public_ids = {q["id"] for q in public_elderly["related_exam_questions"]}
    if "Q-ELDERLY-SERVICE" not in public_ids:
        raise SystemExit("public snapshot must retain structured elderly-service history")
    if "Q-EMPATHY-VIGNETTE" in public_ids:
        raise SystemExit("public snapshot must hide vignette-only population history")
    if int(public_elderly["historical_exam_stats"].get("matched_question_count") or 0) != 1:
        raise SystemExit("public historical count must use the same evidence threshold as the related list")

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
