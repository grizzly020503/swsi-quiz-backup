#!/usr/bin/env python3
"""Run unified question QA across every manifest session.

This is a read-only full-corpus audit. It verifies shard existence/hash/count,
then delegates each session to the existing unified_question_qa.py contract.
No official question data or enrichment is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "cdn" / "question-shards" / "manifest.json"
DEFAULT_ESSAYS = ROOT / "auto" / "essays_auto.json"
DEFAULT_POLICY = ROOT / "data" / "question_qa_policy_v1.json"
UNIFIED_QA = ROOT / "scripts" / "unified_question_qa.py"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def question_count(payload: Any) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        return len(payload["questions"])
    if isinstance(payload, list):
        return len(payload)
    raise ValueError("shard must be an object with questions[] or a list")


def normalize_round(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in {"1", "第一次", "第一試"}:
        return "第一次"
    if raw in {"2", "第二次", "第二試"}:
        return "第二次"
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="SWSI manifest-wide unified question QA")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--essays", type=Path, default=DEFAULT_ESSAYS)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on", choices=["never", "blocked", "review"], default="blocked")
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    shards = manifest.get("shards") if isinstance(manifest, dict) else None
    if not isinstance(shards, list) or not shards:
        raise SystemExit("manifest shards[] is empty or invalid")

    shard_root = args.manifest.parent
    manifest_errors: list[str] = []
    sessions: list[dict] = []
    seen_sessions: set[tuple[str, str]] = set()
    seen_files: set[str] = set()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for index, entry in enumerate(shards):
            if not isinstance(entry, dict):
                manifest_errors.append(f"shards[{index}] is not an object")
                continue
            year = str(entry.get("year") or "").strip()
            round_name = normalize_round(entry.get("round"))
            filename = str(entry.get("file") or "").strip()
            key = (year, round_name)
            if not year or round_name not in {"第一次", "第二次"}:
                manifest_errors.append(
                    f"invalid session metadata at shards[{index}]: {year!r} {round_name!r}"
                )
                continue
            if key in seen_sessions:
                manifest_errors.append(f"duplicate manifest session: {year}-{round_name}")
                continue
            seen_sessions.add(key)
            if not filename or filename in seen_files:
                manifest_errors.append(f"missing or duplicate manifest file: {filename!r}")
                continue
            seen_files.add(filename)

            shard_path = shard_root / filename
            if not shard_path.is_file():
                manifest_errors.append(f"missing shard file: {shard_path}")
                continue

            expected_hash = str(entry.get("sha256") or "").strip().lower()
            actual_hash = sha256(shard_path)
            if expected_hash and actual_hash != expected_hash:
                manifest_errors.append(
                    f"{filename}: sha256 mismatch expected={expected_hash} actual={actual_hash}"
                )

            try:
                actual_count = question_count(read_json(shard_path))
            except Exception as exc:
                manifest_errors.append(f"{filename}: cannot read questions: {exc}")
                continue
            expected_count = int(entry.get("question_count") or 0)
            if expected_count and actual_count != expected_count:
                manifest_errors.append(
                    f"{filename}: question_count mismatch expected={expected_count} actual={actual_count}"
                )

            session_out = tmp / f"{year}-{1 if round_name == '第一次' else 2}.json"
            command = [
                sys.executable,
                str(UNIFIED_QA),
                "--mcq",
                str(shard_path),
                "--essays",
                str(args.essays),
                "--year",
                year,
                "--round",
                round_name,
                "--policy",
                str(args.policy),
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
                    f"{year}-{round_name}: unified QA process failed rc={proc.returncode}: "
                    f"{proc.stderr.strip()[:500]}"
                )
                continue

            report = read_json(session_out)
            overall = report.get("overall") or {}
            official = overall.get("official_core") or {}
            enrichment = overall.get("enrichment") or {}
            sessions.append(
                {
                    "year": year,
                    "round": round_name,
                    "file": filename,
                    "mcq_count": actual_count,
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
            )

    total_items = sum(row["items"] for row in sessions)
    total_blocked = sum(row["official_core"]["blocked"] for row in sessions)
    total_review = sum(row["manual_review_queue_count"] for row in sessions)
    report = {
        "schema_version": 1,
        "dataset_revision": manifest.get("dataset_revision"),
        "manifest_shard_count": int(manifest.get("shard_count") or len(shards)),
        "audited_sessions": len(sessions),
        "manifest_errors": manifest_errors,
        "summary": {
            "total_items": total_items,
            "official_blocked": total_blocked,
            "manual_review_queue_count": total_review,
            "all_manifest_sessions_audited": len(sessions) == len(shards),
            "manifest_integrity_ok": not manifest_errors,
        },
        "sessions": sessions,
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    blocked = bool(manifest_errors) or total_blocked > 0 or len(sessions) != len(shards)
    review = total_review > 0
    if args.fail_on == "blocked" and blocked:
        return 2
    if args.fail_on == "review" and (blocked or review):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
