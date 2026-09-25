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
        "exam_tags": ["責任通報", "安置", "最佳利益"],
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
    wage = {
        "id": "fixture-wage",
        "title": "最低工資調升至新標準",
        "summary": "最低工資審議後公告新標準。",
        "category": "勞動與社會保障",
        "exam_tags": ["最低工資", "保障"],
        "subjects": ["社會政策與社會立法"],
        "concept_keys": [],
    }
    wage_questions = [
        {
            "id": "Q-BASIC-WAGE",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第二次", "qno": "29",
            "major": "社會救助", "topic": "工作收入認定與基本工資",
            "keywords": ["基本工資"], "question": "基本工資與工作收入認定", "law": "",
        },
        {
            "id": "Q-PARENTAL-LEAVE",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第一次", "qno": "21",
            "major": "婦女與性別法規", "topic": "育嬰留職停薪",
            "keywords": ["性別平等工作法", "育嬰留職停薪"],
            "question": "育嬰留職停薪規定", "law": "",
        },
    ]
    out = analyze_item(wage, wage_questions)
    ids = {q["id"] for q in out["related_exam_questions"]}
    if "Q-BASIC-WAGE" not in ids:
        raise SystemExit("最低工資 must bridge to historical 基本工資 through synonym evidence")
    if "Q-PARENTAL-LEAVE" in ids:
        raise SystemExit("broad labor category leaked parental-leave question into minimum-wage history")

    child_survey = {
        "id": "fixture-child-survey",
        "title": "兒童及少年生活狀況調查",
        "summary": "依兒童及少年福利與權益保障法辦理生活狀況調查。",
        "category": "兒少保護",
        "exam_tags": ["兒童", "少年", "政策", "權益"],
        "subjects": ["社會政策與社會立法"],
    }
    child_questions = [
        {
            "id": "Q-CHILD-SURVEY",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第二次", "qno": "23",
            "major": "兒少福利法規", "topic": "調查統計機制",
            "keywords": ["生活狀況調查"],
            "question": "兒少生活狀況調查統計機制",
            "law": "兒童及少年福利與權益保障法",
        },
        {
            "id": "Q-CHILD-ADOPTION",
            "subject": "社會政策與社會立法",
            "year": "115", "round": "第二次", "qno": "22",
            "major": "兒少福利法規", "topic": "收養程序與媒合",
            "keywords": ["收養", "媒合"],
            "question": "兒少收養程序",
            "law": "兒童及少年福利與權益保障法",
        },
    ]
    out = analyze_item(child_survey, child_questions)
    ids = {q["id"] for q in out["related_exam_questions"]}
    if ids != {"Q-CHILD-SURVEY"}:
        raise SystemExit(f"same-law unrelated child questions leaked into survey history: {ids}")
    stats = out.get("historical_exam_stats") or {}
    if stats.get("matched_question_count") != 1:
        raise SystemExit(f"same-topic count mismatch: {stats}")
    if stats.get("law_match_count") != 2:
        raise SystemExit(f"law history must remain separate from topic history: {stats}")
    if stats.get("matching_method") != "event-evidence-v2.2":
        raise SystemExit(f"unexpected matching method: {stats}")


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
            "law_match_year_count", "law_match_years",
            "weighted_match_count", "match_breakdown",
            "high_confidence_match_count", "matching_method",
        ):
            if key not in stats:
                raise SystemExit(f"historical exam stats missing field: {key}")
        if int(stats.get("matched_question_count") or 0) < len(row["related_exam_questions"]):
            raise SystemExit("historical full count cannot be smaller than public related list")
        breakdown = stats.get("match_breakdown") or {}
        if set(breakdown) != {"strong", "medium", "concept"}:
            raise SystemExit(f"invalid historical match breakdown: {breakdown}")
        if float(stats.get("weighted_match_count") or 0) > int(stats.get("matched_question_count") or 0):
            raise SystemExit("weighted historical count cannot exceed raw same-topic count")
        for q in row["related_exam_questions"]:
            for key in ("id", "subject", "year", "round", "qno", "major", "topic", "match_reason", "match_score"):
                if key not in q:
                    raise SystemExit(f"related question missing field: {key}")
            if "question" in q or "opt_a" in q or "opt_b" in q or "opt_c" in q or "opt_d" in q:
                raise SystemExit("public signal snapshot must not expose full question content")

    live_counts = [
        (str(row.get("title") or "")[:18], int((row.get("historical_exam_stats") or {}).get("matched_question_count") or 0))
        for row in items
    ]
    print("Current-affairs same-topic history: " + ", ".join(f"{title}={count}" for title, count in live_counts))
    print(f"Current-affairs signals smoke PASS: {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
