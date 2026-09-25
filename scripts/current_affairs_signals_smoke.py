#!/usr/bin/env python3
"""Fail-closed smoke test for the public Issue #74 exam-signal snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from analyze_current_affairs_signals import analyze_item


def matching_contract_smoke() -> None:
    row = {
        "id": "fixture-1",
        "title": "兒少保護制度與通報支持",
        "summary": "兒童與少年通報、安置及最佳利益。",
        "category": "兒少保護",
        "exam_tags": ["兒童", "少年", "政策", "權益"],
        "subjects": ["社會政策與社會立法"],
    }
    questions = [
        {
            "id": "Q-CHILD-1",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "10",
            "major": "兒少保護", "topic": "責任通報與兒少保護",
            "keywords": ["兒童", "通報"], "question": "兒少保護責任通報", "law": "",
        },
        {
            "id": "Q-CHILD-2",
            "subject": "社會政策與社會立法",
            "year": "112", "round": "第二次", "qno": "21",
            "major": "兒少保護", "topic": "兒少最佳利益與安置",
            "keywords": ["兒少", "安置", "最佳利益"], "question": "兒少安置與最佳利益", "law": "",
        },
        {
            "id": "Q-CHILD-3",
            "subject": "社會政策與社會立法",
            "year": "109", "round": "第一次", "qno": "18",
            "major": "兒少保護", "topic": "責任通報",
            "keywords": ["兒童", "通報", "保護"], "question": "兒童保護責任通報", "law": "",
        },
        {
            "id": "Q-WEAK-1",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "11",
            "major": "一般政策", "topic": "政策",
            "keywords": ["政策"], "question": "一般政策問題", "law": "",
        },
    ]
    out = analyze_item(row, questions)
    ids = {q["id"] for q in out["related_exam_questions"]}
    if "Q-CHILD-1" not in ids:
        raise SystemExit("topic-aware historical question matching failed")
    if "Q-WEAK-1" in ids:
        raise SystemExit("weak generic keyword caused a false historical-question match")
    stats = out.get("historical_exam_stats") or {}
    if int(stats.get("matched_question_count") or 0) != 3:
        raise SystemExit(f"historical exam full-count mismatch: {stats}")
    if stats.get("matched_years") != [109, 112, 115]:
        raise SystemExit(f"historical exam year coverage mismatch: {stats}")
    if stats.get("latest_exam_year") != 115 or stats.get("years_since_last_exam") != 0:
        raise SystemExit(f"historical exam recency mismatch: {stats}")
    if stats.get("subject_count") != 1:
        raise SystemExit(f"historical subject count mismatch: {stats}")


def event_specific_history_smoke() -> None:
    labor_row = {
        "id": "fixture-wage",
        "title": "最低工資調升至新標準",
        "summary": "最低工資審議後公告新標準。",
        "category": "勞動與社會保障",
        "exam_tags": ["最低工資", "行政院", "保障"],
        "subjects": ["社會政策與社會立法"],
        "concept_keys": [],
    }
    questions = [
        {
            "id": "Q-WAGE",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "20",
            "major": "勞動政策", "topic": "最低工資",
            "keywords": ["最低工資"], "question": "最低工資制度與審議", "law": "",
        },
        {
            "id": "Q-PARENTAL-LEAVE",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "21",
            "major": "性別工作平等法", "topic": "育嬰留職停薪",
            "keywords": ["性別平等工作法", "育嬰留職停薪"],
            "question": "育嬰留職停薪規定", "law": "",
        },
    ]
    out = analyze_item(labor_row, questions)
    ids = {q["id"] for q in out["related_exam_questions"]}
    if "Q-WAGE" not in ids:
        raise SystemExit("exact event tag failed to link a historical question")
    if "Q-PARENTAL-LEAVE" in ids:
        raise SystemExit("broad category terms caused an unrelated labor-question match")
    if out["historical_exam_stats"]["matched_question_count"] != 1:
        raise SystemExit("unsupported category match polluted full historical statistics")
    polluted = {**labor_row, "exam_tags": [*labor_row["exam_tags"], "育嬰留職停薪"]}
    if any(q["id"] == "Q-PARENTAL-LEAVE" for q in analyze_item(polluted, questions)["related_exam_questions"]):
        raise SystemExit("tag absent from event text became historical evidence")
    zero = analyze_item(labor_row, questions[1:])
    if zero["related_exam_questions"] or zero["historical_exam_stats"]["matched_question_count"]:
        raise SystemExit("zero evidence must retain zero related questions")
    if zero["historical_exam_stats"]["latest_exam_year"] is not None:
        raise SystemExit("zero evidence must not invent a latest matching exam year")
    corpus = [{**questions[0], "id": f"Q-WAGE-{i}", "year": str(109 + i)} for i in range(7)]
    full = analyze_item(labor_row, corpus, max_related=2)
    if len(full["related_exam_questions"]) != 2 or full["historical_exam_stats"]["matched_question_count"] != 7:
        raise SystemExit("public top-N limit must not truncate full historical statistics")

    ilo_row = {
        "id": "fixture-ilo",
        "title": "ILO project improves social protection coverage",
        "summary": "Policy reforms strengthen social protection systems.",
        "category": "社會救助與居住",
        "exam_tags": ["社會保障"],
        "subjects": ["社會政策與社會立法"],
        "concept_keys": ["social_protection"],
    }
    cross_language = [
        {
            "id": "Q-SOCIAL-ASSISTANCE",
            "subject": "社會政策與社會立法",
            "year": "114", "round": "第一次", "qno": "30",
            "major": "社會救助", "topic": "社會救助制度",
            "keywords": ["社會救助"], "question": "社會救助制度之保障功能", "law": "",
        },
        {
            "id": "Q-HOUSING-ONLY",
            "subject": "社會政策與社會立法",
            "year": "114", "round": "第一次", "qno": "31",
            "major": "住宅政策", "topic": "社會住宅",
            "keywords": ["住宅"], "question": "社會住宅政策", "law": "",
        },
    ]
    out = analyze_item(ilo_row, cross_language)
    related = {q["id"]: q for q in out["related_exam_questions"]}
    if "Q-SOCIAL-ASSISTANCE" not in related:
        raise SystemExit("bilingual canonical concept failed to link historical question")
    if "Q-HOUSING-ONLY" in related:
        raise SystemExit("same broad category caused an unsupported historical match")
    reason = related["Q-SOCIAL-ASSISTANCE"].get("match_reason") or ""
    if "共同概念" not in reason:
        raise SystemExit("cross-language match must expose its concept evidence")
    chinese = {**ilo_row, "title": "社會救助制度改革", "summary": "社會救助保障", "exam_tags": ["社會救助"]}
    same_concept = analyze_item(chinese, cross_language)["related_exam_questions"]
    if same_concept[0]["match_score"] != related["Q-SOCIAL-ASSISTANCE"]["match_score"]:
        raise SystemExit("translated concept/tag/category aliases must not inflate match strength")



def main() -> int:
    matching_contract_smoke()
    event_specific_history_smoke()
    p = Path("auto/current_affairs_signals.json")
    if not p.exists():
        raise SystemExit("current-affairs signal snapshot missing")

    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise SystemExit("unexpected current-affairs signal schema")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise SystemExit("signal snapshot has no items")
    if len(items) > 30:
        raise SystemExit("public signal snapshot exceeds limit")
    if int(data.get("questions_loaded") or 0) < 4800:
        raise SystemExit("signal snapshot must match the current official 4800-question baseline")

    allowed_confidence = {"low", "medium", "high"}
    for row in items:
        if "最低工資" in row.get("title", "") or "延後退休續勞保" in row.get("title", ""):
            reasons = " ".join(q.get("match_reason", "") for q in row.get("related_exam_questions", []))
            if "育嬰留職停薪" in reasons or "性別平等工作法" in reasons:
                raise SystemExit("live wage/pension event links unrelated parental-leave questions")
        for key in ("id", "title", "source_url", "category", "subjects",
                    "policy_signal", "essay_value", "mcq_fact_density",
                    "signal_confidence", "signal_score", "exam_point_summary",
                    "essay_direction", "mcq_focus", "related_exam_questions",
                    "historical_exam_stats"):
            if key not in row:
                raise SystemExit(f"missing field: {key}")
        if row["signal_confidence"] not in allowed_confidence:
            raise SystemExit("invalid signal confidence")
        if not isinstance(row["signal_score"], int) or not 0 <= row["signal_score"] <= 10:
            raise SystemExit("invalid signal score")
        if "不代表命題保證" not in str(row["essay_direction"]):
            raise SystemExit("essay direction must use non-guarantee wording")
        if "命題保證" not in str(row["exam_point_summary"]):
            raise SystemExit("exam summary must use non-guarantee wording")
        if not isinstance(row["mcq_focus"], list):
            raise SystemExit("mcq_focus must be a list")
        if not isinstance(row["related_exam_questions"], list):
            raise SystemExit("related_exam_questions must be a list")
        stats = row.get("historical_exam_stats")
        if not isinstance(stats, dict):
            raise SystemExit("historical_exam_stats must be an object")
        for key in (
            "matched_question_count", "matched_year_count", "matched_years",
            "latest_exam_year", "corpus_latest_year", "years_since_last_exam",
            "subject_counts", "subject_count", "law_match_count",
            "high_confidence_match_count",
        ):
            if key not in stats:
                raise SystemExit(f"historical exam stats missing field: {key}")
        if int(stats.get("matched_question_count") or 0) < len(row["related_exam_questions"]):
            raise SystemExit("historical full count cannot be smaller than public related list")
        for q in row["related_exam_questions"]:
            for key in ("id", "subject", "year", "round", "qno", "major", "topic", "match_reason", "match_score"):
                if key not in q:
                    raise SystemExit(f"related question missing field: {key}")
            if "question" in q or "opt_a" in q or "opt_b" in q or "opt_c" in q or "opt_d" in q:
                raise SystemExit("public signal snapshot must not expose full question content")

    print(f"Current-affairs signals smoke PASS: {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
