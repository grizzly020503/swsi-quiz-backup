#!/usr/bin/env python3
"""No-network regression for MOEX 105-2 and 107-2 combined source-context candidate."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ("id", "subject", "year", "round", "qno", "question", "opt_a", "opt_b", "opt_c", "opt_d")

def read(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf8"))

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def core_sha(q):
    return sha(json.dumps({key: q.get(key) for key in CORE},
              sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf8"))

def run():
    lock=read("data/official_exam_readonly.lock.json")
    manifest=read("cdn/question-shards/manifest.json")
    summary=read("audit/official_105_107_shared_context_integration_20261028.json")
    assert len(lock["mcq"])==4800 and len(lock["essays"])==240
    assert len(summary["changed_mcq_ids"])==13
    assert sum(shard["bytes"] for shard in manifest["shards"])==manifest["total_uncompressed_bytes"]
    for exam,count in (("105-2",8),("107-2",5)):
        rel="cdn/question-shards/"+exam+".json"
        raw=(ROOT / rel).read_bytes()
        rows=read(rel)["questions"]
        info=next(e for e in manifest["shards"] if e["file"]==exam+".json")
        assert len(raw)==info["bytes"] and sha(raw)==info["sha256"]
        assert len(rows)==200
        byid={x["id"]:x for x in rows}
        assert len(byid)==200
        for r in rows:
            assert core_sha(r)==lock["mcq"][r["id"]],r["id"]
        audit=read("audit/official_"+exam.replace("-", "_")+"_shared_context_20261028.json")
        assert len(audit["changes"])==count
        for c in audit["changes"]:
            row=byid[c["id"]]
            fields=c.get("official_core_fields") or c.get("fields")
            assert isinstance(fields,dict)
            for f,d in fields.items():
                assert row[f]==d["after"] != d["before"]
            assert row["answer"]==c["answer"]
            assert row.get("accepted_answers")==c["accepted_answers"]
            assert row["grading_mode"]==c["grading_mode"]
    assert summary["release_approved"] is False
    assert summary["production_writes"] is False
    assert summary["netlify_backup_changes"] is False
    print("MOEX 105+107 integrated 13-row candidate: PASS, locked source+manifest+grading")

if __name__=="__main__":
    run()
