#!/usr/bin/env python3
"""Compare SHA-checked current CDN MCQs with production public.questions (read only).

A report of 'drift' requires source/human review; this tool NEVER rewrites
official wording, answers, accepted answers or grading metadata. Enrichment
and historical law/status fields are deliberately outside this equality test.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from historical_source_url_repair_plan import load_local_shards

OFFICIAL_FIELDS = (
    "subject", "year", "round", "qno", "question",
    "opt_a", "opt_b", "opt_c", "opt_d", "source_exam_code",
)
GRADING_FIELDS = ("answer", "accepted_answers", "grading_mode")
REQUIRED_FIELDS = ("id",) + OFFICIAL_FIELDS + GRADING_FIELDS


def index(rows: list[dict], label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise ValueError(label + ": expected question array")
    indexed: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(label + ": non-object question")
        ident = row.get("id")
        if not isinstance(ident, str) or not ident or ident in indexed:
            raise ValueError(label + ": missing/duplicate question identity")
        if any(key not in row for key in REQUIRED_FIELDS):
            raise ValueError(label + ": missing official field for " + ident)
        indexed[ident] = row
    return indexed


def compare(expected_rows: list[dict], observed_rows: list[dict]) -> dict[str, Any]:
    """Compare all tracked exams, including future profiles without hardcoded years."""
    expected = index(expected_rows, "verified manifest")
    live = index(observed_rows, "read-only production API")
    if len(expected) < 4800:
        raise ValueError("verified corpus incomplete: fewer than historical 4,800 MCQs")
    missing = sorted(expected.keys() - live.keys())
    extra = sorted(live.keys() - expected.keys())
    differences: list[dict] = []
    grading: list[dict] = []
    for ident in sorted(expected.keys() & live.keys()):
        x, y = expected[ident], live[ident]
        official = [field for field in OFFICIAL_FIELDS if x[field] != y[field]]
        grade = [field for field in GRADING_FIELDS if x[field] != y[field]]
        if official:
            differences.append({"id": ident, "fields": official})
        if grade:
            grading.append({"id": ident, "fields": grade})
    status = "HOLD_REVIEW_DRIFT" if (missing or extra or differences or grading) else "MATCH"
    return {
        "schema_version": 1,
        "status": status,
        "source": "SHA256_verified_current_CDN_manifest_vs_public_questions",
        "expected_questions": len(expected),
        "live_questions": len(live),
        "matched_ids": len(expected.keys() & live.keys()),
        "missing_live_ids": missing,
        "unpublished_live_ids": extra,
        "official_wording_differences": differences,
        "grading_differences": grading,
        "summary": {
            "missing_live": len(missing), "unpublished_live": len(extra),
            "official_wording_drift": len(differences),
            "grading_drift": len(grading),
        },
        "official_core_modified": False,
        "database_written": False,
        "release_approved": False,
    }


def check_local(rows: list[dict], root: Path | None = None) -> dict[str, Any]:
    return compare(load_local_shards(root) if root else load_local_shards(), rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=Path, help="offline public.questions JSON export")
    src.add_argument("--live", action="store_true", help="explicit anon read-only Supabase SELECT")
    ap.add_argument("--out", type=Path, help="save diagnostic JSON outside repo")
    ap.add_argument("--fail-on-drift", action="store_true")
    args = ap.parse_args()
    if args.live:
        from build_question_shards import fetch_questions
        rows = fetch_questions()
    else:
        rows = json.loads(args.input.read_text(encoding="utf-8"))
    report = check_local(rows)
    if args.out:
        from historical_source_url_guard import ROOT
        target = args.out.resolve()
        if target == ROOT or ROOT in target.parents:
            raise SystemExit("REFUSED: report must not be written in source repository")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in {"missing_live_ids", "unpublished_live_ids",
                                   "official_wording_differences", "grading_differences"}},
                     ensure_ascii=False))
    raise SystemExit(2 if args.fail_on_drift and report["status"] != "MATCH" else 0)
