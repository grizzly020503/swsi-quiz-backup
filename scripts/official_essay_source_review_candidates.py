#!/usr/bin/env python3
"""Prepare historical essay MOEX source references for human PDF comparison.

Read-only: a URL found on the 40 same-exam/same-subject MCQs is a candidate
source link, NOT evidence that an essay stem has been compared with the PDF.
Never writes Official Core, changes grading or promotes a review status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from official_exam_readonly_guard import extract_embedded_essays, load_auto_essays
from unified_question_qa import canon_round
from verified_essay_cdn_pending_sync import verified_moex_url

ROOT = Path(__file__).resolve().parents[1]
SUBJECT_CODES = {
    "社會工作": "0301",
    "社會工作直接服務": "0302",
    "社會政策與社會立法": "0303",
    "人類行為與社會環境": "0304",
    "社會工作研究方法": "0305",
}
# Verified against MOEX PDF page 1 for exam 112030 (2023-1):
# social work management occupied 0303; current-five subject positions shifted.
# Do not generalize to other exams without inspecting their official PDF headers.
EXAM_SUBJECT_CODE_OVERRIDES = {
    "112030": {
        "社會政策與社會立法": "0304",
        "人類行為與社會環境": "0305",
        "社會工作研究方法": "0306",
    },
}

POLICY = {"round_aliases": {
    "1": "第一次", "第1次": "第一次", "第一次": "第一次",
    "2": "第二次", "第2次": "第二次", "第二次": "第二次",
}}


def session_key(row):
    return (str(row.get("year") or ""), canon_round(row.get("round"), POLICY),
            str(row.get("subject") or ""))


def source_index(shards):
    """Fail closed on any duplicate/ambiguous/missing MOEX provenance."""
    groups = defaultdict(list)
    for filename, rows in shards:
        if len(rows) != 200:
            raise ValueError(f"{filename}: expected 200 MCQs, got {len(rows)}")
        for row in rows:
            key = session_key(row)
            if not key[0] or key[1] not in ("第一次", "第二次") or key[2] not in SUBJECT_CODES:
                raise ValueError(f"{filename}: unknown official question metadata {key}")
            groups[key].append(row)
    sources = {}
    for key, rows in groups.items():
        if len(rows) != 40 or len({str(r.get("id") or "") for r in rows}) != 40:
            raise ValueError(f"{key}: expected 40 distinct MCQs")
        pairs = {(str(r.get("source_exam_code") or ""), str(r.get("source_url") or "")) for r in rows}
        if len(pairs) != 1:
            raise ValueError(f"{key}: same-subject MCQ sources disagree")
        code, url = next(iter(pairs))
        expected_subject_code = EXAM_SUBJECT_CODE_OVERRIDES.get(code, {}).get(key[2], SUBJECT_CODES[key[2]])
        if not code or not verified_moex_url(url, code, expected_subject_code):
            raise ValueError(f"{key}: untrusted MOEX question source")
        sources[key] = {"source_exam_code": code, "source_url": url,
                        "supporting_mcq_count": 40}
    return sources


def candidate_manifest(essays, sources):
    seen = set()
    rows = []
    already = 0
    for e in essays:
        ident = str(e.get("id") or "")
        if not ident or ident in seen:
            raise ValueError(f"invalid/duplicate official essay id: {ident!r}")
        seen.add(ident)
        key = session_key(e)
        source = sources.get(key)
        if not source:
            raise ValueError(f"{ident}: no unambiguous MCQ source match")
        existing_code = str(e.get("source_exam_code") or "")
        existing_url = str(e.get("source_url") or "")
        if (existing_code and existing_code != source["source_exam_code"]) or (
            existing_url and existing_url != source["source_url"]
        ):
            raise ValueError(f"{ident}: preexisting official source conflicts with verified MCQ provenance")
        if existing_code and existing_url:
            already += 1
            continue
        question = str(e.get("q") or "")
        if not question.strip():
            raise ValueError(f"{ident}: empty official essay stem")
        rows.append({
            "id": ident, "year": key[0], "round": key[1], "subject": key[2],
            "qno": str(e.get("qno") or ""),
            "source_exam_code_candidate": source["source_exam_code"],
            "source_url_candidate": source["source_url"],
            "matching_mcqs": 40,
            "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "status": "awaiting_independent_official_pdf_stem_comparison",
            "automatic_release_approval": False,
        })
    rows.sort(key=lambda r: (-int(r["year"]), r["round"], r["subject"], r["qno"]))
    return {"schema_version": 1, "source": "same-session/same-subject already-provenanced MCQ",
            "disclaimer": "Candidate source URL only. No official essay PDF text comparison, grading or review approval was performed.",
            "essays_total": len(essays),
            "already_with_matching_source_fields": already,
            "candidates_needing_pdf_verification": len(rows),
            "candidates": rows}


def load_real_shards():
    manifest = json.loads((ROOT / "cdn/question-shards/manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("shards")
    if not isinstance(entries, list) or len(entries) != 24:
        raise ValueError("unexpected historical manifest: requires 24 sessions")
    shards = []
    for row in entries:
        name = str(row.get("file") or "")
        if not name or Path(name).name != name:
            raise ValueError("invalid shard path in manifest")
        path = ROOT / "cdn/question-shards" / name
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != row.get("sha256"):
            raise ValueError(f"{name}: shard manifest SHA256 mismatch")
        payload = json.loads(raw)
        questions = payload.get("questions") if isinstance(payload, dict) else None
        if not isinstance(questions, list):
            raise ValueError(f"{name}: missing MCQ questions[]")
        shards.append((name, questions))
    return shards


def selftest():
    code = "104030"
    rows = []
    for subject, number in SUBJECT_CODES.items():
        url = ("https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?"
               f"c=103&code={code}&q=1&s={number}&t=Q")
        rows += [dict(id=f"{number}-{i}", subject=subject, year="104",
                      round="第1次", source_exam_code=code, source_url=url)
                 for i in range(1, 41)]
    # Reproduce the real 112-1 wrong-subject provenance failure, fail closed.
    def make_112_rows():
        corrected = []
        for row in rows:
            item = dict(row)
            item["source_exam_code"] = "112030"
            code = EXAM_SUBJECT_CODE_OVERRIDES["112030"].get(item["subject"], SUBJECT_CODES[item["subject"]])
            item["source_url"] = (
                "https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?"
                f"c=103&code=112030&q=1&s={code}&t=Q"
            )
            corrected.append(item)
        return corrected

    rows112 = make_112_rows()
    assert len(source_index([("112-1.json", rows112)])) == 5
    wrong112 = [dict(item) for item in rows112]
    wrong_item = next(item for item in wrong112 if item["subject"] == "社會政策與社會立法")
    wrong_item["source_url"] = wrong_item["source_url"].replace("s=0304", "s=0303")
    try:
        source_index([("112-1.json", wrong112)])
    except ValueError:
        pass
    else:
        raise AssertionError("112-1 wrong-subject source was accepted")

    index = source_index([("104-1.json", rows)])
    essay = dict(id="synthetic-essay", subject="社會工作", year="104",
                 round="第一次", qno="1", q="此為合成題幹")
    report = candidate_manifest([essay], index)
    assert report["candidates_needing_pdf_verification"] == 1
    assert report["candidates"][0]["automatic_release_approval"] is False
    assert report["candidates"][0]["status"].startswith("awaiting_independent")
    approved_fields = dict(essay, source_exam_code=index[session_key(essay)]["source_exam_code"],
                           source_url=index[session_key(essay)]["source_url"])
    assert candidate_manifest([approved_fields], index)["already_with_matching_source_fields"] == 1

    def fails(fn):
        try:
            fn()
        except ValueError:
            return
        raise AssertionError("unsafe official source was accepted")
    fails(lambda: candidate_manifest([essay, essay], index))
    fails(lambda: candidate_manifest([dict(essay, source_url="https://evil.invalid")], index))
    fails(lambda: source_index([("fixture", rows[:-1])]))
    bad = [dict(row) for row in rows]
    bad[0]["source_url"] = "https://evil.invalid"
    fails(lambda: source_index([("fixture", bad)]))
    bad = [dict(row) for row in rows]
    bad[0]["source_exam_code"] = "115100"
    fails(lambda: source_index([("fixture", bad)]))
    fails(lambda: candidate_manifest([dict(essay, year="113")], index))
    print("OFFICIAL ESSAY SOURCE CANDIDATE SELFTEST OK: six fail-closed scenarios")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    source = source_index(load_real_shards())
    essays = extract_embedded_essays() + load_auto_essays()
    report = candidate_manifest(essays, source)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OFFICIAL ESSAY SOURCE CANDIDATES PREPARED: {report['candidates_needing_pdf_verification']} review-only URLs; "
          f"{report['already_with_matching_source_fields']} already attributed; 0 auto-approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
