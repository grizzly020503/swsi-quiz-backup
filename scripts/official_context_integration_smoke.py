#!/usr/bin/env python3
"""Fail-closed regression: source-backed MOEX 105-2 + 107-2 question scenarios."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p): return json.loads((ROOT/p).read_text("utf-8"))
def h(b): return hashlib.sha256(b).hexdigest()
def lockhash(q):
    fs=("id","subject","year","round","qno","question","opt_a","opt_b","opt_c","opt_d")
    return h(json.dumps({k:q.get(k) for k in fs},sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8"))
def main():
    m=load("cdn/question-shards/manifest.json")
    locks=load("data/official_exam_readonly.lock.json")
    proof=load("audit/official_context_integration_20261028.json")
    audits=[load("audit/official_105_2_shared_context_20261028.json"),load("audit/official_107_2_shared_context_20261028.json")]
    expected={x["id"]:x for a in audits for x in a["changes"]}
    assert len(expected)==len(proof["changes"])==13
    assert m["total_questions"]==4800 and len(m["shards"])==24
    assert sum(x["bytes"] for x in m["shards"])==m["total_uncompressed_bytes"]==proof["total_manifest_bytes"]
    seen=set()
    for filename in ("105-2.json","107-2.json"):
        raw=(ROOT/"cdn/question-shards"/filename).read_bytes()
        entry=next(x for x in m["shards"] if x["file"]==filename)
        assert h(raw)==entry["sha256"] and len(raw)==entry["bytes"]
        qs=json.loads(raw)["questions"]
        assert len(qs)==200
        for q in qs:
            assert lockhash(q)==locks["mcq"][q["id"]]
            if q["id"] in expected:
                e=expected[q["id"]]
                assert locks["mcq"][q["id"]]==e["new_lock_sha256"]
                assert q["answer"]==e["answer"]
                assert q.get("accepted_answers")==e["accepted_answers"]
                assert q["grading_mode"]==e["grading_mode"]
                for field,change in e["fields"].items():
                    assert q[field]==change["after"]!=change["before"]
                seen.add(q["id"])
    assert seen==set(expected)
    assert proof["status"]=="DRAFT_NO_GO" and proof["release_approval"] is False
    print("OFFICIAL CONTEXT INTEGRATION PASS: 13 changed rows; 400 official locks; manifest; grades")
if __name__=="__main__": main()
