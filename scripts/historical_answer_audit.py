#!/usr/bin/env python3
"""Audit historical SWSI MC answers against official MOEX final correction sheets.

READ-ONLY:
- downloads MOEX official `t=A` consolidated correction sheets
- reads the public Supabase `questions` table with the existing anon key in index.html
- writes local JSON/Markdown reports only

It never updates Supabase and never changes official question/answer content.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
MOEX_BASE = "https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx"
UA = "Mozilla/5.0 (compatible; swsi-historical-answer-audit/1.0)"

SUBJECTS = [
    "社會工作",
    "社會工作直接服務",
    "社會政策與社會立法",
    "人類行為與社會環境",
    "社會工作研究方法",
]

# Confirmed MOEX exam codes for the social-worker first/second exam in ROC 104–115.
EXAMS = [
    ("104", "第一次", "104030"),
    ("104", "第二次", "104100"),
    ("105", "第一次", "105030"),
    ("105", "第二次", "105090"),
    ("106", "第一次", "106030"),
    ("106", "第二次", "106111"),
    ("107", "第一次", "107030"),
    ("107", "第二次", "107110"),
    ("108", "第一次", "108020"),
    ("108", "第二次", "108110"),
    ("109", "第一次", "109030"),
    ("109", "第二次", "109110"),
    ("110", "第一次", "110030"),
    ("110", "第二次", "110111"),
    ("111", "第一次", "111030"),
    ("111", "第二次", "111110"),
    ("112", "第一次", "112030"),
    ("112", "第二次", "112110"),
    ("113", "第一次", "113030"),
    ("113", "第二次", "113100"),
    ("114", "第一次", "114030"),
    ("114", "第二次", "114100"),
    ("115", "第一次", "115030"),
    ("115", "第二次", "115100"),
]

FW = str.maketrans("ＡＢＣＤａｂｃｄ", "ABCDABCD")


def clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def compact(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def get_pdf(code: str) -> bytes:
    url = f"{MOEX_BASE}?code={code}&t=A"
    r = requests.get(url, timeout=60, headers={"User-Agent": UA})
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"{code}: MOEX consolidated answer is not PDF ({r.headers.get('content-type')})")
    return r.content


def pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def subject_sections(text: str) -> dict[str, str]:
    """Return the best text section for each target subject.

    MOEX PDFs vary by year. We locate subject-name occurrences and take text until
    the next subject heading. A candidate must contain enough pure ABCD/# tokens.
    """
    lines = [clean_line(x) for x in text.splitlines() if clean_line(x)]
    result: dict[str, str] = {}

    subject_positions = []
    for i, line in enumerate(lines):
        for subject in SUBJECTS:
            # Avoid matching 社會工作 inside 社會工作直接服務 / 研究方法 etc.
            if subject == "社會工作":
                hit = bool(re.search(r"科目名稱[:：]?\s*社會工作(?:\s|$)", line)) or line == "社會工作"
            else:
                hit = subject in line
            if hit:
                subject_positions.append((i, subject))

    # If headings split as one line "科目名稱：" then next line subject name.
    for i, line in enumerate(lines[:-1]):
        if compact(line).startswith("科目名稱"):
            nxt = lines[i + 1]
            for subject in SUBJECTS:
                if compact(nxt) == compact(subject):
                    subject_positions.append((i, subject))

    subject_positions = sorted(set(subject_positions))
    all_heading_idxs = sorted({i for i, _ in subject_positions})

    for idx, subject in subject_positions:
        end_candidates = [x for x in all_heading_idxs if x > idx]
        end = end_candidates[0] if end_candidates else min(len(lines), idx + 80)
        # Include enough lines for older layouts where answers are more spread out.
        end = min(len(lines), max(end, idx + 15))
        section = "\n".join(lines[idx:end])
        tokens = re.findall(r"(?<![A-Z])[ABCD#]{1,10}(?![A-Z])", section.upper())
        score = sum(len(t) for t in tokens)
        if score >= 35:
            old = result.get(subject)
            if not old or len(section) < len(old) * 2:
                result[subject] = section

    # Fallback: search around a raw occurrence if the heading detector missed it.
    for subject in SUBJECTS:
        if subject in result:
            continue
        for i, line in enumerate(lines):
            if subject in line:
                section = "\n".join(lines[i : min(len(lines), i + 50)])
                tokens = re.findall(r"(?<![A-Z])[ABCD#]{1,10}(?![A-Z])", section.upper())
                if sum(len(t) for t in tokens) >= 35:
                    result[subject] = section
                    break

    return result


def answer_tokens(section: str) -> str:
    """Extract the 40-character A/B/C/D/# answer row from one subject section."""
    lines = [clean_line(x) for x in section.splitlines() if clean_line(x)]
    candidates: list[str] = []
    started = False

    for line in lines:
        c = compact(line).upper().translate(FW)
        if "答案" in c:
            started = True
            # Some years put chunks on the same line after 答案.
            tail = c.split("答案", 1)[1]
            candidates.extend(re.findall(r"[ABCD#]{2,10}", tail))
            continue
        if not started:
            continue
        if "備註" in c:
            break
        # Accept only pure answer chunks. This rejects prose containing A/B/C/D.
        for tok in re.findall(r"(?<![A-Z])[ABCD#]{1,10}(?![A-Z])", c):
            if re.fullmatch(r"[ABCD#]{1,10}", tok):
                candidates.append(tok)
        joined = "".join(candidates)
        if len(joined) >= 40:
            break

    joined = "".join(candidates)
    # Sometimes old PDFs place the first answer chunks before an explicit 答案 label.
    if len(joined) < 40:
        raw = []
        for line in lines:
            c = compact(line).upper().translate(FW)
            if "備註" in c:
                break
            for tok in re.findall(r"(?<![A-Z])[ABCD#]{2,10}(?![A-Z])", c):
                if re.fullmatch(r"[ABCD#]{2,10}", tok):
                    raw.append(tok)
        joined = "".join(raw)

    # Choose a 40-char prefix/slice that has realistic answer characters.
    if len(joined) < 40:
        raise RuntimeError(f"could only extract {len(joined)} answer chars: {joined!r}")
    return joined[:40]


