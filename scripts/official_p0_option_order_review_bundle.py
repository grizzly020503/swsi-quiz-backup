#!/usr/bin/env python3
"""Build a strictly review-only two-question source bundle in an offline ZIP.

Never updates repository files, Supabase, Cloudflare or Netlify.
All proposed manifest and lock files are simulations; the real source
release builder must issue a new revision and owner-approve the promotion.

Usage:
  python scripts/official_p0_option_order_review_bundle.py --output /tmp/p0-review.zip
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import zipfile

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash
from official_p0_option_order_candidate_selftest import (
    RESET_TO_NULL, TRIGGER_MUTABLE_FIELDS, simulate_official_reset, verify
)
from official_p0_option_order_release_rehearsal import (
    ROOT, SHARD_DIR, MANIFEST_PATH, LOCK_PATH, PROOF_PATH,
    OPTIONS, GRADING, TARGET_IDS, sha, encode, grading_digest, validate_base,
)

def build_review_bundle(output: Path) -> None:
    assert verify() == 0
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    assert proof["status"] == "DRAFT_NO_GO"
    assert proof["independent_human_approval"] is False
    assert proof["owner_release_pin"] is False
    assert proof["production_db_written"] is False
    assert proof["changed_question_count"] == 2
    assert proof["official_p0_queue"] == 428
    assert {x["id"] for x in proof["rows"]} == TARGET_IDS
    baseline_manifest, baseline_lock, source_bytes, source_rows, locations = validate_base()
    assert len(source_rows) == 4800
    assert len(source_bytes) == 24

    candidate_rows = {r["id"]: r for r in proof["rows"]}
    projected_lock = copy.deepcopy(baseline_lock)
    projected_manifest = copy.deepcopy(baseline_manifest)
    proposed_shards: dict[str, bytes] = {}
    expected_diffs: dict[str, list[str]] = {}
    projected_rows = {k: copy.deepcopy(v) for k, v in source_rows.items()}
    original_grading = grading_digest(source_rows)
    for item in projected_manifest["shards"]:
        filename = item["file"]
        ids_here = {id_ for id_ in TARGET_IDS if locations[id_] == filename}
        if not ids_here:
            continue
        original = json.loads(source_bytes[filename])
        candidate = copy.deepcopy(original)
        for row in candidate["questions"]:
            if row["id"] not in ids_here:
                continue
            ident = row["id"]
            evidence = candidate_rows[ident]
            before = copy.deepcopy(row)
            assert [row[key] for key in OPTIONS] == evidence["old_options"]
            for option, value in zip(OPTIONS, evidence["proposed_options"]):
                row[option] = value
            # The production BEFORE UPDATE trigger resets enrichment to
            # pending. This simulation is not a production-side UPDATE.
            staged = simulate_official_reset(row)
            row.clear()
            row.update(staged)
            allowed = set(evidence["changed_fields"]) | TRIGGER_MUTABLE_FIELDS
            actual_changes = {key for key in row if row[key] != before.get(key)}
            assert actual_changes <= allowed
            assert actual_changes & set(OPTIONS) == set(evidence["changed_fields"])
            assert row["analysis_status"] == "pending"
            assert all(row[k] is None for k in RESET_TO_NULL if k in row)
            assert all(row.get(k) == before.get(k) for k in GRADING)
            assert row["source_url"] == before["source_url"]
            assert row["source_exam_code"] == before["source_exam_code"]
            projected_rows[ident] = copy.deepcopy(row)
            expected_diffs[ident] = sorted(actual_changes)
            projected_lock["mcq"][ident] = row_hash(canonical_row(row, MCQ_FIELDS))
            assert projected_lock["mcq"][ident] != baseline_lock["mcq"][ident]
        raw = encode(candidate)
        assert raw != source_bytes[filename]
        assert len(candidate["questions"]) == 200
        item["bytes"] = len(raw)
        item["sha256"] = sha(raw)
        proposed_shards[filename] = raw

        # Real rollback payload has the original exact bytes. Check local
        # inverse projection before packaging.
        for row in candidate["questions"]:
            if row["id"] in ids_here:
                ident = row["id"]
                row.clear()
                row.update(copy.deepcopy(source_rows[ident]))
        assert encode(candidate) == source_bytes[filename]
        assert candidate == original

    assert set(proposed_shards) == {"104-2.json", "107-1.json"}
    assert set(expected_diffs) == TARGET_IDS
    assert len(projected_rows) == 4800
    assert sum(source_rows[k] != projected_rows[k] for k in source_rows) == 2
    assert grading_digest(projected_rows) == original_grading
    assert all(projected_rows[k] == source_rows[k] for k in source_rows if k not in TARGET_IDS)
    assert sum(projected_lock["mcq"][id_] != baseline_lock["mcq"][id_]
               for id_ in baseline_lock["mcq"]) == 2
    assert projected_lock["essays"] == baseline_lock["essays"]
    assert len(projected_lock["essays"]) == 240
    assert len(projected_lock["mcq"]) == 4800

    projected_manifest["total_uncompressed_bytes"] = sum(x["bytes"] for x in projected_manifest["shards"])
    assert projected_manifest["total_questions"] == 4800
    assert projected_manifest["shard_count"] == 24
    assert projected_manifest["dataset_revision"] == baseline_manifest["dataset_revision"]
    assert projected_manifest["generated_at"] == baseline_manifest["generated_at"]
    # Revision/generation metadata are purposefully NOT finalized. These files
    # cannot be treated as a deployable public manifest.
    assert sum(x != y for x,y in zip(projected_manifest["shards"],baseline_manifest["shards"])) == 2
    meta = {
        "status":"HOLD_NO_RELEASE",
        "purpose":"Evidence-only isolated exact-shard option-correction review bundle",
        "baseline_main_sha":proof["baseline_main_sha"],
        "official_p0_queue_unresolved":428,
        "human_approved":False,
        "owner_release_pin":False,
        "production_writes":False,
        "deployment_performed":False,
        "not_deployable_reason":"Real release builder must issue fresh manifest dataset_revision/generated_at, obtain independent PDF signoff, pin main, provide production rollback, and synchronize DB/CDN/lock.",
        "total_questions":4800,"unchanged_questions":4798,"total_shards":24,
        "shards_changed":sorted(proposed_shards),
        "changed_questions":sorted(TARGET_IDS),
        "changed_fields_including_trigger_effects":expected_diffs,
        "official_answer_grading_sha256_before":original_grading,
        "official_answer_grading_sha256_after":grading_digest(projected_rows),
        "unmodified_essays":240,
        "original_shard_sha256":{n:sha(source_bytes[n]) for n in sorted(proposed_shards)},
        "proposed_shard_sha256":{n:sha(proposed_shards[n]) for n in sorted(proposed_shards)},
        "rollback_bytes_verified":True,
    }
    payload: dict[str,bytes] = {
        "REVIEW_ONLY_NO_RELEASE.json":encode(meta),
        "evidence/official_p0_option_order_candidate.json":encode(proof),
        "projected/manifest_NOT_PUBLISH.json":encode(projected_manifest),
        "projected/official_exam_readonly_lock_NOT_PUBLISH.json":encode(projected_lock),
        "rollback/manifest_original.json":MANIFEST_PATH.read_bytes(),
        "rollback/official_exam_readonly_lock_original.json":LOCK_PATH.read_bytes(),
    }
    for filename, raw in sorted(proposed_shards.items()):
        payload[f"projected/shards/{filename}"] = raw
        payload[f"rollback/shards/{filename}"] = source_bytes[filename]
    assert len(payload) == 10
    output = output.resolve()
    assert not str(output).startswith(str(ROOT / "cdn"))
    assert not str(output).startswith(str(ROOT / "data"))
    assert not output.exists(), "Never overwrite review bundles"
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name,raw)
    with zipfile.ZipFile(output) as archive:
        assert sorted(archive.namelist())==sorted(payload)
        for name,expected in payload.items():
            assert archive.read(name)==expected, ("archive mismatch",name)
    print(json.dumps({"verdict":"PASS_REVIEW_BUNDLE_NOT_DEPLOYABLE",
                      "archive_sha256":sha(output.read_bytes()),
                      "files":len(payload),"changed_shards":sorted(proposed_shards),
                      "changed_questions":sorted(TARGET_IDS),"unchanged_mcq":4798,
                      "grading_sha256":original_grading,"rollback_bytes_exact":True,
                      "published":False,"production_writes":False},
                     ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    build_review_bundle(args.output)
