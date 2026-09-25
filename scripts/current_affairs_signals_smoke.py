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

    related_counts = [len(row.get("related_exam_questions") or []) for row in items]
    if related_counts and all(count >= 5 for count in related_counts):
        raise SystemExit("historical-question matcher still saturates every live item at max_hits=5")

    for row in items:
        if "最低工資" in str(row.get("title") or ""):
            reasons = " ".join(
                str(q.get("match_reason") or "")
                for q in (row.get("related_exam_questions") or [])
            )
            forbidden = ("育嬰留職停薪", "性別平等工作法")
            if any(term in reasons for term in forbidden):
                raise SystemExit("minimum-wage event still links unrelated parental-leave/gender-law questions")

    print(
        "Current-affairs historical links: "
        + ", ".join(
            f"{str(row.get('title') or '')[:18]}={len(row.get('related_exam_questions') or [])}"
            for row in items
        )
    )

    allowed_confidence = {"low", "medium", "high"}
    for row in items:
        for key in ("id", "title", "source_url", "category", "subjects",
                    "policy_signal", "essay_value", "mcq_fact_density",
                    "signal_confidence", "signal_score", "exam_point_summary",
                    "essay_direction", "mcq_focus", "related_exam_questions"):
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