def parse_corrections(section: str, row: str) -> dict[int, set[str]]:
    """Map # positions to final accepted answers from the correction note."""
    accepted: dict[int, set[str]] = {}
    note = compact(section).upper().translate(FW)

    # All-give questions.
    for m in re.finditer(r"第(\d{1,2})題一律給分", note):
        accepted[int(m.group(1))] = {"A", "B", "C", "D"}

    # Multiple accepted letters, e.g. A或C或AC者均給分 / A或D者均給分.
    for m in re.finditer(r"第(\d{1,2})題答([ABCD])或([ABCD])(?:或[ABCD]{2,4})?者均給分", note):
        accepted[int(m.group(1))] = {m.group(2), m.group(3)}

    # One corrected answer, e.g. 第43題答C給分.
    for m in re.finditer(r"第(\d{1,2})題答([ABCD])給分", note):
        accepted[int(m.group(1))] = {m.group(2)}

    for qno, ch in enumerate(row, start=1):
        if ch != "#":
            accepted.setdefault(qno, {ch})
        elif qno not in accepted:
            raise RuntimeError(f"question {qno} is # but correction note was not parsed")
    return accepted


def parse_official_exam(data: bytes, year: str, round_name: str, code: str) -> dict[tuple[str, int], set[str]]:
    text = pdf_text(data)
    if "社會工作師" not in text:
        raise RuntimeError(f"{code}: consolidated sheet has no 社會工作師")
    sections = subject_sections(text)
    missing_subjects = [s for s in SUBJECTS if s not in sections]
    if missing_subjects:
        raise RuntimeError(f"{code}: missing subject sections {missing_subjects}")

    out: dict[tuple[str, int], set[str]] = {}
    for subject in SUBJECTS:
        row = answer_tokens(sections[subject])
        acc = parse_corrections(sections[subject], row)
        if len(acc) != 40:
            raise RuntimeError(f"{code} {subject}: parsed {len(acc)} answers")
        for qno in range(1, 41):
            out[(subject, qno)] = acc[qno]
    return out


def read_frontend_config() -> tuple[str, str]:
    text = INDEX.read_text(encoding="utf-8")
    um = re.search(r'url:\s*"(https://[^\"]+\.supabase\.co)"', text)
    km = re.search(r'key:\s*"(eyJ[^\"]+)"', text)
    if not um or not km:
        raise RuntimeError("cannot locate public Supabase URL/key in index.html")
    return um.group(1).rstrip("/"), km.group(1)


def fetch_db_questions() -> list[dict]:
    base, key = read_frontend_config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    rows: list[dict] = []
    offset = 0
    while True:
        url = f"{base}/rest/v1/questions"
        params = {
            "select": "id,subject,year,round,qno,answer",
            "offset": str(offset),
            "limit": "1000",
            "order": "year.asc,round.asc,subject.asc,qno.asc",
        }
        r = requests.get(url, headers=headers, params=params, timeout=45)
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list):
            raise RuntimeError("Supabase response is not a list")
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)
    return rows


