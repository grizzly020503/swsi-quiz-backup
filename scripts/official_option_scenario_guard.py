#!/usr/bin/env python3
"""Read-only heuristic for scenario passages accidentally swallowed by MCQ choices.

A match is a *risk signal*, never proof of the authoritative wording. The rule
must not rewrite the official question, context, options, grading or metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASE_LABEL = re.compile(r"(?:情況|情境|共同情境|共同題組)\s*[:：]")
FOLLOWUP = re.compile(
    r"(?:請依|請根據|請依照|根據|依據).{0,170}?"
    r"(?:回答(?:下列|以下)?|作答(?:下列|以下)?|第\s*[\d一二三四五六七八九十]*\s*題\s*至\s*第\s*[\d一二三四五六七八九十]*\s*題)",
    re.S,
)
NEXT_RANGE = re.compile(
    r"(?:第\s*[\d一二三四五六七八九十]*\s*題\s*至\s*第\s*[\d一二三四五六七八九十]*\s*題|回答下列第.{0,25}題)",
    re.S,
)
FIELDS = ("opt_a", "opt_b", "opt_c", "opt_d")


def read_rows(root: Path = ROOT) -> list[dict[str, Any]]:
    base = root / "cdn" / "question-shards"
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    shards = manifest.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("manifest shards[] missing")
    seen_files: set[str] = set()
    seen_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in shards:
        if not isinstance(item, dict):
            raise ValueError("manifest shard must be an object")
        name = item.get("file")
        if (not isinstance(name, str) or not name.endswith(".json")
                or Path(name).name != name or name in seen_files):
            raise ValueError("unsafe/duplicate manifest shard filename")
        seen_files.add(name)
        raw = (base / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item.get("sha256"):
            raise ValueError(f"manifest SHA-256 mismatch: {name}")
        data = json.loads(raw)
        entries = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(entries, list) or len(entries) != item.get("question_count"):
            raise ValueError(f"incorrect shard question count: {name}")
        for row in entries:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                raise ValueError(f"malformed question in {name}")
            if row["id"] in seen_ids:
                raise ValueError(f"duplicate MCQ identity {row['id']}")
            seen_ids.add(row["id"])
            rows.append(row)
    if len(rows) != manifest.get("total_questions"):
        raise ValueError("manifest total question count mismatch")
    return rows


def scan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for row in rows:
        ident = row.get("id")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("invalid/duplicate question ID")
        seen.add(ident)
        for field in FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{ident}: missing or invalid {field}")
            total += 1
            has_case = bool(CASE_LABEL.search(value))
            has_followup = bool(FOLLOWUP.search(value))
            has_range = bool(NEXT_RANGE.search(value))
            flags = []
            if has_case:
                flags.append("case_label_inside_option")
            if has_followup:
                flags.append("next_question_directive_inside_option")
            if has_range:
                flags.append("question_range_inside_option")
            if len(value) > 260:
                flags.append("long_option_review")
            # Both a case-label and a dependent-questions directive is strong
            # enough to stop a release for expert review, not to auto-edit.
            blocking = has_case and (has_followup or has_range)
            if flags:
                risks.append({
                    "id": ident, "field": field, "year": row.get("year"),
                    "round": row.get("round"), "subject": row.get("subject"),
                    "flags": flags, "blocking": blocking,
                    "review_required": True, "automatic_edit": False,
                    "release_approval": False,
                })
    risks.sort(key=lambda item: (not item["blocking"], item["id"], item["field"]))
    return {
        "schema_version": 1, "scope": "heuristic option-boundary triage only",
        "scanned_questions": len(seen), "scanned_options": total,
        "blocking_suspicions": sum(r["blocking"] for r in risks),
        "review_signals": len(risks),
        "release_approval": False, "official_core_modified": False,
        "risks": risks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="write diagnostic JSON outside repo")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()
    result = scan(read_rows())
    if args.out:
        dest = args.out.resolve()
        if dest == ROOT or ROOT in dest.parents:
            raise SystemExit("REFUSED: audit report output inside repo")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "risks"}, ensure_ascii=False))
    return 2 if args.fail_on_blocked and result["blocking_suspicions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
