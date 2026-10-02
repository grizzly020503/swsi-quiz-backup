#!/usr/bin/env python3
"""Audit one manifest exam session using the existing Full Corpus/Unified QA owners.

This is the per-session execution primitive for #274 resume/checkpoint wiring.
It reuses full_corpus_qa.py for source/hash/essay helpers and
unified_question_qa.py for the actual QA. It never mutates Official Core.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from full_corpus_ops_plan import manifest_units
from full_corpus_qa import (
    DEFAULT_MANIFEST,
    DEFAULT_POLICY,
    ROOT,
    UNIFIED_QA,
    collect_full_essays,
    question_count,
    read_json,
    session_key,
    sha256,
)


def select_unit(manifest: Any, policy: dict[str, Any], requested_unit: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_unit = str(requested_unit or "").strip()
    if not requested_unit:
        raise ValueError("unit id is required")
    units = manifest_units(manifest, policy)
    matches = [row for row in units if row["unit_id"] == requested_unit]
    if len(matches) != 1:
        raise ValueError(f"unit is not in current manifest: {requested_unit}")
    return units, matches[0]


def validate_manifest_files(
    units: list[dict[str, Any]],
    shard_root: Path,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    counts: dict[str, int] = {}
    for row in units:
        path = shard_root / row["file"]
        if not path.is_file():
            errors.append(f"missing shard file: {path}")
            continue
        actual_hash = sha256(path)
        if row["sha256"] and actual_hash != row["sha256"]:
            errors.append(
                f"{row['file']}: sha256 mismatch expected={row['sha256']} actual={actual_hash}"
            )
        try:
            actual_count = question_count(read_json(path))
        except Exception as exc:
            errors.append(f"{row['file']}: cannot read questions: {exc}")
            continue
        counts[row["unit_id"]] = actual_count
        if row["question_count"] and actual_count != row["question_count"]:
            errors.append(
                f"{row['file']}: question_count mismatch "
                f"expected={row['question_count']} actual={actual_count}"
            )
    return errors, counts


def audit_unit(
    requested_unit: str,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    policy = read_json(policy_path)
    units, selected = select_unit(manifest, policy, requested_unit)
    manifest_errors, counts = validate_manifest_files(units, manifest_path.parent)

    try:
        all_essays = collect_full_essays()
    except Exception as exc:
        raise RuntimeError(f"cannot build canonical essay corpus: {exc}") from exc

    essay_counts = Counter(session_key(row, policy) for row in all_essays)
    manifest_keys = {(row["year"], row["round"]) for row in units}
    bad_essay_sessions = sorted(
        f"{year}-{round_name}"
        for (year, round_name) in essay_counts
        if not year or round_name not in {"第一次", "第二次"}
    )
    if bad_essay_sessions:
        manifest_errors.append(
            "essay rows with invalid session metadata: " + ", ".join(bad_essay_sessions)
        )
    extra_essay_sessions = sorted(
        f"{year}-{round_name}"
        for (year, round_name) in essay_counts
        if (year, round_name) not in manifest_keys
    )
    if extra_essay_sessions:
        manifest_errors.append(
            "official essays exist outside manifest sessions: " + ", ".join(extra_essay_sessions)
        )

    shard_path = manifest_path.parent / selected["file"]
    actual_count = counts.get(selected["unit_id"])
    session_result: dict[str, Any] | None = None

    if actual_count is not None and shard_path.is_file():
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            essays_path = tmp / "official-essays-full.json"
            essays_path.write_text(
                json.dumps(all_essays, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            session_out = tmp / "session.json"
            command = [
                sys.executable,
                str(UNIFIED_QA),
                "--mcq",
                str(shard_path),
                "--essays",
                str(essays_path),
                "--year",
                selected["year"],
                "--round",
                selected["round"],
                "--policy",
                str(policy_path),
                "--out",
                str(session_out),
                "--fail-on",
                "never",
            ]
            proc = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
            )
            if proc.returncode != 0:
                manifest_errors.append(
                    f"{selected['unit_id']}: unified QA process failed rc={proc.returncode}: "
                    f"{proc.stderr.strip()[:500]}"
                )
            elif not session_out.is_file():
                manifest_errors.append(
                    f"{selected['unit_id']}: unified QA did not produce a report"
                )
            else:
                report = read_json(session_out)
                overall = report.get("overall") or {}
                official = overall.get("official_core") or {}
                enrichment = overall.get("enrichment") or {}
                key = (selected["year"], selected["round"])
                session_result = {
                    "year": selected["year"],
                    "round": selected["round"],
                    "unit_id": selected["unit_id"],
                    "file": selected["file"],
                    "mcq_count": actual_count,
                    "essay_count": essay_counts.get(key, 0),
                    "items": int(overall.get("items") or 0),
                    "official_core": {
                        "passed": int(official.get("passed") or 0),
                        "needs_review": int(official.get("needs_review") or 0),
                        "blocked": int(official.get("blocked") or 0),
                        "release_ready": bool(official.get("release_ready")),
                    },
                    "enrichment": {
                        "passed": int(enrichment.get("passed") or 0),
                        "needs_review": int(enrichment.get("needs_review") or 0),
                        "blocked": int(enrichment.get("blocked") or 0),
                        "pending_generation": int(enrichment.get("pending_generation") or 0),
                    },
                    "manual_review_queue_count": int(
                        overall.get("manual_review_queue_count") or 0
                    ),
                }
                expected_items = session_result["mcq_count"] + session_result["essay_count"]
                if session_result["items"] != expected_items:
                    manifest_errors.append(
                        f"{selected['unit_id']}: item mismatch "
                        f"unified={session_result['items']} source={expected_items}"
                    )

    official_blocked = (
        int(session_result["official_core"]["blocked"]) if session_result else 0
    )
    manual_review = (
        int(session_result["manual_review_queue_count"]) if session_result else 0
    )
    return {
        "schema_version": 1,
        "audit_scope": "single_manifest_session",
        "dataset_revision": manifest.get("dataset_revision"),
        "manifest_shard_count": len(units),
        "unit_id": selected["unit_id"],
        "manifest_errors": manifest_errors,
        "summary": {
            "session_audited": session_result is not None,
            "official_blocked": official_blocked,
            "manual_review_queue_count": manual_review,
            "manifest_integrity_ok": not manifest_errors,
        },
        "session": session_result,
    }


def self_test() -> dict[str, Any]:
    policy = {"round_aliases": {}}
    manifest = {
        "shard_count": 2,
        "shards": [
            {"year": "115", "round": "第一次", "file": "115-1.json"},
            {"year": "115", "round": "第二次", "file": "115-2.json"},
        ],
    }
    units, selected = select_unit(manifest, policy, "115-第二次")
    assert len(units) == 2
    assert selected["file"] == "115-2.json"
    try:
        select_unit(manifest, policy, "116-第一次")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown unit must fail closed")
    return {"ok": True, "unit_selection": True, "unknown_unit_fail_closed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit one Full Corpus manifest session")
    parser.add_argument("--unit")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on", choices=["never", "blocked", "review"], default="blocked")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.unit:
        raise SystemExit("--unit is required unless --self-test is used")

    try:
        report = audit_unit(args.unit, manifest_path=args.manifest, policy_path=args.policy)
    except Exception as exc:
        raise SystemExit(f"single-session audit failed closed: {exc}") from exc

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    blocked = (
        bool(report["manifest_errors"])
        or not report["summary"]["session_audited"]
        or int(report["summary"]["official_blocked"]) > 0
    )
    review = int(report["summary"]["manual_review_queue_count"]) > 0
    if args.fail_on == "blocked" and blocked:
        return 2
    if args.fail_on == "review" and (blocked or review):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
