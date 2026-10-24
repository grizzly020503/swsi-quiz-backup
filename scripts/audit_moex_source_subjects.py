#!/usr/bin/env python3
"""Audit MOEX subject/source mappings without trusting URL syntax as PDF proof.

Default: fail closed for the two independently PDF-checked boundary sessions:
112-1 (old seven-subject exam) and 115-1 (new five-subject exam).
--scan-all: diagnostic review queue for all 24 shards; NEVER auto-fixes sources.
Source URLs are *not* promoted to verified until MOEX PDF cover-page checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "cdn/question-shards"
OLD = {
    "社會工作": "0301",
    "社會工作直接服務": "0302",
    "社會政策與社會立法": "0304",
    "人類行為與社會環境": "0305",
    "社會工作研究方法": "0306",
}
NEW = {
    "社會工作": "0301",
    "社會工作直接服務": "0302",
    "社會政策與社會立法": "0303",
    "人類行為與社會環境": "0304",
    "社會工作研究方法": "0305",
}
COVER_CHECKED = {"112-1": OLD, "115-1": NEW}


def audit_file(filename: str, known_codes: dict[str, str]) -> list[str]:
    path = DIR / filename
    raw = path.read_bytes()
    questions = json.loads(raw)["questions"]
    if len(questions) != 200:
        return [f"{filename}: expected 200 questions"]
    failures: list[str] = []
    counts: dict[str, int] = {}
    for row in questions:
        subject = row.get("subject", "")
        counts[subject] = counts.get(subject, 0) + 1
        u = urlsplit(str(row.get("source_url") or ""))
        query = parse_qs(u.query)
        expected = known_codes.get(subject)
        if not expected:
            failures.append(f"{filename}/{row.get('id')}: unknown subject {subject}")
            continue
        if (u.scheme != "https" or u.hostname != "wwwq.moex.gov.tw"
                or u.path != "/exam/wHandExamQandA_File.ashx"
                or query.get("code") != [str(row.get("source_exam_code"))]
                or query.get("c") != ["103"] or query.get("q") != ["1"]
                or query.get("t") != ["Q"] or query.get("s") != [expected]):
            failures.append(f"{filename}/{row.get('id')}: expected subject s={expected}")
    if set(counts) != set(known_codes) or any(n != 40 for n in counts.values()):
        failures.append(f"{filename}: expected exactly 40 rows in each of 5 subjects")
    return failures


def audit_manifest() -> list[str]:
    manifest = json.loads((DIR / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    for entry in manifest["shards"]:
        content = (DIR / entry["file"]).read_bytes()
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            errors.append(f"manifest: digest/byte count mismatch {entry['file']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-all", action="store_true", help="report legacy source-code anomalies across all sessions (review only)")
    args = parser.parse_args()
    failures = audit_manifest()
    for session, scheme in COVER_CHECKED.items():
        failures += audit_file(session + ".json", scheme)
    print(f"OFFICIAL PDF SUBJECT MAPPING BASELINE: {'OK' if not failures else 'FAIL'}; checked 112-1 and 115-1")
    if args.scan_all:
        for y in range(104, 116):
            for round_no in (1, 2):
                session = f"{y}-{round_no}"
                if session in COVER_CHECKED:
                    continue
                warnings = audit_file(session + ".json", OLD if y < 115 else NEW)
                if warnings:
                    print(f"REVIEW REQUIRED {session}: {len(warnings)} source rows with unverified/contradictory subject codes")
                else:
                    print(f"STRUCTURAL MATCH ONLY {session}: MOEX PDF cover still needs independent review")
    for problem in failures[:25]:
        print(f"FAIL {problem}")
    if len(failures) > 25:
        print(f"... {len(failures) - 25} further baseline failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
