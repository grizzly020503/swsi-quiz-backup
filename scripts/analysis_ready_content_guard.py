#!/usr/bin/env python3
"""Read-only quality gate: 'ready' must not mean an empty student explanation.

Checks all official MCQ manifest shards. Does not rewrite records, reclassify
reviews, approve official PDF corrections, or inspect private student data.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
EXPLANATION_FIELDS = ("exp_why", "exp_others", "exp_trap", "exp_raw")
STATUSES = {"ready", "review", "pending", "analyzing"}


def scan(records: list[dict]) -> tuple[Counter, list[str]]:
    counts: Counter = Counter()
    bad: list[str] = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("MCQ row is not a JSON object")
        status = row.get("analysis_status")
        if not isinstance(status, str) or status not in STATUSES:
            raise ValueError("missing or invalid analysis_status")
        for field in EXPLANATION_FIELDS:
            if row.get(field) is not None and not isinstance(row[field], str):
                raise ValueError(f"{field}: explanation must be text or null")
        has_explanation = any((row.get(k) or "").strip() for k in EXPLANATION_FIELDS)
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
    for invalid in ({}, [], ["text"], 1, True):
        try:
            scan([{"analysis_status": "ready", "exp_why": invalid}])
        except ValueError:
            pass
        else:
            raise AssertionError(f"non-text explanation accepted: {invalid!r}")
    for status in (None, "", "READY", "done", {}, 1):
        try:
            scan([{"analysis_status": status, "exp_why": "text"}])
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid status accepted: {status!r}")
    for status in STATUSES:
        totals, violations = scan([{"analysis_status": status}])
        assert totals[status] == 1 and totals["no_explanation"] == 1
        assert bool(violations) == (status == "ready")
    # Exercise disk/manifest failures, not only the row predicate. Fixtures
    # never touch the checked-in corpus or the Actions summary.
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        def fixture(rows):
            raw = json.dumps({"questions": rows}).encode()
            (root / "test.json").write_bytes(raw)
            return {"total_questions": len(rows), "shard_count": 1, "shards": [{
                "file": "test.json", "question_count": len(rows),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }]}
        good = {"id": "one", "analysis_status": "ready", "exp_why": "text"}
        for scenario in ("valid", "hash", "duplicate-id", "blank-id", "duplicate-shard", "count"):
            rows = [good, good] if scenario == "duplicate-id" else [dict(good)]
            if scenario == "blank-id":
                rows[0]["id"] = " "
            manifest = fixture(rows)
            if scenario == "hash":
                manifest["shards"][0]["sha256"] = "0" * 64
            if scenario == "duplicate-shard":
                manifest["shards"] *= 2
                manifest.update(total_questions=2, shard_count=2)
            if scenario == "count":
                manifest["total_questions"] += 1
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    run(manifest_path, write_summary=False)
            except ValueError:
                assert scenario != "valid", scenario
            else:
                assert scenario == "valid", scenario
    print("ANALYSIS READY CONTENT GUARD SELFTEST OK")


def run(manifest_path: Path = MANIFEST, *, write_summary: bool = True) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shards = manifest.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("manifest shards missing")
    overall: Counter = Counter()
    bad: list[str] = []
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    for shard in shards:
        filename = str(shard.get("file") or "")
        if not filename or Path(filename).name != filename:
            raise ValueError("invalid shard filename")
        if filename in seen_files:
            raise ValueError("duplicate shard filename")
        seen_files.add(filename)
        source = manifest_path.parent / filename
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != shard.get("sha256"):
            raise ValueError(f"{filename}: SHA-256 mismatch")
        rows = json.loads(raw).get("questions")
        if not isinstance(rows, list):
            raise ValueError(f"{filename}: missing questions")
        if len(rows) != int(shard.get("question_count") or -1):
            raise ValueError(f"{filename}: question count mismatch")
        current, violations = scan(rows)
        for row in rows:
            ident = row.get("id")
            if not isinstance(ident, str) or not ident.strip() or ident != ident.strip() or ident in seen_ids:
                raise ValueError(f"{filename}: missing, invalid or duplicate question ID")
            seen_ids.add(ident)
        overall.update(current)
        bad.extend(violations)
    expected = int(manifest.get("total_questions") or -1)
    if overall["total"] != expected or len(shards) != int(manifest.get("shard_count") or -1):
        raise ValueError("manifest totals or shard count mismatch")
    print(
        f"ANALYSIS CONTENT QA total={overall['total']} ready={overall['ready']} "
        f"review={overall['review']} pending={overall['pending']} analyzing={overall['analyzing']} "
        f"no_explanation={overall['no_explanation']} "
        f"ready_without_explanation={len(bad)}"
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY") if write_summary else None
    if summary:
        with open(summary, "a", encoding="utf-8") as fp:
            fp.write(
                "\n## Historical question explanation coverage (read only)\n\n"
                f"- Total: {overall['total']}\n"
                f"- Automated ready (not human verified): {overall['ready']}\n"
                f"- Review: {overall['review']}\n"
                f"- Pending / analyzing: {overall['pending']} / {overall['analyzing']}\n"
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
