#!/usr/bin/env python3
"""Fail closed when root and CDN auto-MCQ snapshots disagree on Official Core.

Enrichment/status differences are not used as evidence to upgrade review states.
No external network, provider credentials, or production data are accessed.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    "id", "subject", "year", "round", "qno", "question",
    "opt_a", "opt_b", "opt_c", "opt_d", "answer",
    "accepted_answers", "grading_mode", "source_exam_code", "source_url",
)


def indexed(path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: expected non-empty array")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError(f"{path}: invalid question identity")
        if row["id"] in by_id:
            raise ValueError(f"{path}: duplicate id {row['id']}")
        by_id[row["id"]] = row
    return by_id


def verify(root, cdn):
    if root.keys() != cdn.keys():
        missing = sorted(root.keys() - cdn.keys())
        extra = sorted(cdn.keys() - root.keys())
        raise ValueError(f"auto/CDN MCQ ID mismatch: missing={missing[:5]} extra={extra[:5]}")
    mismatches = []
    for qid in sorted(root):
        for field in FIELDS:
            a, b = root[qid], cdn[qid]
            if (field in a) != (field in b) or a.get(field) != b.get(field):
                mismatches.append((qid, field))
    if mismatches:
        raise ValueError(f"auto/CDN Official Core mismatch: {mismatches[:12]} (total {len(mismatches)})")
    return len(root)


def main():
    count = verify(
        indexed(ROOT / "auto/questions_auto.json"),
        indexed(ROOT / "cdn/auto/questions_auto.json"),
    )
    print(f"AUTO/CDN OFFICIAL CORE PARITY OK: {count} questions")


if __name__ == "__main__":
    main()
