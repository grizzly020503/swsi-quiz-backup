#!/usr/bin/env python3
"""Offline, reversible two-question source-bundle rehearsal for draft PR #593.

This program is intentionally NOT a release and NEVER writes to source paths,
main, Supabase, Cloudflare, or Netlify. It validates exact full-corpus baseline,
projects two option fixes into an ephemeral directory, checks the simulated
manifest and Official Core lock, and reverses the entire projection byte-for-byte.

It does not certify independent human PDF review, production DB trigger/rollback,
or actual student-side rendering. The verdict is always NO-GO.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash
from official_p0_option_order_candidate_selftest import verify as verify_candidate

ROOT = Path(__file__).resolve().parents[1]
SHARD_DIR = ROOT / "cdn" / "question-shards"
MANIFEST_PATH = SHARD_DIR / "manifest.json"
LOCK_PATH = ROOT / "data" / "official_exam_readonly.lock.json"
PROOF_PATH = ROOT / "audit" / "official_p0_option_order_candidate_20261110.json"
OPTIONS = ("opt_a", "opt_b", "opt_c", "opt_d")
GRADING = ("answer", "accepted_answers", "grading_mode")
ENRICHMENT = ("exp_why", "exp_others", "exp_trap", "exp_raw",
              "mnemonic", "extension", "law", "mistake")
TARGET_IDS = {"SP104-2-37", "SP107-1-40"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def grading_digest(rows: dict[str, dict]) -> str:
    return sha(json.dumps(
        [(ident, *(rows[ident].get(k) for k in GRADING)) for ident in sorted(rows)],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8"))


def validate_base() -> tuple[dict, dict, dict[str, bytes], dict[str, dict], dict[str, str]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == lock["schema_version"] == 1
    assert manifest["total_questions"] == lock["mcq_count"] == 4800
    assert manifest["shard_count"] == manifest["baseline_shard_count"] == 24
    assert lock["essay_count"] == len(lock["essays"]) == 240
    assert len(lock["mcq"]) == 4800
    assert len(manifest["shards"]) == 24

    physical, questions, location = {}, {}, {}
    seen = set()
    for entry in manifest["shards"]:
        name = entry["file"]
        assert name not in seen
        seen.add(name)
        assert name.endswith(".json") and "/" not in name and "\\" not in name
        raw = (SHARD_DIR / name).read_bytes()
        assert sha(raw) == entry["sha256"], ("bad main manifest hash", name)
        assert len(raw) == entry["bytes"], ("bad main manifest length", name)
        payload = json.loads(raw)
        assert encode(payload) == raw, ("unexpected baseline serialization", name)
        assert payload["schema_version"] == 1
        assert payload["question_count"] == entry["question_count"] == len(payload["questions"]) == 200
        assert payload["year"] == entry["year"] and payload["round"] == entry["round"]
        for row in payload["questions"]:
            ident = row["id"]
            assert ident not in questions, ("duplicate main ID", ident)
            questions[ident] = row
            location[ident] = name
            assert lock["mcq"].get(ident) == row_hash(canonical_row(row, MCQ_FIELDS)), ("lock mismatch", ident)
        physical[name] = raw
    assert len(questions) == 4800
    assert len(location) == 4800
    assert sum(map(len, physical.values())) == manifest["total_uncompressed_bytes"]
    assert set(questions) == set(lock["mcq"])
    return manifest, lock, physical, questions, location


def rehearse() -> None:
    assert verify_candidate() == 0
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    assert proof["status"] == "DRAFT_NO_GO"
    assert proof["independent_human_approval"] is False
    assert proof["owner_release_pin"] is False
    assert proof["production_db_written"] is False
    assert proof["changed_question_count"] == 2 and proof["changed_option_count"] == 5
    assert {r["id"] for r in proof["rows"]} == TARGET_IDS

    manifest, lock, physical, original, location = validate_base()
    target_rows = {r["id"]: r for r in proof["rows"]}
    projected_manifest = copy.deepcopy(manifest)
    projected_lock = copy.deepcopy(lock)
    projection = {}
    changed_ids = set()
    changed_fields = {}
    original_grading = grading_digest(original)

    with tempfile.TemporaryDirectory(prefix="swsi-two-option-rehearsal-") as scratch:
        scratch_dir = Path(scratch)
        for entry in projected_manifest["shards"]:
            name = entry["file"]
            target_ids_here = {ident for ident in TARGET_IDS if location[ident] == name}
            if not target_ids_here:
                assert physical[name] == (SHARD_DIR / name).read_bytes()
                continue
            data = json.loads(physical[name])
            original_data = copy.deepcopy(data)
            for row in data["questions"]:
                ident = row["id"]
                if ident not in target_ids_here:
                    continue
                candidate = target_rows[ident]
                assert original[ident] == row
                assert [row[key] for key in OPTIONS] == candidate["old_options"]
                preimage = copy.deepcopy(row)
                for field, new_value in zip(OPTIONS, candidate["proposed_options"]):
                    row[field] = new_value
                row["analysis_status"] = "review"
                diff = {k for k in set(row) | set(preimage) if row.get(k) != preimage.get(k)}
                expected_diff = set(candidate["changed_fields"])
                if preimage["analysis_status"] != "review":
                    expected_diff.add("analysis_status")
                assert diff == expected_diff, (ident, diff, expected_diff)
                assert all(row.get(k) == preimage.get(k) for k in GRADING), ident
                assert all(row.get(k) == preimage.get(k) for k in ENRICHMENT), ident
                assert row["source_url"] == preimage["source_url"]
                assert row["source_exam_code"] == preimage["source_exam_code"]
                projected_lock["mcq"][ident] = row_hash(canonical_row(row, MCQ_FIELDS))
                assert projected_lock["mcq"][ident] != lock["mcq"][ident]
                changed_ids.add(ident)
                changed_fields[ident] = sorted(diff)

            new_raw = encode(data)
            assert new_raw != physical[name]
            entry["bytes"] = len(new_raw)
            entry["sha256"] = sha(new_raw)
            projection[name] = new_raw
            (scratch_dir / name).write_bytes(new_raw)
            assert (scratch_dir / name).read_bytes() == new_raw

            # Reversibility: exactly the original source JSON bytes, not just
            # equivalent semantic fields, must be restored after a rollback.
            for row in data["questions"]:
                if row["id"] in target_ids_here:
                    row.clear()
                    row.update(copy.deepcopy(original[row["id"]]))
            assert data == original_data
            assert encode(data) == physical[name], ("not byte-reversible", name)

        assert changed_ids == TARGET_IDS
        assert len(projection) == 2
        assert set(projected_lock["mcq"]) == set(lock["mcq"])
        assert projected_lock["essays"] == lock["essays"]
        assert sum(projected_lock["mcq"][id_] != lock["mcq"][id_]
                   for id_ in lock["mcq"]) == 2
        assert set(changed_fields["SP104-2-37"]) == {"opt_b", "opt_c", "opt_d"}
        assert set(changed_fields["SP107-1-40"]) == {"opt_c", "opt_d", "analysis_status"}

        staged_questions = {id_: copy.deepcopy(row) for id_, row in original.items()}
        for name, raw in projection.items():
            rows = json.loads(raw)["questions"]
            for row in rows:
                if row["id"] in TARGET_IDS:
                    staged_questions[row["id"]] = row
        assert len(staged_questions) == 4800
        assert grading_digest(staged_questions) == original_grading
        assert all(staged_questions[id_] == original[id_]
                   for id_ in original if id_ not in TARGET_IDS)
        assert sum(original[id_] != staged_questions[id_] for id_ in original) == 2

        for entry in projected_manifest["shards"]:
            raw = projection.get(entry["file"], physical[entry["file"]])
            assert entry["bytes"] == len(raw)
            assert entry["sha256"] == sha(raw)
        projected_manifest["total_uncompressed_bytes"] = sum(
            entry["bytes"] for entry in projected_manifest["shards"]
        )
        assert projected_manifest["total_questions"] == 4800
        assert projected_manifest["shard_count"] == 24
        assert all(a == b for a, b in zip(manifest["shards"], projected_manifest["shards"])
                   if a["file"] not in projection)
        assert {e["file"] for e in projected_manifest["shards"]} == {
            e["file"] for e in manifest["shards"]
        }
        # Data revision and release provenance must be finalized by the guarded
        # real release builder; this is a simulation, not a publishable manifest.
        assert projected_manifest["dataset_revision"] == manifest["dataset_revision"]
        assert projected_manifest["source"] == manifest["source"]
        assert projected_manifest["generated_at"] == manifest["generated_at"]

        # Run two opposite projections in the disposable work directory only.
        for name in projection:
            restored = physical[name]
            (scratch_dir / name).write_bytes(restored)
            assert (scratch_dir / name).read_bytes() == restored
        assert all((scratch_dir / name).read_bytes() == physical[name] for name in projection)
        assert lock["essays"] == projected_lock["essays"]
        assert set(projection) == {"104-2.json", "107-1.json"}

    print(json.dumps({
        "rehearsal": "PASS_NO_RELEASE",
        "total_questions": 4800, "shards": 24, "essays_locked": 240,
        "modified_mcq": sorted(changed_ids), "modified_shards": sorted(projection),
        "changed_fields": changed_fields,
        "unchanged_questions": 4798,
        "grading_tuple_sha256_before": original_grading,
        "grading_tuple_sha256_after": grading_digest(staged_questions),
        "original_shard_sha256": {name: sha(physical[name]) for name in sorted(projection)},
        "simulated_shard_sha256": {name: sha(projection[name]) for name in sorted(projection)},
        "official_mcq_lock_differences": 2, "essay_lock_differences": 0,
        "simulated_manifest_total_bytes": projected_manifest["total_uncompressed_bytes"],
        "source_review_unresolved": 428, "human_approved": False,
        "production_db_written": False, "published": False,
        "rollback_original_shard_bytes_restored": True,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    rehearse()
