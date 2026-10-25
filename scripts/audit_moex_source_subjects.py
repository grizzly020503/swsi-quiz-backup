#!/usr/bin/env python3
"""Fail closed on exam-specific MOEX PDF identity, without inferring legacy codes.

The registry contains observed PDF cover text + official-index HTTP fingerprints.
This verifies source identity only, never question wording, answers or rubrics.
Use --evidence-dir to independently re-extract the downloaded PDF/index bytes.
Default execution is offline and never updates the corpus or approval metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/moex_source_subjects.v1.json"
SUBJECTS = {"社會工作", "社會工作直接服務", "社會政策與社會立法",
            "人類行為與社會環境", "社會工作研究方法"}


def norm(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def url_identity(url):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (parsed.scheme != "https" or parsed.hostname != "wwwq.moex.gov.tw"
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443) or parsed.fragment
            or parsed.path != "/exam/wHandExamQandA_File.ashx"
            or set(query) != {"c", "code", "s", "q", "t"}
            or any(len(v) != 1 for v in query.values())
            or query["q"] != ["1"] or query["t"] != ["Q"]
            or not re.fullmatch(r"\d{6}", query["code"][0])
            or not re.fullmatch(r"\d{3}", query["c"][0])
            or not re.fullmatch(r"\d{4}", query["s"][0])):
        raise ValueError("invalid official question URL")
    return {k: v[0] for k, v in query.items()}


def header_errors(row, header):
    errors = []
    year, round_no = row["session"].split("-")
    text = norm(header)
    # Preserve line boundaries: '社會工作' must not match '社會工作管理'.
    subject = re.search(r"科\s*目\s*[:：]\s*([^\n]+)", header)
    if not subject or norm(subject.group(1)) != row["subject"]:
        errors.append("PDF subject mismatch")
    if f"{year}年第{'一' if round_no == '1' else '二'}次" not in text:
        errors.append("PDF exam year/round mismatch")
    if "類科:社會工作師" not in text:
        errors.append("PDF professional class mismatch")
    if f"代號:{row['paper_code']}" not in text:
        errors.append("PDF paper code mismatch")
    return errors


def index_matches(row, text):
    expected = url_identity(row["url"])
    for attrs in re.findall(r"<a\b([^>]*)>", text, re.I):
        href = re.search(r'href="([^"]+)"', attrs)
        title = re.search(r'title="([^"]+)"', attrs)
        if not href or not title:
            continue
        link = urljoin("https://wwwq.moex.gov.tw/exam/", html.unescape(href.group(1)))
        try:
            same = url_identity(link) == expected
        except ValueError:
            continue
        if same and f"開啓{row['subject']}試題" in html.unescape(title.group(1)):
            return True
    return False


def validate_record(row):
    identity = url_identity(row["url"])
    year, round_no = row["session"].split("-")
    if (row["status"] != "pdf_header_index_matched" or row.get("errors")
            or identity["code"] != row["exam_code"] or not row["exam_code"].startswith(year)
            or round_no not in ("1", "2") or row["subject"] not in SUBJECTS
            or identity["c"] != row["c"] or identity["s"] != row["s"]
            or not re.fullmatch(r"\d{5}", row["paper_code"])
            or not row["paper_code"].startswith(row["c"])):
        raise ValueError("unreviewable exam-specific source identity")
    index_url = urlsplit(row["index_url"])
    if (index_url.scheme != "https" or index_url.netloc != "wwwq.moex.gov.tw"
            or index_url.path != "/exam/wFrmExamQandASearch.aspx"
            or parse_qs(index_url.query) != {"e": [row["exam_code"]], "y": [str(int(year)+1911)]}):
        raise ValueError("official directory exam mismatch")
    for field, expected_hash in (("http", row["pdf_sha256"]), ("index_http", row["index_sha256"])):
        evidence = row[field]
        if (evidence.get("fetch_status") != "downloaded" or evidence.get("http_status") != 200
                or evidence.get("sha256") != expected_hash
                or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or not evidence.get("checked_at")):
            raise ValueError("missing successful HTTP/hash evidence")
    if ("application/pdf" not in row["http"]["mime"].lower()
            or row["http"]["url"] != row["url"]
            or row["index_http"]["url"] != row["index_url"]):
        raise ValueError("MIME/URL evidence mismatch")
    errors = header_errors(row, row["pdf_header"])
    if errors:
        raise ValueError("; ".join(errors))


def load_registry(path=REGISTRY):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported source registry")
    index = {}
    for row in payload["records"]:
        validate_record(row)
        key = (row["exam_code"], row["subject"])
        if key in index:
            raise ValueError("duplicate official source registry key")
        index[key] = row
    return index


def require_source(index, exam_code, subject, url):
    record = index.get((exam_code, subject))
    if record is None or url_identity(record["url"]) != url_identity(url):
        raise ValueError(f"{exam_code}/{subject}: unverified or wrong-subject source")
    return record


def audit(evidence_dir=None):
    index = load_registry()
    manifest = json.loads((ROOT / "cdn/question-shards/manifest.json").read_text())
    errors, seen = [], set()
    total = 0
    for entry in manifest["shards"]:
        if not re.fullmatch(r"\d{3}-[12]\.json", entry["file"]):
            raise ValueError("invalid historical shard filename")
        raw = (ROOT / "cdn/question-shards" / entry["file"]).read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            errors.append(entry["file"] + ": manifest integrity mismatch")
        questions = json.loads(raw)["questions"]
        if len(questions) != 200 or Counter(q["subject"] for q in questions) != Counter({s:40 for s in SUBJECTS}):
            errors.append(entry["file"] + ": expected 5 x 40 questions")
        for q in questions:
            total += 1
            try:
                row = require_source(index, q["source_exam_code"], q["subject"], q["source_url"])
                if row["session"] != Path(entry["file"]).stem or str(q["year"]) != row["session"].split("-")[0]:
                    raise ValueError("question/shard exam mismatch")
                seen.add((row["exam_code"], row["subject"]))
            except ValueError as exc:
                errors.append(str(q["id"]) + ": " + str(exc))
    if len(index) != 120 or len(seen) != 120 or total != 4800 or len(manifest["shards"]) != 24:
        errors.append("requires exactly 24 sessions / 120 PDF identities / 4800 MCQs")
    revision = hashlib.sha256("\n".join(f"{e['file']}:{e['sha256']}" for e in manifest["shards"]).encode()).hexdigest()[:20]
    if (manifest["dataset_revision"] != revision
            or manifest["total_uncompressed_bytes"] != sum(e["bytes"] for e in manifest["shards"])
            or manifest["total_questions"] != total):
        errors.append("manifest aggregate/revision mismatch")
    if evidence_dir:
        for row in index.values():
            name = f"{row['exam_code']}-{row['c']}-{row['s']}.pdf"
            pdf = evidence_dir / name
            raw = pdf.read_bytes()
            directory = (evidence_dir / f"index-{row['exam_code']}.html").read_bytes()
            if (not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != row["pdf_sha256"]
                    or hashlib.sha256(directory).hexdigest() != row["index_sha256"]):
                errors.append(name + ": downloaded evidence fingerprint mismatch")
                continue
            text = subprocess.check_output(["pdftotext", "-f", "1", "-l", "1", "-layout", str(pdf), "-"], text=True)
            errors += [name + ": " + e for e in header_errors(row, text.split("甲、")[0][:1800])]
            if not index_matches(row, directory.decode("utf-8-sig")):
                errors.append(name + ": official directory subject link mismatch")
    return {"scope": "source_identity_only", "questions": total, "pdf_identities": len(seen),
            "full_stem_answer_approval": False, "errors": errors, "status": "PASS" if not errors else "NO_GO"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit(args.evidence_dir)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
