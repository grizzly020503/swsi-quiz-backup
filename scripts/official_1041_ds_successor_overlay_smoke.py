#!/usr/bin/env python3
"""Fail-closed successor overlay for SWSI 104-1 three-row draft release.

Checks the complete staged future source/manifest/Official Core lock and
reconstructs the EXACT published predecessor. Deliberately keeps the existing
ten-source historical regression unchanged. Never deploys or writes tracked
files; the only output is a temporary predecessor overlay for historical tests.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/official_104_1_direct_service_three_ocr_candidate_20261031.json"
META = ROOT / "cdn/question-shards/manifest.json"
SHARD = ROOT / "cdn/question-shards/104-1.json"
LOCK = ROOT / "data/official_exam_readonly.lock.json"
TEXT = ("question", "opt_a", "opt_b", "opt_c", "opt_d")
ENRICH = ("major", "topic", "keywords", "exp_why", "exp_others",
          "exp_trap", "exp_raw", "mnemonic", "extension", "law", "mistake")
GRADE = ("answer", "accepted_answers", "grading_mode")
EXAM_COUNT = 4800
EXPECTED_CHANGED = {"DS-104-1-22", "DS-104-1-27", "DS-104-1-29"}
SOURCE_DESCRIPTION = (
    "DRAFT NO-GO: human-unapproved official-source correction for DS-104-1-22/27/29"
)


def must(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError("SUCCESSOR FAIL-CLOSED: " + message)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stable(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def verify(staged_root: Path) -> tuple[dict[str, bytes], dict]:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    must(audit["independent_human_approval"] is False and
         audit["release_approved"] is False and
         audit["production_database_written"] is False and
         audit["netlify_backup_changed"] is False, "must remain explicitly unapproved")
    must(set(audit["affected_ids"]) == EXPECTED_CHANGED and
         len(audit["proposed_changes"]) == 3, "not exactly 3 pinned candidates")

    before_manifest_raw = META.read_bytes()
    before_shard_raw = SHARD.read_bytes()
    before_lock_raw = LOCK.read_bytes()
    before_manifest = json.loads(before_manifest_raw)
    before_payload = json.loads(before_shard_raw)
    before_lock = json.loads(before_lock_raw)
    current_manifest_raw = (staged_root / "cdn/question-shards/manifest.json").read_bytes()
    current_shard_raw = (staged_root / "cdn/question-shards/104-1.json").read_bytes()
    current_lock_raw = (staged_root / "data/official_exam_readonly.lock.json").read_bytes()
    current_manifest = json.loads(current_manifest_raw)
    current_payload = json.loads(current_shard_raw)
    current_lock = json.loads(current_lock_raw)

    must(len(before_manifest["shards"]) == 24 and
         before_manifest["total_questions"] == EXAM_COUNT and
         before_lock["mcq_count"] == EXAM_COUNT and before_lock["essay_count"] == 240,
         "prior historical counts drifted")
    must(before_manifest["dataset_revision"] == audit["baseline_dataset_revision"],
         "base manifest revision drift")
    before_meta = next(m for m in before_manifest["shards"] if m["file"] == "104-1.json")
    must(before_meta["sha256"] == sha(before_shard_raw) ==
         audit["baseline_shard_sha256"], "base physical shard hash drift")
    must(len(before_shard_raw) == before_meta["bytes"], "base bytes drift")

    expected_payload = copy.deepcopy(before_payload)
    by_id = {r["id"]: r for r in expected_payload["questions"]}
    must(len(expected_payload["questions"]) == 200 and
         len(by_id) == 200, "base 104-1 group damaged")
    edited = set()
    for item in audit["proposed_changes"]:
        rid = item["id"]
        must(rid in EXPECTED_CHANGED and rid not in edited, "unexpected duplicate target")
        edited.add(rid)
        before = by_id[rid]
        must(all(before[k] == item["preimage_fields"][k] for k in TEXT),
             rid + " preimage mismatch")
        must({k: item["proposed_fields"][k] for k in TEXT}.keys() == set(TEXT),
             "candidate must carry all five text fields")
        must(all(before[k] == item["proposed_fields"][k] or k in item["changed_fields"]
                 for k in TEXT), "unreported edit")
        must(tuple(before[k] for k in GRADE) ==
             (item["official_answer_unchanged"], item["accepted_answers_unchanged"],
              item["grading_mode_unchanged"]), rid + " official grading drift")
        for k in TEXT:
            before[k] = item["proposed_fields"][k]
        for k in ENRICH:
            before[k] = None
        before["analysis_status"] = "review"
    must(edited == EXPECTED_CHANGED, "missing source correction")

    expected_shard_raw = stable(expected_payload)
    must(current_shard_raw == expected_shard_raw,
         "new source shard includes an undeclared byte, record or field change")
    expected_manifest = copy.deepcopy(before_manifest)
    meta = next(m for m in expected_manifest["shards"] if m["file"] == "104-1.json")
    meta["sha256"] = sha(expected_shard_raw)
    meta["bytes"] = len(expected_shard_raw)
    expected_manifest["total_uncompressed_bytes"] += len(expected_shard_raw) - before_meta["bytes"]
    expected_manifest["dataset_revision"] = sha("\n".join(
        f"{m['file']}:{m['sha256']}" for m in expected_manifest["shards"]
    ).encode("utf-8"))[:20]
    expected_manifest["source"] = SOURCE_DESCRIPTION
    expected_manifest["generated_at"] = "2026-10-31T15:00:00Z"
    must(current_manifest_raw == stable(expected_manifest),
         "staged manifest not precisely derivable from existing 24-shard manifest")
    must(expected_manifest["shard_count"] == 24 and
         expected_manifest["total_questions"] == EXAM_COUNT, "successor counts drift")
    for meta in before_manifest["shards"]:
        if meta["file"] == "104-1.json":
            continue
        raw = (ROOT / "cdn/question-shards" / meta["file"]).read_bytes()
        must(sha(raw) == meta["sha256"] and len(raw) == meta["bytes"],
             "unrelated shard physical bytes changed: " + meta["file"])

    expected_lock = copy.deepcopy(before_lock)
    must(len(before_lock["mcq"]) == EXAM_COUNT and
         len(before_lock["essays"]) == 240, "original core/essay lock count drift")
    for item in audit["proposed_changes"]:
        rid = item["id"]
        original = next(r for r in before_payload["questions"] if r["id"] == rid)
        must(before_lock["mcq"][rid] == row_hash(canonical_row(original, MCQ_FIELDS)),
             rid + " predecessor Official Core hash drift")
        after = by_id[rid]
        expected_lock["mcq"][rid] = row_hash(canonical_row(after, MCQ_FIELDS))
    expected_lock_raw = (json.dumps(expected_lock, ensure_ascii=False, indent=2) + "\n").encode()
    must(current_lock_raw == expected_lock_raw,
         "staged Official Core lock changed beyond the 3 corrected IDs")

    must(stable(before_payload) == before_shard_raw,
         "predecessor physical shard must be reproducible byte-for-byte")
    must(stable(before_manifest) == before_manifest_raw,
         "predecessor manifest must be byte-stable")
    must((json.dumps(before_lock, ensure_ascii=False, indent=2) + "\n").encode() ==
         before_lock_raw, "predecessor Official Core lock must be byte-stable")

    evidence = {
        "status": "VERIFIED_SUCCESSOR_RECONSTRUCTS_PREDECESSOR_EXACTLY_DRAFT_NO_GO",
        "human_approved": False,
        "published": False,
        "parent_dataset_revision": before_manifest["dataset_revision"],
        "candidate_dataset_revision": expected_manifest["dataset_revision"],
        "parent_manifest_sha256": sha(before_manifest_raw),
        "recovered_predecessor_manifest_sha256": sha(stable(before_manifest)),
        "parent_1041_shard_sha256": sha(before_shard_raw),
        "recovered_predecessor_1041_shard_sha256": sha(stable(before_payload)),
        "candidate_1041_shard_sha256": sha(current_shard_raw),
        "parent_official_lock_sha256": sha(before_lock_raw),
        "recovered_predecessor_official_lock_sha256": sha(
            (json.dumps(before_lock, ensure_ascii=False, indent=2) + "\n").encode()),
        "updated_1041_ids": sorted(EXPECTED_CHANGED),
        "other_mcq_identical_count": 4797,
        "grading_tuple_unchanged_count": EXAM_COUNT,
        "essay_lock_unchanged_count": len(before_lock["essays"]),
        "historical_pinned_transition_must_run_on_restored_predecessor": True,
    }
    return {
        "cdn/question-shards/104-1.json": before_shard_raw,
        "cdn/question-shards/manifest.json": before_manifest_raw,
        "data/official_exam_readonly.lock.json": before_lock_raw,
    }, evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    dest = args.out.resolve()
    must(dest != ROOT and ROOT not in dest.parents, "cannot write tracked files")
    must(not dest.exists(), "destination must not preexist")
    must(candidate != ROOT and ROOT not in candidate.parents, "must inspect external staged tree")
    originals, evidence = verify(candidate)
    dest.mkdir(parents=True)
    for subpath, body in originals.items():
        file = dest / subpath
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(body)
    (dest / "successor-reconciliation.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    must(len(list(dest.rglob("*"))) == 7,
         "expected 3 predecessor files, 1 evidence file, 3 dirs")
    print("SUCCESSOR REGRESSION PASS: exact predecessor 104-1, manifest and Official Core lock recovered; 4797 unrelated MCQs, 4800 grading and 240 essay locks unchanged; human approval false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
