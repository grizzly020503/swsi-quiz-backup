#!/usr/bin/env python3
"""Stage a NOT-YET-APPROVED three-question Official Core release package.

Runs only against checked-in immutable public files. Never connects to Supabase.
Writes candidate 104-1 shard, updated manifest and Official Core locks solely
to a caller-supplied directory outside the repository. Does NOT publish.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/official_104_1_direct_service_three_ocr_candidate_20261031.json"
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
SHARDS = ROOT / "cdn/question-shards"
LOCK = ROOT / "data/official_exam_readonly.lock.json"
REGISTRY = ROOT / "data/moex_source_subjects.v1.json"
CORE = ("id", "subject", "year", "round", "qno", "question",
        "opt_a", "opt_b", "opt_c", "opt_d")
TEXT = ("question", "opt_a", "opt_b", "opt_c", "opt_d")
ENRICH = ("major", "topic", "keywords", "exp_why", "exp_others",
          "exp_trap", "exp_raw", "mnemonic", "extension", "law", "mistake")
GRADING = ("answer", "accepted_answers", "grading_mode")
IDS = {"DS-104-1-22": "A", "DS-104-1-27": "B", "DS-104-1-29": "D"}
PDF_SHA = "979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError("FAIL CLOSED: " + reason)


def stable(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def core_hash(row: dict) -> str:
    b = json.dumps({field: row.get(field) for field in CORE}, ensure_ascii=False,
                   sort_keys=True, separators=(",", ":")).encode("utf-8")
    return digest(b)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out != ROOT and ROOT not in out.parents, "output must not be inside repository")
    require(not out.exists(), "output directory must not preexist: " + str(out))

    audit = json.loads(AUDIT.read_text("utf-8"))
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    lock = json.loads(LOCK.read_text("utf-8"))
    registry = json.loads(REGISTRY.read_text("utf-8"))
    require(audit["independent_human_approval"] is False
            and audit["release_approved"] is False
            and audit["production_database_written"] is False,
            "this program is for unapproved candidates ONLY")
    require(audit["original_pdf_sha256_reverified_in_this_run"] is True
            and audit["original_pdf_sha256_expected_from_pinned_registry"] == PDF_SHA,
            "source PDF not original-byte verified")
    sources = [p for p in registry["records"] if p["session"] == "104-1"
               and p["subject"] == "社會工作直接服務"]
    require(len(sources) == 1 and sources[0]["pdf_sha256"] == PDF_SHA,
            "official source identity drift")
    require(audit["baseline_dataset_revision"] == manifest["dataset_revision"],
            "manifest release revision drift")
    require(len(manifest["shards"]) == 24 and manifest["total_questions"] == 4800
            and lock["mcq_count"] == 4800 and lock["essay_count"] == 240,
            "historic corpus count drift")
    require(set(audit["affected_ids"]) == set(IDS)
            and len(audit["proposed_changes"]) == 3, "candidate scope drift")

    original_records = {}
    existing_shard_raw = {}
    for meta in manifest["shards"]:
        name = meta["file"]
        require(Path(name).name == name and name.endswith(".json"), "unsafe shard path")
        raw = (SHARDS / name).read_bytes()
        require(len(raw) == meta["bytes"] and digest(raw) == meta["sha256"],
                name + ": baseline physical SHA mismatch")
        payload = json.loads(raw)
        require(len(payload["questions"]) == meta["question_count"] == 200,
                name + ": not 200 rows")
        existing_shard_raw[name] = raw
        for row in payload["questions"]:
            rid = row["id"]
            require(rid not in original_records, "duplicate ID " + rid)
            original_records[rid] = row
    require(len(original_records) == 4800, "invalid full ID count")
    require(set(original_records) == set(lock["mcq"]), "lock ID drift")
    for rid, row in original_records.items():
        require(core_hash(row) == lock["mcq"][rid],
                "frozen official core mismatch before candidate: " + rid)

    file_name = "104-1.json"
    meta = next((x for x in manifest["shards"] if x["file"] == file_name), None)
    require(meta is not None and audit["baseline_shard_sha256"] == meta["sha256"],
            "target shard baseline drift")
    payload = json.loads(existing_shard_raw[file_name])
    current = {r["id"]: r for r in payload["questions"]}
    changed = {}
    for candidate in audit["proposed_changes"]:
        rid = candidate["id"]
        require(rid in IDS and rid in current, "unknown candidate row")
        row = current[rid]
        require(row["subject"] == "社會工作直接服務"
                and row["year"] == "104" and row["round"] == "第一次",
                "source group drift " + rid)
        require(set(candidate["preimage_fields"]) == set(TEXT)
                and set(candidate["proposed_fields"]) == set(TEXT),
                "only official question/options may be changed")
        require(all(row[k] == candidate["preimage_fields"][k] for k in TEXT),
                "wrong current source preimage " + rid)
        require(row["answer"] == IDS[rid] == candidate["official_answer_unchanged"],
                "official grading drift")
        require(tuple(row[k] for k in GRADING) ==
                (candidate["official_answer_unchanged"],
                 candidate["accepted_answers_unchanged"],
                 candidate["grading_mode_unchanged"]), "special grading drift")
        before = copy.deepcopy(row)
        for k, v in candidate["proposed_fields"].items():
            row[k] = v
        for k in ENRICH:
            row[k] = None
        row["analysis_status"] = "review"
        actual_diff = {k for k in row if row[k] != before[k]}
        require(actual_diff <= {*TEXT, *ENRICH, "analysis_status"},
                "unexpected non-text/enrichment field change")
        require(any(row[k] != before[k] for k in TEXT), "empty source correction")
        changed[rid] = {
            "before_core_sha": core_hash(before),
            "after_core_sha": core_hash(row),
            "changed_fields": sorted(actual_diff),
            "status_before": before["analysis_status"],
            "status_after": row["analysis_status"],
            "official_answer": row["answer"],
        }
    require(len(changed) == 3, "not exactly three changes")

    replacement = stable(payload)
    require(digest(replacement) != meta["sha256"], "candidate not modified")
    other_ids = set(original_records) - set(IDS)
    require(len(other_ids) == 4797, "other count drift")
    staged = copy.deepcopy(original_records)
    for row in payload["questions"]:
        staged[row["id"]] = row
    require(all(staged[rid] == original_records[rid] for rid in other_ids),
            "unrelated questions changed")
    require(all(tuple(staged[rid][k] for k in GRADING) ==
                tuple(original_records[rid][k] for k in GRADING)
                for rid in original_records), "any grading tuple changed")
    require(sum(r["analysis_status"] == "review" for r in staged.values()) == 136,
            "unexpected review count after two stale explanations quarantined")

    updated_manifest = copy.deepcopy(manifest)
    target = next(x for x in updated_manifest["shards"] if x["file"] == file_name)
    target["sha256"] = digest(replacement)
    target["bytes"] = len(replacement)
    updated_manifest["total_uncompressed_bytes"] += (len(replacement) - meta["bytes"])
    hashes = [f"{item['file']}:{item['sha256']}" for item in updated_manifest["shards"]]
    updated_manifest["dataset_revision"] = digest("\n".join(hashes).encode())[:20]
    updated_manifest["source"] = "DRAFT NO-GO: human-unapproved official-source correction for DS-104-1-22/27/29"
    updated_manifest["generated_at"] = "2026-10-31T15:00:00Z"
    require(all(a["sha256"] == b["sha256"] and a["bytes"] == b["bytes"]
                for a, b in zip(updated_manifest["shards"], manifest["shards"])
                if a["file"] != file_name),
            "unrelated shard physical metadata changed")

    updated_lock = copy.deepcopy(lock)
    for rid in IDS:
        updated_lock["mcq"][rid] = core_hash(staged[rid])
    require(all(lock["mcq"][rid] == updated_lock["mcq"][rid] for rid in other_ids),
            "unrelated official core hashes changed")
    require(lock["essays"] == updated_lock["essays"], "essay locks changed")
    require({rid for rid in lock["mcq"] if lock["mcq"][rid] != updated_lock["mcq"][rid]} ==
            set(IDS), "wrong lock changes")

    targetdir = out / "cdn/question-shards"
    targetdir.mkdir(parents=True)
    (out / "data").mkdir(parents=True)
    (targetdir / file_name).write_bytes(replacement)
    (targetdir / "manifest.json").write_bytes(stable(updated_manifest))
    (out / "data/official_exam_readonly.lock.json").write_text(
        json.dumps(updated_lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence = {
        "status": "STAGED_ONLY_HUMAN_APPROVAL_FALSE_PRODUCTION_NO_GO",
        "human_approval": False,
        "published": False,
        "official_pdf_sha256": PDF_SHA,
        "base_main_sha": audit["base_main_sha"],
        "before_dataset_revision": manifest["dataset_revision"],
        "staged_dataset_revision": updated_manifest["dataset_revision"],
        "before_shard_sha256": meta["sha256"],
        "staged_shard_sha256": digest(replacement),
        "unaffected_exact_row_count": len(other_ids),
        "grading_unchanged_count": len(staged),
        "changed_official_lock_count": len(changed),
        "essay_lock_count": len(updated_lock["essays"]),
        "staged_review_count": 136,
        "staged_ready_count": 4664,
        "changes": changed,
        "required_before_real_release": [
            "independent human primary source approval",
            "production 37-column preimages revalidation and source release SQL",
            "staged artifacts rederived against latest main and production",
            "all release gates full CI",
            "separate explicit owner merge and production deployment permission",
        ],
    }
    (out / "candidate-evidence.json").write_bytes(
        json.dumps(evidence, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    require(len(list(out.rglob("*"))) == 7,
            "output must be exactly four files and three directories")
    print("STAGED OFFLINE NO-GO: three original-PDF-supported repairs, "
          "4,797 untouched, 4,800 grading tuples unchanged, "
          "three Official Core hashes staged, 136 proposed review / 4664 ready; "
          "NO tracked or production writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
