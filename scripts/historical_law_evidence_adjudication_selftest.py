#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

import historical_law_evidence_adjudication as h

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def must_fail(label: str, fn) -> None:
    try:
        fn()
    except (ValueError, AssertionError):
        return
    raise AssertionError(f"expected fail-closed rejection: {label}")


machine = load(h.DEFAULT_MACHINE)
adjudication = load(h.DEFAULT_ADJUDICATION)
stage4 = load(h.DEFAULT_STAGE4)
stage5 = load(h.DEFAULT_STAGE5)
stage6 = load(h.DEFAULT_STAGE6)
links = load(h.DEFAULT_LINKS)
questions = h.load_question_shards(h.DEFAULT_SHARDS)

records = h.adjudicated_records(adjudication, stage4, stage5, stage6, links, questions)
expected_qids = {
    "SP108-2-40", "SP104-1-31", "SP107-1-31",
    "SP110-2-11", "SP104-2-35", "SW-109-1-37",
}
assert {row["question_id"] for row in records} == expected_qids
assert all(row["verification_level"] == h.ADJUDICATED_LEVEL for row in records)
assert all(row["historical_version_checked"] is True for row in records)
assert all(not (h.PROTECTED_CORE_FIELDS & set(row)) for row in records)

combined = h.build_combined_registry(machine, adjudication, stage4, stage5, stage6, links, questions)
assert combined["verified_record_count"] == 19
assert combined["historical_version_checked_count"] == 19
assert combined["verification_level_counts"] == {
    h.MACHINE_LEVEL: 13,
    h.ADJUDICATED_LEVEL: 6,
}
assert {row["question_id"] for row in combined["records"] if row["verification_level"] == h.ADJUDICATED_LEVEL} == expected_qids
assert all(not (h.PROTECTED_CORE_FIELDS & set(row)) for row in combined["records"])

bad_method = copy.deepcopy(adjudication)
bad_method["records"][0]["verification_level"] = "human_verified_historical_v1"
must_fail("unknown verification method", lambda: h.validate_adjudication_payload(bad_method))

bad_answer_questions = copy.deepcopy(questions)
first_qid = adjudication["records"][0]["question_id"]
bad_answer_questions[first_qid]["answer"] = "A"
must_fail(
    "official answer drift",
    lambda: h.adjudicated_records(adjudication, stage4, stage5, stage6, links, bad_answer_questions),
)

bad_option_questions = copy.deepcopy(questions)
answer = adjudication["records"][0]["expected_official_answer"].lower()
bad_option_questions[first_qid][f"opt_{answer}"] = "unrelated option"
must_fail(
    "official answer-option drift",
    lambda: h.adjudicated_records(adjudication, stage4, stage5, stage6, links, bad_option_questions),
)

bad_stage4 = copy.deepcopy(stage4)
target = adjudication["records"][0]
for row in bad_stage4["records"]:
    if h.key(row) == h.key(target):
        row["historical_article_sha256"] = "0" * 64
        break
must_fail(
    "Stage4 article fingerprint drift",
    lambda: h.adjudicated_records(adjudication, bad_stage4, stage5, stage6, links, questions),
)

bad_stage6 = copy.deepcopy(stage6)
for row in bad_stage6["records"]:
    if h.key(row) == h.key(target):
        row["status"] = "historical_semantic_confirmed"
        break
must_fail(
    "Stage6 state drift",
    lambda: h.adjudicated_records(adjudication, stage4, stage5, bad_stage6, links, questions),
)

held = copy.deepcopy(adjudication)
held_qid = held["records"][0]["question_id"]
held["records"][0]["decision"] = "held"
held_combined = h.build_combined_registry(machine, held, stage4, stage5, stage6, links, questions)
assert held_combined["verified_record_count"] == 18
assert held_qid not in {row["question_id"] for row in held_combined["records"]}

duplicate_machine = copy.deepcopy(machine)
conflict = copy.deepcopy(duplicate_machine["records"][0])
conflict["law_name"] = target["law_name"]
conflict["question_id"] = target["question_id"]
duplicate_machine["records"].append(conflict)
duplicate_machine["verified_record_count"] += 1
duplicate_machine["historical_version_checked_count"] += 1
must_fail(
    "machine/adjudicated key conflict",
    lambda: h.build_combined_registry(duplicate_machine, adjudication, stage4, stage5, stage6, links, questions),
)

print("HISTORICAL LAW EVIDENCE ADJUDICATION SELFTEST OK: 13 machine + 6 evidence adjudicated = 19, with fail-closed drift guards")
