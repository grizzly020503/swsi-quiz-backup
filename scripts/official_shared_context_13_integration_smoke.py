#!/usr/bin/env python3
"""Read-only regression of 13 original MOEX shared-scenario corrections."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "cdn/question-shards"
FIELDS = ("id", "subject", "year", "round", "qno", "question", "opt_a", "opt_b", "opt_c", "opt_d")

def h(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def rowhash(q: dict) -> str:
    return h(json.dumps({k: q.get(k) for k in FIELDS}, ensure_ascii=False,
                        sort_keys=True, separators=(",", ":")).encode("utf-8"))

def main():
    audit = json.loads((ROOT / "audit/official_shared_context_13_integration_20261028.json").read_text(encoding="utf-8"))
    man = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "data/official_exam_readonly.lock.json").read_text(encoding="utf-8"))
    assert len(lock["mcq"]) == 4800 and len(audit["scope"]["modified_mcq_ids"]) == 13
    assert man["total_questions"] == 4800
    assert sum(x["bytes"] for x in man["shards"]) == man["total_uncompressed_bytes"]
    details = {}
    for entry in man["shards"]:
        source = (DATA / entry["file"]).read_bytes()
        assert h(source) == entry["sha256"] and len(source) == entry["bytes"]
        rows = json.loads(source)["questions"]
        assert len(rows) == entry["question_count"]
        for q in rows:
            assert rowhash(q) == lock["mcq"][q["id"]]
            details[q["id"]] = q
    assert len(details) == 4800
    changed = set()
    for proof_path in ("audit/official_105_2_shared_context_20261028.json", "audit/official_107_2_shared_context_20261028.json"):
        proof = json.loads((ROOT / proof_path).read_text(encoding="utf-8"))
        for change in proof["changes"]:
            ident = change["id"]
            assert ident not in changed
            changed.add(ident)
            row = details[ident]
            for field, delta in change["fields"].items():
                assert row[field] == delta["after"] and delta["before"] != delta["after"]
            assert rowhash(row) == change["new_lock_sha256"]
            assert row["answer"] == change["answer"]
            assert row.get("accepted_answers") == change["accepted_answers"]
            assert row["grading_mode"] == change["grading_mode"]
    assert len(changed) == 13 and changed == set(audit["scope"]["modified_mcq_ids"])
    assert audit["approved_to_merge"] is False and audit["production_mutation"] is False
    print("MOEX 13-QUESTION INTEGRATION PASS: 4800 locks, 24 manifests, 13 exact corrections, grading unchanged")

if __name__ == "__main__":
    main()
