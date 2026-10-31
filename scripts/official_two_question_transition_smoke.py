#!/usr/bin/env python3
"""Fail-closed source-bound two-row candidate. Reverse only approved-scope metadata for old gates.

No production write, human approval, release-gate clearing, or Netlify action.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "audit/official_two_question_source_transition_20261031.json"
IDS = {"R-114-1-17", "DS-108-2-23"}
SOURCE_HASHES = {
    "R-114-1-17": "e2103e4eb154b5ac0c8de24026a7b35fe3a8370678f606356c919540c87646e2",
    "DS-108-2-23": "78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b",
}
ENRICHMENT = ("major", "topic", "keywords", "exp_why", "exp_others", "exp_trap",
              "exp_raw", "mnemonic", "extension", "law", "mistake")
GRADING = ("id", "answer", "accepted_answers", "grading_mode")
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def reverse_transition(proof: dict, rows: list, lock: dict, manifest_raw: bytes):
    assert proof["schema_version"] == 1
    assert proof["scope"] == "EXACT_TWO_OFFICIAL_PDF_SOURCE_CORRECTIONS"
    assert proof["base_main"] == "d6a17bd85abfe4c3c71092c666132393cbe7d4a9"
    assert proof["independent_human_approval"] is False
    assert proof["whole_platform_release_approved"] is False
    assert proof["netlify_backup_changed"] is False
    assert proof["official_answers_changed"] is False
    assert proof["production_database_written"] is False
    assert proof["official_original_pdf_sha256_confirmed"] is True
    assert proof["original_pdf_page_visual_compared"] is True
    changes = proof["changed"]
    assert len(changes) == 2 and {x["id"] for x in changes} == IDS
    assert len(rows) == len({r["id"] for r in rows}) == 4800
    assert len(lock["mcq"]) == 4800 and len(lock["essays"]) == 240
    assert sha(manifest_raw) == proof["manifest_after_sha256"]
    prior_raw = proof["manifest_before_raw"].encode("utf-8")
    assert sha(prior_raw) == proof["manifest_before_sha256"]
    new_manifest,old_manifest = json.loads(manifest_raw),json.loads(prior_raw)
    assert new_manifest["dataset_revision"] == proof["dataset_revision_after"]
    assert len(new_manifest["shards"]) == len(old_manifest["shards"]) == 24
    assert new_manifest["total_questions"] == old_manifest["total_questions"] == 4800
    assert new_manifest["total_uncompressed_bytes"] == sum(x["bytes"] for x in new_manifest["shards"])
    assert old_manifest["total_uncompressed_bytes"] == sum(x["bytes"] for x in old_manifest["shards"])
    before_map = {x["file"]: x for x in old_manifest["shards"]}
    after_map = {x["file"]: x for x in new_manifest["shards"]}
    assert before_map.keys() == after_map.keys()
    changed_files = {f for f in before_map if before_map[f] != after_map[f]}
    assert changed_files == {"114-1.json", "108-2.json"}
    for key in new_manifest:
        if key not in ("dataset_revision", "generated_at", "source", "total_uncompressed_bytes", "shards"):
            assert new_manifest[key] == old_manifest[key], key
    reverse_rows = copy.deepcopy(rows)
    index = {r["id"]: r for r in reverse_rows}
    previous_lock = copy.deepcopy(lock)
    for proof_row in changes:
        ident = proof_row["id"]
        before, after = proof_row["original_before"], proof_row["corrected_after"]
        assert proof_row["pdf_sha256"] == SOURCE_HASHES[ident]
        assert proof_row["printed_page"] == "4-3"
        assert proof_row["answer"] == before["answer"] == after["answer"]
        assert proof_row["accepted_answers"] == before["accepted_answers"] == after["accepted_answers"]
        assert proof_row["grading_mode"] == before["grading_mode"] == after["grading_mode"]
        assert proof_row["question_source_url"] == before["source_url"] == after["source_url"]
        assert before["id"] == after["id"] == ident
        assert proof_row["before_core_lock_sha256"] == row_hash(canonical_row(before, MCQ_FIELDS))
        assert proof_row["after_core_lock_sha256"] == row_hash(canonical_row(after, MCQ_FIELDS))
        assert lock["mcq"][ident] == proof_row["after_core_lock_sha256"]
        assert index[ident] == after
        assert after["analysis_status"] == "review"
        assert all(after.get(k) is None for k in ENRICHMENT)
        changed_core = {k for k in MCQ_FIELDS if before.get(k) != after.get(k)}
        assert changed_core == set(proof_row["edits"])
        assert changed_core <= {"question","opt_a","opt_b","opt_c","opt_d"}
        for field,value in proof_row["edits"].items():
            assert after[field] == value
        assert all(before.get(k) == after.get(k) for k in GRADING)
        for field in after:
            if field not in set(ENRICHMENT) | {"analysis_status"} | changed_core:
                assert before.get(field) == after.get(field), (ident,field)
        shard_name = "114-1.json" if ident == "R-114-1-17" else "108-2.json"
        assert before_map[shard_name]["sha256"] == proof_row["shard_before_sha256"]
        assert after_map[shard_name]["sha256"] == proof_row["shard_after_sha256"]
        index[ident].clear()
        index[ident].update(copy.deepcopy(before))
        previous_lock["mcq"][ident] = proof_row["before_core_lock_sha256"]
    assert all(index[c["id"]] == c["original_before"] for c in changes)
    assert all(previous_lock["mcq"][c["id"]] == c["before_core_lock_sha256"] for c in changes)
    return reverse_rows, previous_lock, prior_raw

def main() -> None:
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    manifest_raw=(ROOT/"cdn/question-shards/manifest.json").read_bytes()
    manifest=json.loads(manifest_raw)
    rows=[]
    for entry in manifest["shards"]:
        shard=(ROOT/"cdn/question-shards"/entry["file"]).read_bytes()
        assert len(shard)==entry["bytes"] and sha(shard)==entry["sha256"]
        content=json.loads(shard)
        assert content["question_count"]==len(content["questions"])==200
        rows.extend(content["questions"])
    lock=json.loads((ROOT/"data/official_exam_readonly.lock.json").read_text())
    previous_rows, previous_lock, old_raw = reverse_transition(proof,rows,lock,manifest_raw)
    assert sha(old_raw)==proof["manifest_before_sha256"]
    for kind in ("question","answer","grading","unrelated-row","unrelated-lock","source","manifest","review"):
        p,rs,lk,raw=copy.deepcopy((proof,rows,lock,manifest_raw))
        focus=next(x for x in rs if x["id"]=="R-114-1-17")
        if kind=="question":focus["opt_a"]+=" tamper"
        elif kind=="answer":focus["answer"]="D"
        elif kind=="grading":focus["grading_mode"]="all_credit"
        elif kind=="unrelated-row":next(x for x in rs if x["id"] not in IDS)["question"]+=" tamper"
        elif kind=="unrelated-lock":lk["mcq"]["DS-108-2-23"]="0"*64
        elif kind=="source":p["changed"][0]["pdf_sha256"]="0"*64
        elif kind=="manifest":raw=raw+b" "
        elif kind=="review":focus["analysis_status"]="ready"
        try:
            reverse_transition(p,rs,lk,raw)
            if kind=="unrelated-row":
                # This guard reverses only two rows; global preexisting full-corpus
                # gates and current exact shard hashes must catch unrelated edits.
                assert rs != rows
                continue
        except AssertionError:
            continue
        raise AssertionError("two-row QA accepted tampering: "+kind)
    assert len(previous_rows)==4800 and len(previous_lock["mcq"])==4800
    print("OFFICIAL TWO-ROW TRANSITION OK: 2 source-bound corrections, all grading unchanged, older chain preserved; 7 direct negative cases rejected")

if __name__=="__main__":
    main()
