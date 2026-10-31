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
import tempfile
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



def adversarial_selftest(staged_root: Path) -> None:
    """Demand that intentional mutations in the staged successor fail closed."""
    paths = [
        "cdn/question-shards/104-1.json",
        "cdn/question-shards/manifest.json",
        "data/official_exam_readonly.lock.json",
    ]
    original = {p: (staged_root / p).read_bytes() for p in paths}
    changes = [
        ("target question text", "shard", "DS-104-1-22", "question"),
        ("unrelated question text", "shard", "DS-104-1-01", "opt_a"),
        ("official grading", "shard", "DS-104-1-27", "answer"),
        ("stale explanation retained", "shard", "DS-104-1-22", "exp_why"),
        ("review status faked ready", "shard", "DS-104-1-29", "analysis_status"),
        ("manifest revision", "manifest", "", "dataset_revision"),
        ("manifest unrelated shard", "manifest", "104-2.json", "sha256"),
        ("manifest forged publication", "manifest", "", "source"),
        ("official target lock", "lock", "DS-104-1-22", ""),
        ("official other lock", "lock", "DS-104-1-01", ""),
    ]
    for label, category, item_id, field in changes:
        with tempfile.TemporaryDirectory(prefix="swsi-successor-tamper-") as directory:
            tmp = Path(directory)
            for path, data in original.items():
                f = tmp / path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(data)
            if category == "shard":
                file = tmp / paths[0]
                obj = json.loads(file.read_bytes())
                target = next((r for r in obj["questions"] if r["id"] == item_id), None)
                must(target is not None, "selftest target unavailable " + item_id)
                if field == "analysis_status":
                    target[field] = "ready"
                elif field == "answer":
                    target[field] = "D" if target[field] != "D" else "A"
                else:
                    target[field] = str(target.get(field) or "") + " TAMPER"
                file.write_bytes(stable(obj))
                # Recompute all plausible manifest checksums, so the test
                # cannot pass only because of a stale digest.
                mf = tmp / paths[1]
                m = json.loads(mf.read_bytes())
                shard = next(x for x in m["shards"] if x["file"] == "104-1.json")
                old_bytes = shard["bytes"]
                shard["bytes"] = len(file.read_bytes())
                shard["sha256"] = sha(file.read_bytes())
                m["total_uncompressed_bytes"] += shard["bytes"] - old_bytes
                m["dataset_revision"] = sha("\n".join(
                    f"{x['file']}:{x['sha256']}" for x in m["shards"]
                ).encode("utf-8"))[:20]
                mf.write_bytes(stable(m))
                if item_id in EXPECTED_CHANGED:
                    lf = tmp / paths[2]
                    l = json.loads(lf.read_bytes())
                    from official_exam_readonly_guard import row_hash, canonical_row, MCQ_FIELDS
                    l["mcq"][item_id] = row_hash(canonical_row(target, MCQ_FIELDS))
                    lf.write_text(json.dumps(l, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
            elif category == "manifest":
                file = tmp / paths[1]
                obj = json.loads(file.read_bytes())
                if item_id:
                    entry = next(x for x in obj["shards"] if x["file"] == item_id)
                    entry[field] = "0" * 64
                else:
                    obj[field] = "UNAUTHORIZED" if field == "source" else "0" * 20
                file.write_bytes(stable(obj))
            else:
                file = tmp / paths[2]
                obj = json.loads(file.read_bytes())
                obj["mcq"][item_id] = "0" * 64
                file.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            try:
                verify(tmp)
            except (AssertionError, ValueError, KeyError, TypeError):
                continue
            raise AssertionError("SUCCESSOR NEGATIVE CHECK DID NOT FAIL: " + label)
    print("SUCCESSOR ADVERSARIAL SELFTEST PASS: 10/10 unauthorized successor mutations rejected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--adversarial-selftest", action="store_true")
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    dest = args.out.resolve()
    must(dest != ROOT and ROOT not in dest.parents, "cannot write tracked files")
    must(not dest.exists(), "destination must not preexist")
    must(candidate != ROOT and ROOT not in candidate.parents, "must inspect external staged tree")
    originals, evidence = verify(candidate)
    if args.adversarial_selftest:
        adversarial_selftest(candidate)
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
