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


def main() -> int:
    matching_contract_smoke()
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
        if "不代表命題保證" not in str(row["exam_point_summary"]):
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
