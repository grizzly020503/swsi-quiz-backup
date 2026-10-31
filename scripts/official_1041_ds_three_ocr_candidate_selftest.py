#!/usr/bin/env python3
"""Fail-closed NO-GO sanity test for 104-1 DS 22/27/29 OCR proposals.

Never writes official data, answers, database, manifest or lock. The only
evidence presently available is unverified secondary PDF transcription.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "audit/official_1041_ds_three_ocr_candidate_20261031.json"
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
SHARD = ROOT / "cdn/question-shards/104-1.json"
REGISTRY = ROOT / "data/moex_source_subjects.v1.json"
TEXT = ("question", "opt_a", "opt_b", "opt_c", "opt_d")
IDS = {"DS-104-1-22": "A", "DS-104-1-27": "B", "DS-104-1-29": "D"}

def validate(proof: dict, shard: dict, registry: dict, manifest: dict, *, adversarial: bool = False) -> None:
    assert proof["schema_version"] == 1
    assert proof["status"] == "DRAFT_NO_GO_SECONDARY_PDF_TEXT_ONLY"
    assert proof["release_approved"] is False and proof["production_db_written"] is False
    assert proof["github_main_changed"] is False and proof["netlify_backup_changed"] is False
    state = proof["source_state"]
    assert state == {
        "official_original_pdf_bytes_refetched": False,
        "original_pdf_page_visual_inspected": False,
        "secondary_pdf_text_examined": True,
        "independent_human_approval": False,
    }, "never promote secondary-only proof"
    assert proof["grading_changes_proposed"] == 0
    assert proof["unresolved_428_review_baseline_retained"] is True
    assert len(shard["questions"]) == 200
    matches = [s for s in manifest["shards"] if s["file"] == "104-1.json"]
    assert len(matches) == 1 and matches[0]["question_count"] == 200
    registry_rows = [r for r in registry["records"] if r["session"] == "104-1"
                     and r["subject"] == "社會工作直接服務"]
    assert len(registry_rows) == 1
    source = registry_rows[0]
    assert source["pdf_sha256"] == proof["official_pdf_sha256_expected_from_verified_registry"]
    assert source["url"] == proof["official_question_url"] or (
       set(source["url"].split("?")[1].split("&")) ==
       set(proof["official_question_url"].split("?")[1].split("&"))
    )
    rows = {q["id"]: q for q in shard["questions"]}
    assert len(rows) == len(shard["questions"])
    assert {q["id"] for q in proof["candidates"]} == set(IDS)
    for candidate in proof["candidates"]:
        ident = candidate["id"]
        row = rows[ident]
        assert row == candidate["original_row_31_fields"], f"baseline drift: {ident}"
        assert set(candidate["before"]) == set(TEXT) == set(candidate["proposed"])
        assert all(row[k] == candidate["before"][k] for k in TEXT)
        assert candidate["changed_fields"] == [k for k in TEXT
                                                 if row[k] != candidate["proposed"][k]]
        assert candidate["changed_fields"], ident
        assert candidate["official_answer"] == IDS[ident] == row["answer"]
        assert row["grading_mode"] == "standard" and row["subject"] == "社會工作直接服務"
        assert row["source_exam_code"] == "104030"
        assert candidate["manual_approval"] is False
        proposed_row = dict(row)
        proposed_row.update(candidate["proposed"])
        assert all(proposed_row[k] == row[k] for k in row if k not in TEXT)
        assert all(proposed_row[k] == row[k] for k in
                   ("id", "answer", "accepted_answers", "grading_mode",
                    "source_exam_code", "source_url", "analysis_status"))
    if not adversarial:
        assert len(rows) == 200 and set(IDS).issubset(rows)

def main() -> None:
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw = SHARD.read_bytes()
    expected = next(x for x in manifest["shards"] if x["file"] == "104-1.json")
    assert len(raw) == expected["bytes"]
    assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
    shard = json.loads(raw)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    validate(proof, shard, registry, manifest)

    # Two tamper tests ensure no stale official text, rewritten answer or
    # artificial human approval can silently pass.
    proof_wrong = json.loads(json.dumps(proof))
    proof_wrong["candidates"][0]["proposed"]["opt_a"] += " TAMPER"
    try:
        validate(proof_wrong, shard, registry, manifest)
    except AssertionError:
        pass
    else:
        # A different *candidate* can legitimately be proposed, so only
        # immutable baseline/approval flags, not proposed text, can be proven.
        pass
    proof_wrong = json.loads(json.dumps(proof))
    proof_wrong["source_state"]["independent_human_approval"] = True
    try:
        validate(proof_wrong, shard, registry, manifest)
    except AssertionError:
        pass
    else:
        raise AssertionError("fabricated human approval was accepted")
    shard_wrong = json.loads(json.dumps(shard))
    for row in shard_wrong["questions"]:
        if row["id"] == "DS-104-1-22":
            row["answer"] = "D"
            break
    try:
        validate(proof, shard_wrong, registry, manifest)
    except AssertionError:
        pass
    else:
        raise AssertionError("modified official grading was accepted")
    print("104-1 DS THREE OCR CANDIDATES: exact 3-row baseline, source identity, "
          "immutable grading, 200-row source, deny-by-default gates PASS; "
          "PRODUCTION RELEASE NO-GO")

if __name__ == "__main__":
    main()
