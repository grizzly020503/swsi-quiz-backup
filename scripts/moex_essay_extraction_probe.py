#!/usr/bin/env python3
"""Read-only, SHA-bound diagnostic for MOEX essay PDF segmentation failures.

Diagnostic hints are not official transcript proof and NEVER clear review gates.
Use a local, immutable PDF; this command never downloads or edits Official Core.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
EXACT_FIRST = "甲、申論題部分"
EXACT_LAST = "乙、測驗題部分"
RELAXED_FIRST = re.compile(r"甲\s*、\s*申\s*論\s*題\s*部\s*分")
RELAXED_LAST = re.compile(r"乙\s*、\s*測\s*驗\s*題\s*部\s*分")
EXACT_ESSAY = re.compile(r"(?m)^\s*([一二])、\s*")
# Diagnostic only: NEVER use this broad match to publish/rewrite question text.
RELAXED_ESSAY = re.compile(r"([一二])\s*、")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def locate(text: str, expression: re.Pattern) -> list[dict]:
    return [{"marker": m.group(1), "offset": m.start()} for m in expression.finditer(text)]


def diagnose(text: str, legacy_parser: Callable[[str], list[dict]], *,
             verified_pdf_sha256: str | None = None) -> dict:
    """Show where legacy extraction failed, without inventing recovered text."""
    if not isinstance(text, str):
        raise ValueError("extracted PDF text must be a string")
    first = text.find(EXACT_FIRST)
    last = text.find(EXACT_LAST)
    section = text[first + len(EXACT_FIRST):last] if first >= 0 and last > first else ""
    exact = locate(section, EXACT_ESSAY) if section else []
    relaxed_first = RELAXED_FIRST.search(text)
    relaxed_last = RELAXED_LAST.search(text)
    loose_start = relaxed_first.end() if relaxed_first else -1
    loose_end = relaxed_last.start() if relaxed_last else -1
    loose_section = text[loose_start:loose_end] if loose_start >= 0 and loose_end > loose_start else ""
    loose = locate(loose_section, RELAXED_ESSAY) if loose_section else []
    legacy = legacy_parser(text)
    if not isinstance(legacy, list):
        raise ValueError("legacy parser must return an essay list")
    hints = []
    if first < 0 or last <= first:
        hints.append("exact_section_boundary_missing_or_out_of_order")
    if relaxed_first and relaxed_last and (first < 0 or last <= first):
        hints.append("whitespace_or_linebreak_inside_section_boundary")
    if section and [m["marker"] for m in exact] != ["一", "二"]:
        hints.append("exact_essay_start_markers_not_two_in_order")
    if [m["marker"] for m in loose] == ["一", "二"] and [m["marker"] for m in exact] != ["一", "二"]:
        hints.append("possible_inline_or_spaced_question_markers")
    if len(legacy) != 2:
        hints.append("legacy_parser_did_not_return_two_essays")
    status = ("EXTRACTED_BUT_REQUIRES_PDF_TEXT_REVIEW" if len(legacy) == 2
              else "PARSER_FAILURE_REVIEW_REQUIRED")
    return {
        "schema_version": 1, "status": status,
        "verified_pdf_sha256": verified_pdf_sha256,
        "extracted_text_sha256": sha(text.encode("utf-8")),
        "exact_section_start_found": first >= 0,
        "exact_section_end_found": last >= 0 and last > first,
        "relaxed_section_start_found": relaxed_first is not None,
        "relaxed_section_end_found": relaxed_last is not None,
        "exact_question_markers": exact[:8],
        "diagnostic_only_relaxed_markers": loose[:8],
        "legacy_essay_count": len(legacy),
        "legacy_essay_points": [str(r.get("points")) for r in legacy],
        "suspected_extraction_stages": hints,
        "human_approval": False, "release_approved": False,
        "official_core_modified": False, "production_written": False,
    }


def registry_row(session: str, subject: str, root: Path = ROOT) -> dict:
    doc = json.loads((root / "data/moex_source_subjects.v1.json").read_text(encoding="utf-8"))
    rows = [r for r in doc["records"] if r.get("session") == session and r.get("subject") == subject]
    if len(rows) != 1 or rows[0].get("status") != "pdf_header_index_matched":
        raise ValueError("unverified or ambiguous official PDF identity")
    row = rows[0]
    if not re.fullmatch("[0-9a-f]{64}", str(row.get("pdf_sha256"))):
        raise ValueError("invalid registered PDF SHA256")
    return row


def pdf_probe(pdf: Path, *, session: str, subject: str, root: Path = ROOT) -> dict:
    # SHA check BEFORE parser invocation prevents stale/wrong PDFs producing
    # apparently official recovered essays.
    row = registry_row(session, subject, root)
    raw = pdf.read_bytes()
    if not raw.startswith(b"%PDF-") or sha(raw) != row["pdf_sha256"]:
        raise ValueError("PDF bytes do not match pinned official SHA256; no parsing performed")
    import moex_sync
    parser_subject = next((p for p in moex_sync.SUBJECTS if p["name"] == subject), None)
    if parser_subject is None:
        raise ValueError("no matching legacy importer subject")
    year, number = session.split("-")
    round_name = {"1": "第一次", "2": "第二次"}.get(number)
    if round_name is None:
        raise ValueError("unrecognized exam session round")
    extracted = moex_sync.pdf_text(raw)
    legacy = lambda text: moex_sync.parse_essays(
        text, parser_subject, row["exam_code"], year, round_name
    )
    result = diagnose(extracted, legacy, verified_pdf_sha256=row["pdf_sha256"])
    result.update({
        "session": session, "subject": subject,
        "source_url": row["url"], "exam_code": row["exam_code"],
    })
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, required=True, help="local exact SHA-pinned MOEX PDF")
    ap.add_argument("--session", required=True, help="e.g. 108-2")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--out", type=Path, required=True, help="JSON diagnostic outside checkout")
    args = ap.parse_args()
    destination = args.out.resolve()
    root = ROOT.resolve()
    if destination == root or root in destination.parents:
        raise SystemExit("REFUSED: diagnostic output must be outside the repository")
    result = pdf_probe(args.pdf, session=args.session, subject=args.subject)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        k: v for k, v in result.items()
        if k not in ("exact_question_markers", "diagnostic_only_relaxed_markers")
    }, ensure_ascii=False))
    return 0 if result["legacy_essay_count"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
