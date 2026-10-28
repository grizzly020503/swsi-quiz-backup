#!/usr/bin/env python3
"""SWSI official 105-2+107-2 shared-context integrated candidate, read-only smoke."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "cdn/question-shards"
PROOFS = [
    ROOT / "audit/official_105_2_shared_context_20261028.json",
    ROOT / "audit/official_107_2_shared_context_20261028.json",
]
TARGET_IDS = [
    {"R-105-2-12", "R-105-2-13", "R-105-2-14", "R-105-2-15", "R-105-2-16", "R-105-2-20", "R-105-2-21", "R-105-2-22"},
    {"R-107-2-04", "R-107-2-05", "R-107-2-06", "R-107-2-07", "R-107-2-08"},
]
CORE = ("id", "subject", "year", "round", "qno", "question", "opt_a", "opt_b", "opt_c", "opt_d")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical_hash(q):
    return sha(json.dumps({k: q.get(k) for k in CORE}, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))

def main():
    lock = json.loads((ROOT / "data/official_exam_readonly.lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((SHARDS / "manifest.json").read_text(encoding="utf-8"))
    assert len(lock["mcq"]) == manifest["total_questions"] == 4800
    assert manifest["shard_count"] == 24
    assert sum(s["bytes"] for s in manifest["shards"]) == manifest["total_uncompressed_bytes"] == 7639946
    all_changes = set()
    for part, proof_path, expected in zip(("105-2", "107-2"), PROOFS, TARGET_IDS):
        raw = (SHARDS / (part + ".json")).read_bytes()
        source = json.loads(raw)
        entry = next(e for e in manifest["shards"] if e["file"] == part + ".json")
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        assert sha(raw) == entry["sha256"] == proof["new_shard_sha256"]
        assert len(raw) == entry["bytes"]
        assert proof["not_approved_for_merge"] is True
        assert source["question_count"] == len(source["questions"]) == 200
        rows = {r["id"]: r for r in source["questions"]}
        assert len(rows) == 200
        for row in rows.values():
            assert canonical_hash(row) == lock["mcq"][row["id"]]
        changes = proof["changes"]
        assert {c["id"] for c in changes} == expected
        for c in changes:
            q = rows[c["id"]]
            assert lock["mcq"][c["id"]] == c["new_lock_sha256"]
            assert c["old_lock_sha256"] != c["new_lock_sha256"]
            for field, patch in c["fields"].items():
                assert q[field] == patch["after"] != patch["before"]
            assert q["answer"] == c["answer"]
            assert q.get("accepted_answers") == c["accepted_answers"]
            assert q["grading_mode"] == c["grading_mode"]
        all_changes |= expected
        if part == "105-2":
            assert all("情況：" not in rows[x]["opt_d"] for x in ("R-105-2-12", "R-105-2-20"))
            for n in (13,14,15,16,21,22):
                assert rows[f"R-105-2-{n}"]["question"].startswith("情況：")
        else:
            assert "情況：" not in rows["R-107-2-04"]["opt_d"]
            for n in (5,6,7,8):
                assert rows[f"R-107-2-{n:02d}"]["question"].startswith("情況：")
    assert len(all_changes) == 13
    print("PASS: 13 MOEX source corrections, 400 source locks, 24-shard manifest, no grading edits")

if __name__ == "__main__":
    main()
