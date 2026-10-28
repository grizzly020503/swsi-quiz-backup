#!/usr/bin/env python3
"""Read-only official 105-2 & 107-2 shared-context integration integrity check."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "cdn/question-shards"
MANIFEST = SHARDS / "manifest.json"
LOCK = ROOT / "data/official_exam_readonly.lock.json"
PROOF = ROOT / "audit/official_shared_context_13row_integration_20261028.json"
FIELDS = ("id", "subject", "year", "round", "qno", "question", "opt_a", "opt_b", "opt_c", "opt_d")

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def core_sha(row):
    raw = json.dumps({k: row.get(k) for k in FIELDS}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha(raw.encode("utf-8"))

def main():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    l = json.loads(LOCK.read_text(encoding="utf-8"))
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    assert sha(MANIFEST.read_bytes()) == proof["candidate"]["manifest_sha256"]
    assert sha(LOCK.read_bytes()) == proof["candidate"]["lock_sha256"]
    assert m["total_questions"] == 4800 and len(m["shards"]) == 24
    assert m["total_uncompressed_bytes"] == sum(e["bytes"] for e in m["shards"])
    assert len(l["mcq"]) == 4800
    questions = {}
    for e in m["shards"]:
        source = SHARDS / e["file"]
        raw = source.read_bytes()
        assert len(raw) == e["bytes"] and sha(raw) == e["sha256"], e["file"]
        payload = json.loads(raw)
        assert len(payload["questions"]) == e["question_count"], e["file"]
        for row in payload["questions"]:
            ident = row["id"]
            assert ident not in questions, ident
            assert core_sha(row) == l["mcq"][ident], ident
            questions[ident] = row
    assert len(questions) == 4800 and len(proof["changed_rows"]) == 13
    assert len(set(q["id"] for q in proof["changed_rows"])) == 13
    assert all(q["answer_unchanged"] and q["grading_unchanged"] for q in proof["changed_rows"])
    assert questions["R-105-2-12"]["opt_d"] == "Chatili, D., Mary, E. K., Ching, M. L., and Lee, S. S."
    assert questions["R-105-2-20"]["opt_d"] == "樣本數經常會不足"
    assert questions["R-107-2-04"]["opt_d"] == "沒有箭頭的線條表示兩端的變項沒有關係"
    for nums, prefix in (([13,14,15,16], "R-105-2-"), ([21,22], "R-105-2-"), ([5,6,7,8], "R-107-2-")):
        for num in nums:
            q = questions[prefix + str(num).zfill(2)]
            assert q["question"].startswith("情況：") and "\n\n" in q["question"], q["id"]
    assert proof["status"] == "DRAFT_INTEGRATED_QA_NO_GO"
    assert proof["controls"]["production_write"] is False
    assert proof["controls"]["netlify_backup_change"] is False
    print("OFFICIAL SHARED CONTEXT INTEGRATION PASS: 4800 hashes, 24 shards, 13 source-backed rows")

if __name__ == "__main__":
    main()
