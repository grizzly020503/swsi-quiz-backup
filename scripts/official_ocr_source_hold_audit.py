#!/usr/bin/env python3
"""Read-only live source HOLD: three known PDF-proven 104-1 Direct Service OCR defects.

Does not approve the source, change the Official Core, mark AI ready, or deploy.
The prior original MOEX PDF SHA-256 evidence is pinned in the reviewed audit.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/official_104_1_direct_service_three_ocr_candidate_20261031.json"
SHARD = ROOT / "cdn/question-shards/104-1.json"
IDS = frozenset(("DS-104-1-22", "DS-104-1-27", "DS-104-1-29"))
TEXT = ("question", "opt_a", "opt_b", "opt_c", "opt_d")
PDF_SHA = "979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc"


def classify(rows: list[dict], proof: dict) -> dict:
    if (proof.get("release_approved") is not False
            or proof.get("independent_human_approval") is not False):
        raise ValueError("unapproved original-PDF OCR release")
    source = proof.get("original_source_verification") or {}
    if (source.get("exact_byte_sha256") != PDF_SHA
            or proof.get("original_pdf_sha256_expected_from_pinned_registry") != PDF_SHA
            or source.get("matched_proposed_text_fields") != 15
            or source.get("independent_human_approval") is not False):
        raise ValueError("original MOEX source evidence not trustworthy")
    proposals = proof.get("proposed_changes")
    if not isinstance(proposals, list) or len(proposals) != 3 or {
            p.get("id") for p in proposals} != IDS:
        raise ValueError("missing or duplicate original-PDF candidate")
    if not isinstance(rows, list) or len(rows) != 3 or {
            r.get("id") for r in rows} != IDS:
        raise ValueError("must inspect exactly three official MCQ IDs")
    mapping = {r["id"]: r for r in rows}
    if len(mapping) != 3:
        raise ValueError("duplicate official MCQ ID")
    details = []
    for p in sorted(proposals, key=lambda p: p["id"]):
        row = mapping[p["id"]]
        for key, value in (
                ("answer", p["official_answer_unchanged"]),
                ("accepted_answers", p["accepted_answers_unchanged"]),
                ("grading_mode", p["grading_mode_unchanged"]),
                ("source_exam_code", p["source_exam_code"])):
            if row.get(key) != value:
                raise ValueError("official grading/source identity drift: " + p["id"])
        if row.get("analysis_status") not in ("ready", "review", "pending", "analyzing"):
            raise ValueError("unexpected AI analysis status")
        before, after = p["preimage_fields"], p["proposed_fields"]
        if set(before) != set(TEXT) or set(after) != set(TEXT):
            raise ValueError("incomplete original PDF text proof")
        old = [name for name in TEXT if before[name] != after[name]
               and row.get(name) == before[name]]
        proposed = [name for name in TEXT if before[name] != after[name]
                    and row.get(name) == after[name]]
        unknown = [name for name in TEXT if row.get(name) not in
                   (before[name], after[name])]
        if unknown or len(old) + len(proposed) != sum(
                before[name] != after[name] for name in TEXT):
            raise ValueError("unreviewed official OCR text drift: " + p["id"])
        if not old:
            raise ValueError("MOEX OCR correction appeared without human release approval: " + p["id"])
        details.append({
            "id": p["id"], "analysis_status": row["analysis_status"],
            "precorrection_fields": old, "candidate_fields_present": proposed,
            "ready_despite_known_ocr_error": bool(old and row["analysis_status"] == "ready"),
        })
    return {
        "status": "HOLD_KNOWN_MOEX_OCR_DEFECTS_NOT_RELEASE_APPROVED",
        "source_sha256": PDF_SHA,
        "questions_checked": len(details),
        "precorrection_text_fields": sum(len(x["precorrection_fields"]) for x in details),
        "ready_with_known_text_errors": sum(x["ready_despite_known_ocr_error"] for x in details),
        "independent_human_approval": False,
        "official_core_changed": False,
        "release_approved": False,
        "records": details,
    }


def local_rows() -> list[dict]:
    rows = json.loads(SHARD.read_text(encoding="utf-8"))["questions"]
    return [r for r in rows if r.get("id") in IDS]


def live_rows() -> list[dict]:
    """One bounded public-anon SELECT by ID, no retries, no service-role."""
    import requests
    from build_question_shards import frontend_config

    base, key = frontend_config()
    cols = ("id", *TEXT, "answer", "accepted_answers",
            "grading_mode", "source_exam_code", "analysis_status")
    response = requests.get(
        base + "/rest/v1/questions",
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Accept": "application/json", "User-Agent": "SWSI-PDF-OCR-Hold-GET/1.0"},
        params={"select": ",".join(cols),
                "id": "in.(" + ",".join(sorted(IDS)) + ")",
                "order": "id.asc", "limit": "3"},
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("malformed public Supabase OCR rows")
    return rows


def synthetic_selftest(proof: dict) -> None:
    base = local_rows()
    result = classify(base, proof)
    assert result["questions_checked"] == 3
    assert result["precorrection_text_fields"] == 12, result
    assert result["ready_with_known_text_errors"] == 2, result
    def must_fail(rows: list[dict], p: dict, message: str) -> None:
        try:
            classify(rows, p)
        except ValueError as error:
            assert message in str(error), str(error)
        else:
            raise AssertionError("unsafe OCR mutation accepted: " + message)
    for field, value, msg in (
            ("answer", "D", "grading/source identity"),
            ("source_exam_code", "115100", "grading/source identity"),
            ("question", "unverified text", "unreviewed official OCR text"),
            ("analysis_status", "official_human_verified", "unexpected AI")):
        bad = copy.deepcopy(base)
        bad[0][field] = value
        must_fail(bad, proof, msg)
    must_fail(base[:2], proof, "exactly three")
    bad = copy.deepcopy(proof)
    bad["independent_human_approval"] = True
    must_fail(base, bad, "unapproved original-PDF")
    bad = copy.deepcopy(proof)
    bad["original_source_verification"]["exact_byte_sha256"] = "0" * 64
    must_fail(base, bad, "source evidence")
    bad = copy.deepcopy(base)
    bad[0]["question"] = next(p for p in proof["proposed_changes"]
                               if p["id"] == bad[0]["id"])["proposed_fields"]["question"]
    # Partial source text remains held, but can never be mislabeled approved.
    assert classify(bad, proof)["release_approved"] is False
    print("MOEX OCR HOLD SELFTEST OK: 3 known source discrepancies, 2 ready; 7 fail-closed negatives")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    proof = json.loads(AUDIT.read_text(encoding="utf-8"))
    if args.selftest:
        synthetic_selftest(proof)
        return 0
    result = classify(live_rows() if args.live else local_rows(), proof)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0  # Known defects explicitly HOLD; unexpected source drift FAILS.


if __name__ == "__main__":
    raise SystemExit(main())
