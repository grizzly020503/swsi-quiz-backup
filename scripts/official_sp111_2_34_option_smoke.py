#!/usr/bin/env python3
"""Fail-closed, offline review of one official PDF-backed option-boundary correction.

Proof is evidence of candidate changes, NOT permission to merge/deploy.
"""
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "audit/official_sp111_2_34_option_boundary_20261028.json"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def check():
    p = json.loads(PROOF.read_text(encoding="utf-8"))
    assert p["status"] == "DRAFT_REVIEW_ONLY_NO_PRODUCTION_WRITES"
    assert p["review_required"] is True and p["human_approval"] is False
    assert p["production_written"] is False and p["release_approved"] is False
    assert p["source_pdf_sha256"] == "9a4afe4df13a7b88582efa0bb3950ccdb3780ec5c7e3380afabe8b0e8f2e3a0d"
    assert p["source_pdf_page"] == 5 and p["answer_pdf_sha256"] == "56913562ef043ea9fe22bb011c3d710ced08192896ea0e6cc94033c694b8ab2b"
    assert p["original_shard_blob_sha"] == "3a6fe35845f504ffbbcd25595987185f8bce3c90"
    before, after = p["before"], p["after"]
    assert before["id"] == after["id"] == "SP111-2-34"
    assert {k for k in before if before[k] != after[k] and k in ("question","opt_a","opt_b","opt_c","opt_d")} == set(p["changed_official_fields"]) == {"opt_a","opt_b","opt_c","opt_d"}
    assert all(before[k] == after[k] for k in ("id","subject","year","round","qno","question","answer","accepted_answers","grading_mode","source_exam_code","source_url"))
    assert after["answer"] == p["official_answer"] == "C"
    assert after["grading_mode"] == "standard" and after["accepted_answers"] is None
    assert [after["opt_" + x] for x in "abcd"] == ["1 至 3 個月", "2 至 4 個月", "3 至 6 個月", "4 至 6 個月"]
    assert after["analysis_status"] == "review"
    for key in ("major","topic","keywords","exp_why","exp_others","exp_trap","exp_raw","mnemonic","extension","law","mistake"):
        assert after[key] is None, "stale AI-derived explanation survived"
    assert row_hash(canonical_row(before, MCQ_FIELDS)) == p["before_lock_sha256"] == "fd9b1712d88c89537a0c03b07e40fc2aa6d64f479afba1f53cbfc66ae7d3f3b9"
    assert row_hash(canonical_row(after, MCQ_FIELDS)) == p["after_lock_sha256"] == "fd5542b3d9c391f96bb9345855fc7002c6ab40c9279a7a732ec4fa477df91f5d"
    raw = (ROOT / "cdn/question-shards/111-2.json").read_bytes()
    assert sha(raw) == p["after_shard_sha256"]
    parsed = json.loads(raw)
    assert len(parsed["questions"]) == 200 and parsed["question_count"] == 200
    items = [x for x in parsed["questions"] if x["id"] != p["id"]]
    assert len(items) == p["untouched_199_row_count"] == 199
    assert sha(json.dumps(items,ensure_ascii=False,separators=(",",":")).encode("utf-8")) == p["untouched_199_json_sha256"]
    assert next(x for x in parsed["questions"] if x["id"] == p["id"]) == after
    locked = json.loads((ROOT / "data/official_exam_readonly.lock.json").read_text(encoding="utf-8"))
    assert locked["mcq"][p["id"]] == p["after_lock_sha256"]
    manifest_raw=(ROOT / "cdn/question-shards/manifest.json").read_bytes()
    assert sha(manifest_raw) == p["after_manifest_sha256"]
    manifest=json.loads(manifest_raw)
    target=next(x for x in manifest["shards"] if x["file"]=="111-2.json")
    assert target["bytes"] == len(raw) and target["sha256"] == sha(raw)
    assert manifest["total_uncompressed_bytes"] == sum(x["bytes"] for x in manifest["shards"])
    revision=sha("\\n".join(x["file"]+":"+x["sha256"] for x in manifest["shards"]).encode("utf-8"))[:20]
    assert manifest["dataset_revision"] == revision
    print("OFFICIAL SP111-2-34 CANDIDATE OK: four option boundaries restored; 199 peer rows and official C grading preserved; release remains HOLD")

if __name__ == "__main__":
    check()
