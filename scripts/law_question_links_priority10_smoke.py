#!/usr/bin/env python3
"""Fail closed on false law-question links and official answer drift."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
links = json.loads((ROOT / "data/law_question_links_priority10.v1.json").read_text())
questions = {}
for year in range(104, 116):
    for sitting in (1, 2):
        shard = json.loads((ROOT / f"cdn/question-shards/{year}-{sitting}.json").read_text())
        for q in shard["questions"]:
            assert q["id"] not in questions, q["id"]
            questions[q["id"]] = q
assert len(questions) == 4800
assert len(links["cards"]) == 10

for card in links["cards"]:
    rows = card["questions"]
    assert len(rows) == card["matched_question_count"]
    assert len({row["question_id"] for row in rows}) == len(rows)
    for row in rows:
        q = questions[row["question_id"]]
        assert any(alias in (q.get("law") or "") for alias in card["aliases"]), row["question_id"]
        assert row["match_strength"] == "metadata_only"
        assert row["historical_version_checked"] is False
        for key, source in (
            ("stem", "question"), ("official_answer", "answer"),
            ("law_metadata", "law"), ("subject", "subject"),
            ("year", "year"), ("round", "round"),
            ("question_number", "qno"), ("grading_mode", "grading_mode"),
            ("accepted_answers", "accepted_answers"),
        ):
            assert row[key] == q[source], (row["question_id"], key)
print("LAW QUESTION LINK CONTRACT OK: 24 shards, 4800 questions, 10 laws")
