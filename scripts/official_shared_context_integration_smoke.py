#!/usr/bin/env python3
"""Fail-closed, read-only MOEX 105-2 + 107-2 shared-context integration QA.

Validate all 24 retained MCQ shards / 4,800 exact Official Core row locks,
then verify the 13 source-PDF-backed corrections from both original proof
records. No network, write, deployment or official answer modification.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "cdn/question-shards"
PROOFS = (
    (
        "105-2",
        ROOT / "audit/official_105_2_shared_context_20261028.json",
        {"R-105-2-12", "R-105-2-13", "R-105-2-14", "R-105-2-15",
         "R-105-2-16", "R-105-2-20", "R-105-2-21", "R-105-2-22"},
        "6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836",
    ),
    (
        "107-2",
        ROOT / "audit/official_107_2_shared_context_20261028.json",
        {"R-107-2-04", "R-107-2-05", "R-107-2-06",
         "R-107-2-07", "R-107-2-08"},
        "65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d",
    ),
)
CORE = ("id", "subject", "year", "round", "qno", "question",
        "opt_a", "opt_b", "opt_c", "opt_d")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(row):
    raw = json.dumps({key: row.get(key) for key in CORE}, sort_keys=True,
                     ensure_ascii=False, separators=(",", ":"))
    return sha(raw.encode("utf-8"))


def main():
    lock = json.loads((ROOT / "data/official_exam_readonly.lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((SHARDS / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_questions"] == len(lock["mcq"]) == 4800
    assert lock["essay_count"] == len(lock["essays"]) == 240
    assert manifest["shard_count"] == len(manifest["shards"]) == 24
    assert sum(entry["bytes"] for entry in manifest["shards"]) == manifest["total_uncompressed_bytes"] == 7639946

    rows = {}
    checked_shards = set()
    for entry in manifest["shards"]:
        name = entry["file"]
        assert name not in checked_shards and name.endswith(".json"), name
        checked_shards.add(name)
        raw = (SHARDS / name).read_bytes()
        assert sha(raw) == entry["sha256"] and len(raw) == entry["bytes"], name
        part = json.loads(raw)
        assert len(part["questions"]) == part["question_count"] == entry["question_count"] == 200, name
        for row in part["questions"]:
            ident = row["id"]
            assert ident not in rows and ident in lock["mcq"], ident
            assert canonical_hash(row) == lock["mcq"][ident], ident
            rows[ident] = row

    assert len(rows) == 4800 and set(rows) == set(lock["mcq"])
    all_changed_ids = set()
    for part, proof_path, expected_ids, pdf_sha in PROOFS:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        assert proof["source_pdf_sha256"] == pdf_sha
        assert proof["not_approved_for_merge"] is True
        file_name = part + ".json"
        expected_shard_sha = next(s["sha256"] for s in manifest["shards"] if s["file"] == file_name)
        assert proof["new_shard_sha256"] == expected_shard_sha
        changes = proof["changes"]
        assert len(changes) == len(expected_ids) and {c["id"] for c in changes} == expected_ids
        assert not (all_changed_ids & expected_ids)
        all_changed_ids.update(expected_ids)
        for change in changes:
            row = rows[change["id"]]
            assert row["subject"] == "社會工作研究方法"
            assert canonical_hash(row) == lock["mcq"][change["id"]] == change["new_lock_sha256"]
            assert change["old_lock_sha256"] != change["new_lock_sha256"]
            for field, mutation in change["fields"].items():
                assert mutation["before"] != mutation["after"] == row[field], (change["id"], field)
            assert row["answer"] == change["answer"]
            assert row.get("accepted_answers") == change["accepted_answers"]
            assert row["grading_mode"] == change["grading_mode"]

    assert len(all_changed_ids) == 13
    for ident in ("R-105-2-12", "R-105-2-20", "R-107-2-04"):
        assert "情況：" not in rows[ident]["opt_d"], ident
    for session, numbers in (("105-2", (13, 14, 15, 16, 21, 22)),
                             ("107-2", (5, 6, 7, 8))):
        for number in numbers:
            ident = f"R-{session}-{number:02d}"
            assert rows[ident]["question"].startswith("情況："), ident

    print("PASS: 13 MOEX official source corrections; 4,800 core locks; 24 shard SHA256/byte checks; 240 essay locks unchanged in scope")
    print("Draft / NO-GO: source-independent human review, original PDF release QA and production parity still required")


if __name__ == "__main__":
    main()
