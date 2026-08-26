#!/usr/bin/env python3
"""Protect official past-exam question wording from accidental edits.

This guard intentionally locks only official exam facts/text, not SWSI-authored
analysis, explanations, tags, guide content, or UI metadata.

Locked MCQ fields:
  id, subject, year, round, qno, question, opt_a, opt_b, opt_c, opt_d
Locked essay fields:
  id, subject, year, round, qno, q, points

New official question IDs are allowed (for future MOEX syncs), but every ID
already present in the committed lock must remain byte-for-byte equivalent at
the canonical JSON field level.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "data" / "official_exam_readonly.lock.json"
INDEX_PATH = ROOT / "index.html"
AUTO_ESSAYS_PATH = ROOT / "auto" / "essays_auto.json"
SHARD_DIR = ROOT / "cdn" / "question-shards"

MCQ_FIELDS = ("id", "subject", "year", "round", "qno", "question", "opt_a", "opt_b", "opt_c", "opt_d")
ESSAY_FIELDS = ("id", "subject", "year", "round", "qno", "q", "points")


def canonical_row(row: dict, fields: tuple[str, ...]) -> dict:
    return {key: row.get(key) for key in fields}


def row_hash(row: dict) -> str:
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_official_essay(row: dict) -> bool:
    subject = str(row.get("subject") or "")
    ident = str(row.get("id") or "")
    return subject != "時事預測題" and not ident.startswith("時事-")


def extract_embedded_essays() -> list[dict]:
    text = INDEX_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"window\.ESSAYS\s*=\s*(\[.*?\]);\s*\n\s*window\.CLUSTER_ANCHORS",
        text,
        flags=re.S,
    )
    if not match:
        raise RuntimeError("Could not locate window.ESSAYS JSON in index.html")
    data = json.loads(match.group(1))
    if not isinstance(data, list):
        raise RuntimeError("window.ESSAYS is not a JSON array")
    return [row for row in data if isinstance(row, dict) and is_official_essay(row)]


def load_auto_essays() -> list[dict]:
    if not AUTO_ESSAYS_PATH.exists():
        return []
    data = json.loads(AUTO_ESSAYS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("auto/essays_auto.json is not a JSON array")
    return [row for row in data if isinstance(row, dict) and is_official_essay(row)]


def collect_essays() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for source_row in extract_embedded_essays() + load_auto_essays():
        canonical = canonical_row(source_row, ESSAY_FIELDS)
        ident = str(canonical.get("id") or "").strip()
        if not ident:
            raise RuntimeError("Official essay row without id")
        if ident in rows and rows[ident] != canonical:
            raise RuntimeError(f"Conflicting official essay rows for {ident}")
        rows[ident] = canonical
    return rows


def collect_mcq() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    shard_paths = sorted(SHARD_DIR.glob("[0-9][0-9][0-9]-[12].json"))
    if not shard_paths:
        raise RuntimeError("No official MCQ shards found")
    for path in shard_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        questions = payload.get("questions") if isinstance(payload, dict) else None
        if not isinstance(questions, list):
            raise RuntimeError(f"Invalid questions array in {path}")
        for source_row in questions:
            if not isinstance(source_row, dict):
                continue
            canonical = canonical_row(source_row, MCQ_FIELDS)
            ident = str(canonical.get("id") or "").strip()
            if not ident:
                raise RuntimeError(f"MCQ row without id in {path}")
            if ident in rows and rows[ident] != canonical:
                raise RuntimeError(f"Conflicting MCQ rows for {ident}")
            rows[ident] = canonical
    return rows


def build_snapshot() -> dict:
    mcq = collect_mcq()
    essays = collect_essays()
    return {
        "schema_version": 1,
        "purpose": "Lock official past-exam wording only; SWSI-authored analysis/UI remains editable.",
        "mcq_count": len(mcq),
        "essay_count": len(essays),
        "mcq": {ident: row_hash(row) for ident, row in sorted(mcq.items())},
        "essays": {ident: row_hash(row) for ident, row in sorted(essays.items())},
    }


def write_snapshot() -> int:
    snapshot = build_snapshot()
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE OFFICIAL EXAM LOCK: MCQ={snapshot['mcq_count']} ESSAY={snapshot['essay_count']} -> {LOCK_PATH}")
    return 0


def check_snapshot() -> int:
    if not LOCK_PATH.exists():
        print(f"ERROR: lock file missing: {LOCK_PATH}", file=sys.stderr)
        return 2
    locked = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    current = build_snapshot()
    failures: list[str] = []
    additions: list[str] = []

    for section in ("mcq", "essays"):
        locked_rows = locked.get(section, {})
        current_rows = current.get(section, {})
        if not isinstance(locked_rows, dict) or not isinstance(current_rows, dict):
            failures.append(f"invalid lock section: {section}")
            continue
        for ident, expected_hash in locked_rows.items():
            actual_hash = current_rows.get(ident)
            if actual_hash is None:
                failures.append(f"{section}: locked official question missing: {ident}")
            elif actual_hash != expected_hash:
                failures.append(f"{section}: OFFICIAL QUESTION CHANGED: {ident}")
        additions.extend(f"{section}:{ident}" for ident in current_rows.keys() - locked_rows.keys())

    if failures:
        print("OFFICIAL EXAM READ-ONLY GUARD FAILED", file=sys.stderr)
        for item in failures:
            print(f" - {item}", file=sys.stderr)
        print("Do not edit historical official question wording. If MOEX officially corrected a source question, review it explicitly before refreshing the lock.", file=sys.stderr)
        return 1

    print(f"OFFICIAL EXAM READ-ONLY GUARD OK: locked MCQ={len(locked.get('mcq', {}))}, essays={len(locked.get('essays', {}))}")
    if additions:
        print(f"INFO: {len(additions)} new official question IDs are not locked yet (allowed for new exam syncs).")
        for item in additions[:20]:
            print(f" + {item}")
        if len(additions) > 20:
            print(f" + ... and {len(additions)-20} more")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true", help="Write/refresh the baseline lock after explicit review")
    args = parser.parse_args()
    return write_snapshot() if args.snapshot else check_snapshot()


if __name__ == "__main__":
    raise SystemExit(main())
