#!/usr/bin/env python3
"""Read-only, fingerprint-bound official essay text comparison.

Reuse the existing MOEX v2 parser. A normalized PDF text match is mechanical
evidence, never a human rubric approval or permission to rewrite Official Core.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import difflib
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from audit_moex_source_subjects import load_registry
from official_exam_readonly_guard import collect_essays
from official_essay_source_review_candidates import session_key


def normalize(text):
    # Only existing MOEX font labels, Unicode compatibility forms and layout
    # whitespace. Retain punctuation, numbers, negation and substantive wording.
    for glyph, label in (("\ue129", "（一）"), ("\ue12a", "（二）"), ("\ue12b", "（三）")):
        text = text.replace(glyph, label)
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def compare(stored, official):
    normalized = unicodedata.normalize("NFKC", official["q"])
    # Never accept the import parser's historical default of 20 as PDF proof.
    totals = re.findall(r"共\s*(\d+)\s*分", normalized)
    score_marks = re.findall(r"\(\s*(\d+)\s*分\s*\)", normalized)
    if totals:
        explicit_points = str(int(totals[0])) if len(set(totals)) == 1 and 1 <= int(totals[0]) <= 50 else None
    else:
        explicit_points = str(sum(map(int, score_marks))) if score_marks and 1 <= sum(map(int, score_marks)) <= 50 else None
    reasons = []
    if explicit_points is None:
        reasons.append("official_score_not_explicitly_extracted")
    if explicit_points is not None and str(stored.get("points")) != explicit_points:
        reasons.append("points_differ")
    left, right = normalize(stored["q"]), normalize(official["q"])
    differences = []
    if left != right:
        reasons.append("normalized_text_differs")
        for tag, a, b, c, d in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
            if tag != "equal":
                differences.append({"operation": tag, "stored": left[a:b], "official_extraction": right[c:d],
                                    "context": right[max(0,c-14):min(len(right),d+14)]})
    return {"status": "normalized_pdf_text_match" if not reasons else "review",
            "reasons": reasons, "stored_points": stored.get("points"), "pdf_points": explicit_points,
            "existing_parser_points": official.get("points"),
            "stored_text_sha256": hashlib.sha256(stored["q"].encode()).hexdigest(),
            "pdf_extracted_text": official["q"], "differences": differences,
            "human_approval": False, "official_core_mutation": False}


def audit(evidence_dir):
    import moex_sync_v2 as parser
    registry = load_registry()
    root=Path(__file__).resolve().parents[1]
    fingerprint_paths=['scripts/official_essay_pdf_audit.py','scripts/moex_sync.py','scripts/moex_sync_v2.py','index.html','auto/essays_auto.json','data/moex_source_subjects.v1.json']
    fingerprints={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in fingerprint_paths}
    indexed = {(*session_key(e), str(e["qno"])): e for e in collect_essays().values()}
    if len(indexed) != 240:
        raise ValueError("expected 240 distinct official essay identities")

    def inspect(item):
        code, subject = item
        row = registry[item]
        path = evidence_dir / f"{code}-{row['c']}-{row['s']}.pdf"
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["pdf_sha256"]:
            raise ValueError(f"{code}/{subject}: PDF fingerprint mismatch")
        text = unicodedata.normalize("NFKC", parser.base.pdf_text(raw))
        profile = next(s for s in parser.base.SUBJECTS if s["name"] == subject)
        round_name = "第一次" if row["session"].endswith("-1") else "第二次"
        year = row["session"].split("-")[0]
        essays = parser.base.parse_essays(text, profile, code, year, round_name)
        if len(essays) != 2:
            return [{"id": indexed[(year,round_name,subject,str(q))]["id"], "status": "review",
                     "reasons": ["existing_parser_cannot_extract_exactly_two_essays"],
                     "source_url": row["url"], "pdf_sha256": row["pdf_sha256"],
                     "human_approval": False, "official_core_mutation": False} for q in (1,2)]
        results = []
        for essay in essays:
            key = (year, round_name, subject, str(essay["qno"]))
            stored = indexed[key]
            result = compare(stored, essay)
            result.update(id=stored["id"], year=year, round=round_name, subject=subject,
                          qno=essay["qno"], source_url=row["url"], pdf_sha256=row["pdf_sha256"])
            results.append(result)
        return results

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = [row for result in pool.map(inspect, sorted(registry)) for row in result]
    counts = Counter(r["status"] for r in rows)
    return {"schema_version": 1, "input_sha256": fingerprints, "scope": "normalized_official_essay_text_comparison_only",
            "essays": len(rows), "pdfs": len(registry), "counts": dict(counts),
            "normalization": "MOEX E129/E12A/E12B labels, NFKC, layout whitespace only",
            "human_review_completed": False, "official_core_modified": False,
            "release_approval": False, "rows": rows}


def selftest():
    a = {"q": "試說明倫理原則。（25 分）", "points": "25"}
    b = {"q": "試說明倫理原則。\n（25 分）", "points": "25"}
    assert compare(a,b)["status"] == "normalized_pdf_text_match"
    for text in ("試說明倫理原則？（25 分）", "試說明倫理原則。（20 分）",
                 "試說明非倫理原則。（25 分）", "試說明倫理原則。"):
        assert compare(a,{"q":text,"points":"25"})["status"] == "review"
    assert compare(dict(a,points="20"),b)["status"] == "review"
    assert compare(a,dict(b,points="20"))["status"] == "normalized_pdf_text_match"
    assert compare(a,dict(b,q="試說明倫理原則。（ 25 分）"))["status"] == "normalized_pdf_text_match"
    assert normalize("第12條") != normalize("第21條")
    assert normalize("應") != normalize("不應")
    assert normalize("\ue129評估") == normalize("（一）評估")
    print("OFFICIAL ESSAY PDF AUDIT SELFTEST OK: layout/font equivalence; wording, punctuation, number and score differences held")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.evidence_dir or not args.out:
        parser.error("--evidence-dir and --out required; no implicit downloads or writes")
    report = audit(args.evidence_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k != "rows"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
