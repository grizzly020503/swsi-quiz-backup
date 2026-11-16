#!/usr/bin/env python3
"""Diagnose official MOEX essay re-extraction changes before any remote sync.

Read-only: compares regenerated incoming/*.json with the committed HEAD
versions. Even whitespace-only changes remain blocking, never auto-approved.
Only public official essay question fields are included in diagnostics.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FIELDS = ("id", "subject", "year", "round", "qno", "q", "points")


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def indexed(payload: dict, *, label: str) -> dict[str, dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("essays"), list):
        raise ValueError(f"{label}: essays[] must exist")
    result: dict[str, dict] = {}
    for row in payload["essays"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError(f"{label}: invalid official essay row")
        ident = row["id"]
        if ident in result:
            raise ValueError(f"{label}: duplicate official essay ID {ident}")
        result[ident] = row
    return result


def delta_hint(old: object, new: object) -> dict:
    left = str(old if old is not None else "")
    right = str(new if new is not None else "")
    spans = [op for op in difflib.SequenceMatcher(
        None, left, right, autojunk=False
    ).get_opcodes() if op[0] != "equal"]
    samples = []
    for tag, i, j, a, b in spans[:4]:
        samples.append({
            "operation": tag,
            "before": left[max(0, i - 20):min(len(left), j + 20)],
            "after": right[max(0, a - 20):min(len(right), b + 20)],
        })
    return {
        "before_sha256": digest(old),
        "after_sha256": digest(new),
        "before_length": len(left),
        "after_length": len(right),
        # Forensics only: this indicator never makes a change acceptable.
        "possible_layout_whitespace_only": (
            left != right and re.sub(r"\\s+", "", left) == re.sub(r"\\s+", "", right)
        ),
        "edit_count": len(spans),
        "edit_samples": samples,
    }


def compare(previous: dict, current: dict) -> list[dict]:
    old = indexed(previous, label="committed baseline")
    new = indexed(current, label="regenerated candidate")
    findings = []
    for ident in sorted(old.keys() - new.keys()):
        findings.append({"id": ident, "kind": "missing_previously_locked_essay"})
    for ident in sorted(old.keys() & new.keys()):
        changes = {
            field: delta_hint(old[ident].get(field), new[ident].get(field))
            for field in CORE_FIELDS
            if old[ident].get(field) != new[ident].get(field)
        }
        if changes:
            findings.append({"id": ident, "kind": "official_core_drift", "fields": changes})
    # New IDs have their own official intake and lock acceptance gates.
    return findings


def read_committed(ref: str, path: Path) -> dict | None:
    relative = path.resolve().relative_to(ROOT).as_posix()
    r = subprocess.run(
        ["git", "show", f"{ref}:{relative}"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if r.returncode:
        if "exists on disk, but not in" in r.stderr or "does not exist in" in r.stderr:
            return None
        raise RuntimeError(f"git show baseline failed for {relative}: {r.stderr.strip()[:240]}")
    return json.loads(r.stdout)


def selftest() -> None:
    source = {"essays": [
        {"id": "E-1", "subject": "人類行為與社會環境", "year": "115",
         "round": "第二次", "qno": "1", "q": "NEET training ）可能", "points": "20",
         "analysis_status": "pending"},
    ]}
    same = json.loads(json.dumps(source, ensure_ascii=False))
    same["essays"][0]["analysis_status"] = "ready"
    assert not compare(source, same), "AI-only metadata must not count as official drift"
    whitespace = json.loads(json.dumps(source, ensure_ascii=False))
    whitespace["essays"][0]["q"] = "NEET training）可能"
    diff = compare(source, whitespace)
    assert len(diff) == 1 and diff[0]["fields"]["q"]["possible_layout_whitespace_only"]
    assert diff[0]["fields"]["q"]["edit_count"] >= 1
    semantic = json.loads(json.dumps(source, ensure_ascii=False))
    semantic["essays"][0]["q"] = "NEET training）可能嗎"
    assert compare(source, semantic)[0]["fields"]["q"]["possible_layout_whitespace_only"] is False
    points = json.loads(json.dumps(source, ensure_ascii=False))
    points["essays"][0]["points"] = "25"
    assert "points" in compare(source, points)[0]["fields"]
    assert compare(source, {"essays": []})[0]["kind"] == "missing_previously_locked_essay"
    try:
        compare(source, {"essays": [source["essays"][0], source["essays"][0]]})
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate IDs must fail closed")
    print("MOEX essay drift diagnostics self-test: PASS (metadata, whitespace, text, points, missing, duplicate)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-ref", default="HEAD")
    ap.add_argument("--incoming-dir", type=Path, default=ROOT / "incoming")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fail-on-drift", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    # Ref failure must not masquerade as a new/untracked exam.
    subprocess.run(
        ["git", "rev-parse", "--verify", f"{args.baseline_ref}^{{commit}}"],
        cwd=ROOT, stdout=subprocess.DEVNULL, check=True,
    )
    findings = []
    new_exams = []
    checked = []
    for path in sorted(args.incoming_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json")):
        current = json.loads(path.read_text(encoding="utf-8"))
        previous = read_committed(args.baseline_ref, path)
        if previous is None:
            new_exams.append(path.name)
            continue
        checked.append(path.name)
        for finding in compare(previous, current):
            findings.append({"exam_file": path.name, **finding})
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_never_auto_approve",
        "baseline_ref": args.baseline_ref,
        "checked_exam_files": checked,
        "untracked_new_exam_files": new_exams,
        "blocking": len(findings),
        "findings": findings,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 3 if args.fail_on_drift and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
