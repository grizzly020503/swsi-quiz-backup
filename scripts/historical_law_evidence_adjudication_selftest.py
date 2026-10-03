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
evidence_snapshot = load(h.DEFAULT_EVIDENCE_SNAPSHOT)
links = load(h.DEFAULT_LINKS)
questions = h.load_question_shards(h.DEFAULT_SHARDS)

records = h.adjudicated_records(adjudication, evidence_snapshot, links, questions)
expected_qids = {
    "SP108-2-40",
    "SP104-1-31",
    "SP107-1-31",
    "SP110-2-11",
    "SP104-2-35",
    "SW-109-1-37",
}
assert {row["question_id"] for row in records} == expected_qids
assert all(row["verification_level"] == h.ADJUDICATED_LEVEL for row in records)
assert all(row["historical_version_checked"] is True for row in records)
assert all(not (h.PROTECTED_CORE_FIELDS & set(row)) for row in records)

combined = h.build_combined_registry(
    machine,
    adjudication,
    evidence_snapshot,
    links,
    questions,
)
assert combined["verified_record_count"] == 19
assert combined["historical_version_checked_count"] == 19
assert combined["verification_level_counts"] == {
    h.MACHINE_LEVEL: 13,
    h.ADJUDICATED_LEVEL: 6,
}
assert {
    row["question_id"]
    for row in combined["records"]
    if row["verification_level"] == h.ADJUDICATED_LEVEL
} == expected_qids
assert all(not (h.PROTECTED_CORE_FIELDS & set(row)) for row in combined["records"])

bad_method = copy.deepcopy(adjudication)
bad_method["records"][0]["verification_level"] = "human_verified_historical_v1"
must_fail("unknown verification method", lambda: h.validate_adjudication_payload(bad_method))

first_qid = adjudication["records"][0]["question_id"]
bad_answer_questions = copy.deepcopy(questions)
bad_answer_questions[first_qid]["answer"] = "A"
must_fail(
    "official answer drift",
    lambda: h.adjudicated_records(adjudication, evidence_snapshot, links, bad_answer_questions),
)

bad_option_questions = copy.deepcopy(questions)
answer = adjudication["records"][0]["expected_official_answer"].lower()
bad_option_questions[first_qid][f"opt_{answer}"] = "unrelated option"
must_fail(
    "official answer-option drift",
    lambda: h.adjudicated_records(adjudication, evidence_snapshot, links, bad_option_questions),
)

bad_snapshot_hash = copy.deepcopy(evidence_snapshot)
bad_snapshot_hash["records"][0]["historical_article_sha256"] = "0" * 64
must_fail(
    "durable snapshot article fingerprint drift",
    lambda: h.adjudicated_records(adjudication, bad_snapshot_hash, links, questions),
)

bad_snapshot_stage6 = copy.deepcopy(evidence_snapshot)
bad_snapshot_stage6["records"][0]["stage6_status"] = "historical_semantic_confirmed"
must_fail(
    "durable snapshot Stage6 state drift",
    lambda: h.adjudicated_records(adjudication, bad_snapshot_stage6, links, questions),
)

bad_snapshot_run = copy.deepcopy(evidence_snapshot)
bad_snapshot_run["source_run_id"] += 1
must_fail(
    "durable snapshot provenance run drift",
    lambda: h.adjudicated_records(adjudication, bad_snapshot_run, links, questions),
)

held = copy.deepcopy(adjudication)
held_qid = held["records"][0]["question_id"]
held["records"][0]["decision"] = "held"
held_combined = h.build_combined_registry(machine, held, evidence_snapshot, links, questions)
assert held_combined["verified_record_count"] == 18
assert held_qid not in {row["question_id"] for row in held_combined["records"]}

duplicate_machine = copy.deepcopy(machine)
target = adjudication["records"][0]
conflict = copy.deepcopy(duplicate_machine["records"][0])
conflict["law_name"] = target["law_name"]
conflict["question_id"] = target["question_id"]
duplicate_machine["records"].append(conflict)
duplicate_machine["verified_record_count"] += 1
duplicate_machine["historical_version_checked_count"] += 1
must_fail(
    "machine/adjudicated key conflict",
    lambda: h.build_combined_registry(
        duplicate_machine,
        adjudication,
        evidence_snapshot,
        links,
        questions,
    ),
)

print(
    "HISTORICAL LAW EVIDENCE ADJUDICATION SELFTEST OK: "
    "13 machine + 6 evidence adjudicated = 19; durable evidence drift guards pass"
)
