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
from audit_moex_source_subjects import load_registry, require_source, url_identity

ROOT = Path(__file__).resolve().parents[1]
SUBJECT_CODES = {
    "社會工作": "0301",
    "社會工作直接服務": "0302",
    "社會政策與社會立法": "0303",
    "人類行為與社會環境": "0304",
    "社會工作研究方法": "0305",
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
    registry = load_registry()
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
        # Query ordering is not source identity. Parse every row strictly before
        # comparing; duplicate parameters, wrong host/type/code still fail closed.
        pairs = {(str(r.get("source_exam_code") or ""),
                  tuple(sorted(url_identity(str(r.get("source_url") or "")).items())))
                 for r in rows}
        if len(pairs) != 1:
            raise ValueError(f"{key}: same-subject MCQ sources disagree")
        code, _identity = next(iter(pairs))
        record = require_source(registry, code, key[2], str(rows[0]["source_url"]))
        url = record["url"]
        round_no = {"第一次": 1, "第二次": 2}[key[1]]
        expected_session = f"{key[0]}-{round_no}"
        if record["session"] != expected_session:
            raise ValueError(f"{key}: MOEX PDF session mismatch")
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
            existing_url and url_identity(existing_url) != url_identity(source["source_url"])
        ):
            raise ValueError(f"{ident}: preexisting official source conflicts with PDF-identity-linked MCQ metadata")
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
    return {"schema_version": 1, "source": "same-session/same-subject MCQ with PDF-header/index identity evidence",
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
        url = load_registry()[(code, subject)]["url"]
        rows += [dict(id=f"{number}-{i}", subject=subject, year="104",
                      round="第1次", source_exam_code=code, source_url=url)
                 for i in range(1, 41)]
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
    # Git-pinned legacy candidate intentionally preserves both c-first and
    # t-first query order. They must remain one verified PDF identity.
    from urllib.parse import urlencode
    mixed = [dict(row) for row in rows]
    parsed = urlsplit(mixed[0]["source_url"])
    mixed[0]["source_url"] = parsed._replace(query=urlencode(sorted(parse_qs(parsed.query).items()), doseq=True)).geturl()
    mixed_index = source_index([("104-1.json", mixed)])
    assert len(mixed_index) == 5
    alternate = dict(approved_fields, source_url=mixed[0]["source_url"])
    assert candidate_manifest([alternate], mixed_index)["already_with_matching_source_fields"] == 1

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
    # Regression: the old 112-1 policy URL s=0303 opens Social Work Management,
    # not Social Policy/Legislation. Require the verified official 0304 code.
    verified_112 = []
    for subject, _ in SUBJECT_CODES.items():
        source_112 = load_registry()[("112030", subject)]
        code_112 = source_112["s"]
        url_112 = source_112["url"]
        verified_112 += [dict(id=f"112-{code_112}-{i}", subject=subject,
                              year="112", round="第1次",
                              source_exam_code="112030", source_url=url_112)
                         for i in range(1, 41)]
    assert len(source_index([("112-1.json", verified_112)])) == 5
    wrong_112 = [dict(row) for row in verified_112]
    for row in wrong_112:
        if row["subject"] == "社會政策與社會立法":
            row["source_url"] = row["source_url"].replace("s=0304&", "s=0303&")
    fails(lambda: source_index([("112-1.json", wrong_112)]))
    print("OFFICIAL ESSAY SOURCE CANDIDATE SELFTEST OK: query-order equivalence and seven fail-closed scenarios")


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
