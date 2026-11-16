#!/usr/bin/env python3
"""Read-only proof of current MOEX 115-2 HBSE essay extraction against HEAD.

Single public PDF GET. Never writes incoming/, official locks, DB or student UI.
A detected drift is evidence to review, NOT an authorized correction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import moex_sync_v2 as v2
from moex_essay_drift_preflight import ROOT, compare, read_committed

EXAM = "115100"
SUBJECT = "人類行為與社會環境"
SOURCE = ROOT / "incoming" / "115100.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-ref", default="HEAD")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    historical = read_committed(args.baseline_ref, SOURCE)
    if historical is None:
        raise SystemExit("Missing committed MOEX 115100 baseline; cannot evaluate live drift")
    old = [x for x in historical["essays"] if x.get("subject") == SUBJECT]
    if len(old) != 2 or {str(x.get("qno")) for x in old} != {"1", "2"}:
        raise SystemExit("Missing exact two committed HBSE essays")
    base = v2.base
    subject = next(x for x in base.SUBJECTS if x["name"] == SUBJECT)
    url = base.pdf_url(EXAM, subject["s"], "Q")
    pdf = base.get_bytes(url)
    source_sha256 = hashlib.sha256(pdf).hexdigest()
    extracted = base.pdf_text(pdf)
    base.validate_question_pdf(extracted, subject)
    current = base.parse_essays(extracted, subject, EXAM, "115", "第二次")
    if len(current) != 2 or {str(x.get("qno")) for x in current} != {"1", "2"}:
        raise SystemExit("Live source did not produce exactly two HBSE essays")
    findings = compare({"essays": old}, {"essays": current})
    report = {
        "schema_version": 1,
        "mode": "read_only_source_probe_no_release_approval",
        "exam_code": EXAM,
        "subject": SUBJECT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": url,
        "source_pdf_sha256": source_sha256,
        "source_pdf_bytes": len(pdf),
        "parser": "moex_sync_v2->moex_sync.parse_essays",
        "pypdf_version": version("pypdf"),
        "baseline_ref": args.baseline_ref,
        "old_essay_count": len(old),
        "parsed_essay_count": len(current),
        "drift_count": len(findings),
        "review_required": bool(findings),
        "findings": findings,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
