#!/usr/bin/env python3
"""Synchronize the compact historical-law student map with verified evidence.

The browser must not carry article full text, hashes, semantic scores, protected
question fields, or a runtime network dependency. This script deterministically
projects the 13 machine-verified + evidence-adjudicated verified records into the
existing private HISTORICAL_VERIFIED map owned by 86.law-trust-ui.part.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import historical_law_evidence_adjudication as evidence

ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "monthly_patch_parts" / "86.law-trust-ui.part"
MAP_RE = re.compile(r"var HISTORICAL_VERIFIED=(\{.*?\});\n\n  function H", re.S)
ALLOWED_LEVELS = {
    evidence.MACHINE_LEVEL,
    evidence.ADJUDICATED_LEVEL,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_combined() -> dict:
    return evidence.build_combined_registry(
        load_json(evidence.DEFAULT_MACHINE),
        load_json(evidence.DEFAULT_ADJUDICATION),
        load_json(evidence.DEFAULT_EVIDENCE_SNAPSHOT),
        load_json(evidence.DEFAULT_LINKS),
        evidence.load_question_shards(evidence.DEFAULT_SHARDS),
    )


def build_student_map() -> dict[str, dict]:
    combined = build_combined()
    out: dict[str, dict] = {}
    for row in combined.get("records") or []:
        qid = str(row.get("question_id") or "").strip()
        level = str(row.get("verification_level") or "").strip()
        if not qid or qid in out:
            raise ValueError(f"invalid/duplicate student historical-law question id: {qid!r}")
        if row.get("historical_version_checked") is not True or level not in ALLOWED_LEVELS:
            raise ValueError(f"student projection received unverified/unknown row: {qid}")
        version = row.get("selected_version") or {}
        compact = {
            "law_name": row.get("law_name"),
            "exam_code": row.get("exam_code"),
            "article": row.get("article"),
            "historical_version_checked": True,
            "verification_level": level,
            "selected_version": {
                "version_date": version.get("version_date"),
                "effective_date": version.get("effective_date"),
                "url": version.get("url"),
            },
            "official_history_url": row.get("official_history_url"),
            "exam_date_source_url": row.get("exam_date_source_url"),
        }
        # Browser data minimization is deliberate. Never carry evidence internals.
        forbidden = {
            "historical_article_sha256",
            "historical_semantic",
            "verification_basis",
            "evidence_adjudication",
            "stem",
            "question",
            "options",
            "official_answer",
            "answer",
            "accepted_answers",
            "grading_mode",
        }
        if forbidden & set(compact):
            raise ValueError(f"forbidden student projection field: {qid}")
        out[qid] = compact

    counts = combined.get("verification_level_counts") or {}
    if len(out) != int(combined.get("verified_record_count") or -1):
        raise ValueError("student projection count drift")
    if counts != {
        evidence.MACHINE_LEVEL: 13,
        evidence.ADJUDICATED_LEVEL: 6,
    }:
        raise ValueError(f"unexpected verification-level counts: {counts}")
    return dict(sorted(out.items()))


def extract_embedded(ui_text: str) -> dict:
    match = MAP_RE.search(ui_text)
    if not match:
        raise ValueError("historical runtime map missing from law trust owner")
    return json.loads(match.group(1))


def rendered_assignment() -> str:
    payload = json.dumps(build_student_map(), ensure_ascii=False, separators=(",", ":"))
    return f"var HISTORICAL_VERIFIED={payload};\n\n  function H"


def sync(ui_path: Path) -> None:
    text = ui_path.read_text(encoding="utf-8")
    if not MAP_RE.search(text):
        raise ValueError("historical runtime map missing from law trust owner")
    updated = MAP_RE.sub(rendered_assignment(), text, count=1)
    ui_path.write_text(updated, encoding="utf-8")


def check(ui_path: Path) -> None:
    actual = extract_embedded(ui_path.read_text(encoding="utf-8"))
    expected = build_student_map()
    if actual != expected:
        raise SystemExit(
            "historical-law student map drift: run "
            "python scripts/historical_law_student_surface_sync.py --write"
        )
    print(
        "HISTORICAL LAW STUDENT MAP SYNC OK: "
        f"records={len(actual)} machine=13 evidence_adjudicated=6"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ui", type=Path, default=UI_PATH)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.write:
        sync(args.ui)
    if args.check or not args.write:
        check(args.ui)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
