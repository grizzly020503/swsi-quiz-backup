#!/usr/bin/env python3
"""Read-only quality gate: 'ready' must not mean an empty student explanation.

Checks all official MCQ manifest shards. Does not rewrite records, reclassify
reviews, approve official PDF corrections, or inspect private student data.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
EXPLANATION_FIELDS = ("exp_why", "exp_others", "exp_trap", "exp_raw")


def scan(records: list[dict]) -> tuple[Counter, list[str]]:
    counts: Counter = Counter()
    bad: list[str] = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("MCQ row is not a JSON object")
        status = str(row.get("analysis_status") or "").strip().lower()
        has_explanation = any(str(row.get(k) or "").strip() for k in EXPLANATION_FIELDS)
        counts["total"] += 1
        counts[status or "missing_status"] += 1
        if not has_explanation:
            counts["no_explanation"] += 1
        if status == "ready" and not has_explanation:
            bad.append(str(row.get("id") or "<missing-id>"))
    return counts, bad


def selftest() -> None:
    cases = [
        ({"id": "ok", "analysis_status": "ready", "exp_why": "合理的說明"}, False),
        ({"id": "raw", "analysis_status": "ready", "exp_raw": "原始解析"}, False),
        ({"id": "held", "analysis_status": "review", "exp_why": ""}, False),
        ({"id": "bad", "analysis_status": "ready", "exp_why": ""}, True),
        ({"id": "blank", "analysis_status": "ready", "exp_why": "   "}, True),
    ]
    for record, expected in cases:
        totals, bad = scan([record])
        assert totals["total"] == 1
        assert bool(bad) is expected, (record, bad)
    print("ANALYSIS READY CONTENT GUARD SELFTEST OK")


def run() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    shards = manifest.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("manifest shards missing")
    overall: Counter = Counter()
    bad: list[str] = []
    for shard in shards:
        filename = str(shard.get("file") or "")
        if not filename or Path(filename).name != filename:
            raise ValueError("invalid shard filename")
        source = MANIFEST.parent / filename
        rows = json.loads(source.read_text(encoding="utf-8")).get("questions")
        if not isinstance(rows, list):
            raise ValueError(f"{filename}: missing questions")
        if len(rows) != int(shard.get("question_count") or -1):
            raise ValueError(f"{filename}: question count mismatch")
        current, violations = scan(rows)
        overall.update(current)
        bad.extend(violations)
    expected = int(manifest.get("total_questions") or -1)
    if overall["total"] != expected or len(shards) != int(manifest.get("shard_count") or -1):
        raise ValueError("manifest totals or shard count mismatch")
    print(
        f"ANALYSIS CONTENT QA total={overall['total']} ready={overall['ready']} "
        f"review={overall['review']} no_explanation={overall['no_explanation']} "
        f"ready_without_explanation={len(bad)}"
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fp:
            fp.write(
                "\n## Historical question explanation coverage (read only)\n\n"
                f"- Total: {overall['total']}\n"
                f"- Automated ready (not human verified): {overall['ready']}\n"
                f"- Review: {overall['review']}\n"
                f"- No explanation content: {overall['no_explanation']}\n"
                f"- Misleading ready-without-explanation: {len(bad)}\n\n"
                "Review status and the official PDF review queue stay held. "
                "No question or analysis state is automatically changed.\n"
            )
    if bad:
        raise SystemExit(
            "BLOCK: analysis_status=ready without actual explanation fields: "
            + ", ".join(bad[:10])
            + (f" (+{len(bad)-10} more)" if len(bad) > 10 else "")
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    selftest() if args.selftest else run()
