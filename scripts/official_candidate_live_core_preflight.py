#!/usr/bin/env python3
"""Three-way, read-only Official Core parity: pinned main vs candidate vs live.

No Official Core corrections, SQL writes, publish, human approval, private data,
or automatic rollback. The only network mode uses existing anonymous SELECT.
Compare the exact per-question lock hashes (not heuristic language similarity).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash, ROOT
from official_option_scenario_guard import read_rows, validate_live_baseline

BASELINE_COMMIT = "62fed9b5a3e7b6bd770886bfc9fe6b6ce3ce1576"
LOCK_PATH = "data/official_exam_readonly.lock.json"
GRADING_FIELDS = ("answer", "accepted_answers", "grading_mode")
EXPECTED_CHANGED = 43
ESSAY_ID = "社會工作-112-2-申論2"
ESSAY_PROOF = ROOT / "audit/official_essay_112_2_sw2_correction.json"


def read_pinned_lock(root: Path = ROOT, commit: str = BASELINE_COMMIT) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("baseline commit must be an exact SHA")
    proc = subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{LOCK_PATH}"],
        cwd=root, capture_output=True, check=False, timeout=20,
    )
    if proc.returncode:
        raise ValueError("pinned baseline lock not available; fetch exact reviewed commit")
    return json.loads(proc.stdout)


def current_lock(root: Path = ROOT) -> dict:
    return json.loads((root / LOCK_PATH).read_text(encoding="utf-8"))


def unique(rows: list[dict], label: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    if not isinstance(rows, list):
        raise ValueError(label + " must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(label + " contains non-question")
        ident = row.get("id")
        if not isinstance(ident, str) or not ident or ident in indexed:
            raise ValueError(label + " has missing/duplicate ID")
        if any(field not in row for field in (*MCQ_FIELDS, *GRADING_FIELDS)):
            raise ValueError(label + f" missing required Official Core or grading: {ident}")
        indexed[ident] = row
    return indexed


def check(
    baseline: dict, candidate_lock: dict,
    candidate_rows: list[dict], live_rows: list[dict],
    expected_changes: int = EXPECTED_CHANGED,
) -> dict:
    old, new = baseline.get("mcq"), candidate_lock.get("mcq")
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ValueError("official lock mcq maps required")
    essay_before, essay_after = baseline.get("essays"), candidate_lock.get("essays")
    if (len(old) != 4800 or set(old) != set(new)
            or not isinstance(essay_before, dict) or not isinstance(essay_after, dict)
            or len(essay_before) != 240 or set(essay_before) != set(essay_after)):
        raise ValueError("pinned official lock coverage/essay lock mismatch")
    # The candidate includes one already documented official essay typo/wrong-stem
    # correction, not zero. The exact official PDF proof must bind both hashes.
    essay_changes = {ident for ident in essay_before if essay_before[ident] != essay_after[ident]}
    proof = json.loads(ESSAY_PROOF.read_text(encoding="utf-8"))
    if (essay_changes != {ESSAY_ID} or proof.get("id") != ESSAY_ID
            or proof.get("status") != "CONTROLLED_OFFICIAL_CORE_CORRECTION_CANDIDATE"
            or proof.get("human_approval") is not False
            or proof.get("before_lock_sha256") != essay_before[ESSAY_ID]
            or proof.get("after_lock_sha256") != essay_after[ESSAY_ID]):
        raise ValueError("unreviewed official essay delta or proof-hash mismatch")
    changes = {ident for ident in old if old[ident] != new[ident]}
    if len(changes) != expected_changes:
        raise ValueError(f"unreviewed Official Core candidate change scope: {len(changes)}")
    proposed, live = unique(candidate_rows, "candidate"), unique(live_rows, "live")
    if set(proposed) != set(old) or set(live) != set(old):
        raise ValueError("candidate/live historical question IDs differ from pinned 4800")
    for ident, row in proposed.items():
        if row_hash(canonical_row(row, MCQ_FIELDS)) != new[ident]:
            raise ValueError("candidate Official Core disagrees with own lock: " + ident)

    before, after, unexpected, grade_drift = [], [], [], []
    for ident in sorted(old):
        row, target = live[ident], proposed[ident]
        live_sha = row_hash(canonical_row(row, MCQ_FIELDS))
        if any(row[field] != target[field] for field in GRADING_FIELDS):
            grade_drift.append(ident)
        if old[ident] == new[ident]:
            if live_sha != old[ident]:
                unexpected.append(ident)
        elif live_sha == old[ident]:
            before.append(ident)
        elif live_sha == new[ident]:
            after.append(ident)
        else:
            unexpected.append(ident)
    state = ("DRIFT" if unexpected or grade_drift
             else "MIXED_PARTIAL" if before and after
             else "BEFORE_ONLY" if before
             else "AFTER_ONLY")
    return {
        "schema_version": 1,
        "baseline_ref": BASELINE_COMMIT,
        "historical_questions": 4800,
        "official_essay_count": 240,
        "candidate_changed_official_essay": len(essay_changes),
        "essay_live_parity": "NOT_CHECKED_REQUIRE_SEPARATE_OFFICIAL_ESSAY_REVIEW",
        "candidate_changed_official_core": len(changes),
        "live_pending_exact_core": len(before),
        "live_already_at_candidate_core": len(after),
        "live_unexpected_core_drift": len(unexpected),
        "live_grading_difference": len(grade_drift),
        "live_state": state,
        "pending_ids": before,
        "already_applied_ids": after,
        "unexpected_ids": unexpected,
        "grading_difference_ids": grade_drift,
        "official_core_modified": False,
        "production_written": False,
        "release_approved": False,
        "release_status": "HOLD_SOURCE_AI_HUMAN_AND_CONTROLLED_DEPLOY",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-ref", default=BASELINE_COMMIT)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true", help="explicit public anon SELECT; zero writes")
    source.add_argument("--input", type=Path, help="offline JSON list of production-shaped questions")
    p.add_argument("--out", type=Path)
    p.add_argument("--fail-on-drift", action="store_true")
    args = p.parse_args()
    old_lock = read_pinned_lock(commit=args.baseline_ref)
    if args.live:
        from build_question_shards import fetch_questions
        rows = fetch_questions()
    else:
        rows = json.loads(args.input.read_text(encoding="utf-8"))
    validate_live_baseline(rows)
    # The three-way candidate is limited to its reviewed 4,800 historical rows.
    historical = [r for r in rows if str(r.get("year") or "") in
                  {str(y) for y in range(104, 116)}]
    result = check(old_lock, current_lock(), read_rows(), historical)
    result["baseline_ref"] = args.baseline_ref
    result["mode"] = "live_public_anon_select" if args.live else "offline_fixture"
    if args.out:
        dest = args.out.resolve()
        if dest == ROOT or ROOT in dest.parents:
            raise SystemExit("REFUSED: output inside repository")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("_ids")}, ensure_ascii=False))
    return 2 if args.fail_on_drift and result["live_state"] in {"DRIFT", "MIXED_PARTIAL"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
