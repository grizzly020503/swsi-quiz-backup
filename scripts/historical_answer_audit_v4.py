#!/usr/bin/env python3
"""Historical answer audit v4: also verify official unanswered-scoring semantics.

v3 already performs the expensive, proven 4,800-question accepted-answer audit
against MOEX per-subject final PDFs. v4 keeps that path intact and enriches each
parsed answer set with one of:

- standard
- all_credit   (official 一律給分; blank also scores)
- any_answer   (除未作答者不給分外，其餘均給分)

The same run then compares all 4,800 database ``grading_mode`` values, so a future
parser regression cannot silently collapse these two special MOEX rules again.
READ-ONLY: this script never writes Supabase.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import requests

import historical_answer_audit as base
import historical_answer_audit_v3 as v3

ALL = {"A", "B", "C", "D"}


class GradedAnswers(set):
    def __init__(self, values=(), grading_mode: str = "standard"):
        super().__init__(values)
        self.grading_mode = grading_mode


def correction_sets_with_modes(text: str, row: str) -> dict[int, GradedAnswers]:
    note = base.compact(text).upper().translate(base.FW)
    accepted: dict[int, GradedAnswers] = {}

    for m in re.finditer(r"第(\d{1,2})題([^第]*)", note):
        qno = int(m.group(1))
        body = m.group(2)
        if not 1 <= qno <= 40:
            continue

        if "一律給分" in body:
            accepted[qno] = GradedAnswers(ALL, "all_credit")
            continue

        if "未作答者不給分" in body and "其餘均給分" in body:
            accepted[qno] = GradedAnswers(ALL, "any_answer")
            continue

        if "給分" in body and "答" in body:
            between = body.split("答", 1)[1].split("給分", 1)[0]
            letters = set(re.findall(r"[ABCD]", between))
            if letters:
                accepted[qno] = GradedAnswers(letters, "standard")

    for qno, ch in enumerate(row, start=1):
        if ch != "#":
            accepted.setdefault(qno, GradedAnswers({ch}, "standard"))
        elif qno not in accepted:
            marker = f"第{qno}題"
            p = note.find(marker)
            excerpt = note[p:p + 160] if p >= 0 else note[:240]
            raise RuntimeError(
                f"q{qno} is # but final correction note grading rule was not parsed; excerpt={excerpt!r}"
            )

    if len(accepted) != 40:
        raise RuntimeError(f"resolved {len(accepted)} / 40 answers with grading modes")
    return accepted


# Keep v3's coordinate/PDF parser, only enrich correction results.
v3.correction_sets = correction_sets_with_modes


def fetch_db_questions_with_grading() -> list[dict]:
    supabase_url, key = base.read_frontend_config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "select": "id,subject,year,round,qno,grading_mode",
            "offset": str(offset),
            "limit": "1000",
            "order": "year.asc,round.asc,subject.asc,qno.asc",
        }
        r = requests.get(
            f"{supabase_url}/rest/v1/questions",
            headers=headers,
            params=params,
            timeout=45,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list):
            raise RuntimeError("Supabase grading-mode response is not a list")
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)
    return rows


def audit_with_grading(output_dir: Path) -> dict:
    official_cache: dict[tuple[str, str, str], dict] = {}
    original_parse = base.parse_official_exam

    def cached_parse(data: bytes, year: str, round_name: str, code: str):
        out = v3.parse_official_exam(data, year, round_name, code)
        official_cache[(year, round_name, code)] = out
        return out

    base.parse_official_exam = cached_parse
    try:
        report = v3.audit_with_multi(output_dir)
    finally:
        base.parse_official_exam = original_parse

    db_rows = fetch_db_questions_with_grading()
    if len(db_rows) != 4800:
        raise RuntimeError(f"expected 4800 DB grading rows, got {len(db_rows)}")

    db = {}
    for r in db_rows:
        key = (str(r["year"]), str(r["round"]), str(r["subject"]), int(r["qno"]))
        if key in db:
            raise RuntimeError(f"duplicate DB grading logical key {key}")
        db[key] = str(r.get("grading_mode") or "")

    official_modes = {}
    for (year, round_name, _code), answers in official_cache.items():
        for (subject, qno), answer_set in answers.items():
            mode = getattr(answer_set, "grading_mode", "standard")
            official_modes[(year, round_name, subject, int(qno))] = mode

    if len(official_modes) != 4800:
        raise RuntimeError(f"expected 4800 official grading modes, got {len(official_modes)}")

    mismatches = []
    for key, official_mode in official_modes.items():
        db_mode = db.get(key)
        if db_mode != official_mode:
            mismatches.append({
                "year": key[0],
                "round": key[1],
                "subject": key[2],
                "qno": key[3],
                "official_grading_mode": official_mode,
                "db_grading_mode": db_mode,
            })

    grading = {
        "official_counts": dict(sorted(Counter(official_modes.values()).items())),
        "db_counts": dict(sorted(Counter(db.values()).items())),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    report["grading_mode_audit"] = grading

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "historical_answer_audit.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_path = output_dir / "historical_answer_audit.md"
    md = md_path.read_text(encoding="utf-8") if md_path.exists() else "# Historical MOEX Answer Audit\n"
    md += "\n## Official grading-mode audit\n\n"
    md += f"- standard: **{grading['official_counts'].get('standard', 0)}**\n"
    md += f"- all_credit（一律給分，空白也得分）: **{grading['official_counts'].get('all_credit', 0)}**\n"
    md += f"- any_answer（未作答不給分，其餘均給分）: **{grading['official_counts'].get('any_answer', 0)}**\n"
    md += f"- grading-mode mismatches: **{grading['mismatch_count']}**\n"
    if mismatches:
        md += "\n### Grading-mode mismatches\n\n"
        for x in mismatches:
            md += (
                f"- {x['year']} {x['round']} / {x['subject']} Q{x['qno']}: "
                f"official `{x['official_grading_mode']}` vs DB `{x['db_grading_mode']}`\n"
            )
    md_path.write_text(md, encoding="utf-8")

    return report


def main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="audit_output")
    args = ap.parse_args()
    try:
        report = audit_with_grading(Path(args.output_dir))
    except Exception as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        return 2

    grading = report["grading_mode_audit"]
    print(json.dumps({
        "official_questions": report["official_question_count"],
        "answer_findings": report["finding_count"],
        "grading_mode_mismatches": grading["mismatch_count"],
        "grading_mode_counts": grading["official_counts"],
    }, ensure_ascii=False))

    return 0 if report["finding_count"] == 0 and grading["mismatch_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