def db_accepted(answer: str) -> set[str]:
    a = str(answer or "").strip().upper().translate(FW)
    if a == "一律給分":
        return {"A", "B", "C", "D"}
    if a in {"A", "B", "C", "D"}:
        return {a}
    return set()


def audit(output_dir: Path) -> dict:
    db_rows = fetch_db_questions()
    if len(db_rows) != 4800:
        raise RuntimeError(f"expected 4800 DB questions, got {len(db_rows)}")

    db = {}
    for r in db_rows:
        key = (str(r["year"]), str(r["round"]), str(r["subject"]), int(r["qno"]))
        if key in db:
            raise RuntimeError(f"duplicate DB logical key {key}")
        db[key] = r

    findings = []
    exam_summary = []
    official_count = 0

    for year, round_name, code in EXAMS:
        print(f"AUDIT {year} {round_name} ({code})", flush=True)
        data = get_pdf(code)
        official = parse_official_exam(data, year, round_name, code)
        official_count += len(official)
        counts = Counter()

        for (subject, qno), off_set in official.items():
            key = (year, round_name, subject, qno)
            row = db.get(key)
            if row is None:
                findings.append({
                    "type": "MISSING_DB",
                    "year": year,
                    "round": round_name,
                    "exam_code": code,
                    "subject": subject,
                    "qno": qno,
                    "official": sorted(off_set),
                    "db": None,
                    "id": None,
                })
                counts["MISSING_DB"] += 1
                continue

            db_set = db_accepted(row.get("answer"))
            if not db_set:
                typ = "INVALID_DB_ANSWER"
            elif db_set == off_set:
                typ = "OK"
            elif db_set.issubset(off_set) and len(off_set) > len(db_set):
                typ = "INCOMPLETE_MULTI"
            elif off_set.issubset(db_set) and len(db_set) > len(off_set):
                typ = "DB_TOO_BROAD"
            elif db_set.isdisjoint(off_set):
                typ = "WRONG"
            else:
                typ = "SET_MISMATCH"

            counts[typ] += 1
            if typ != "OK":
                findings.append({
                    "type": typ,
                    "year": year,
                    "round": round_name,
                    "exam_code": code,
                    "subject": subject,
                    "qno": qno,
                    "official": sorted(off_set),
                    "db": sorted(db_set),
                    "db_raw": row.get("answer"),
                    "id": row.get("id"),
                })

        exam_summary.append({
            "year": year,
            "round": round_name,
            "exam_code": code,
            "counts": dict(counts),
        })

    if official_count != 4800:
        raise RuntimeError(f"expected 4800 official answers, parsed {official_count}")

    type_counts = Counter(x["type"] for x in findings)
    report = {
        "schema_version": 1,
        "official_exam_count": len(EXAMS),
        "official_question_count": official_count,
        "db_question_count": len(db_rows),
        "finding_count": len(findings),
        "finding_types": dict(type_counts),
        "exam_summary": exam_summary,
        "findings": findings,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "historical_answer_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# SWSI × 考選部歷屆答案稽核",
        "",
        f"- 官方考次：{len(EXAMS)}",
        f"- 官方題數：{official_count}",
        f"- Supabase 題數：{len(db_rows)}",
        f"- 非完全一致：{len(findings)}",
        "",
        "## Finding types",
        "",
    ]
    if type_counts:
        for k, v in sorted(type_counts.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 無")
    lines += ["", "## Findings", ""]
    if not findings:
        lines.append("全部與考選部最終答案一致。")
    else:
        lines.append("| Type | 年度 | 考次 | 科目 | 題號 | ID | 平台 | 官方 |")
        lines.append("|---|---:|---|---|---:|---|---|---|")
        for f in findings:
            lines.append(
                f"| {f['type']} | {f['year']} | {f['round']} | {f['subject']} | {f['qno']} | "
                f"{f.get('id') or ''} | {','.join(f.get('db') or [])} | {','.join(f.get('official') or [])} |"
            )
    (output_dir / "historical_answer_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="audit_output")
    args = ap.parse_args()
    try:
        report = audit(Path(args.output_dir))
    except Exception as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "official_questions": report["official_question_count"],
        "findings": report["finding_count"],
        "types": report["finding_types"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
