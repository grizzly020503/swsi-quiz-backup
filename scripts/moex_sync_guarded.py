#!/usr/bin/env python3
"""Fail-closed MOEX sync entrypoint with official-page structure discovery.

This is intentionally a wrapper around the existing, reviewed ``moex_sync``
parser. It adds two gates without changing Official Core parsing logic:

1. official exam-page subject discovery must match an approved exam profile;
2. the fully parsed payload must still pass the existing exam-scheme gate.

A future structure change is quarantined before PDF parsing. No new scheme is
auto-approved here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

from exam_scheme import compare_payload
from moex_structure_probe import probe_live
from moex_sync import build_exam, default_candidates


class GuardedIntakeBlocked(RuntimeError):
    pass


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def guarded_build(
    exam_code: str,
    *,
    probe_fn: Callable[[str], dict[str, Any]] = probe_live,
    build_fn: Callable[[str], dict[str, Any]] = build_exam,
    compare_fn: Callable[[dict[str, Any]], dict[str, Any]] = compare_payload,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    probe = probe_fn(exam_code)
    if probe.get("status") != "match" or probe.get("safe_to_parse_pdfs") is not True:
        raise GuardedIntakeBlocked(
            f"{exam_code}: official-page structure gate blocked intake: {probe.get('status')}"
        )

    payload = build_fn(exam_code)
    scheme = compare_fn(payload)
    if scheme.get("status") != "match" or scheme.get("approved") is not True:
        raise GuardedIntakeBlocked(
            f"{exam_code}: parsed payload scheme gate blocked intake: {scheme.get('status')}"
        )
    return payload, probe, scheme


def main() -> int:
    parser = argparse.ArgumentParser(description="MOEX 社工師題庫同步：官方頁面結構先行、未知格式 fail-closed")
    parser.add_argument("--exam", action="append", help="指定六位數考試代碼，可重複")
    parser.add_argument("--output-dir", default="incoming")
    parser.add_argument("--probe-output-dir", help="結構 probe 報表目錄；預設 <output-dir>/_structure_probe")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    probe_dir = Path(args.probe_output_dir) if args.probe_output_dir else outdir / "_structure_probe"
    candidates = args.exam or default_candidates()
    blocked = 0

    for code in candidates:
        if not re.fullmatch(r"\d{3}(030|100)", code):
            raise RuntimeError(f"拒絕匯入：不允許的考試代碼 {code}")
        out = outdir / f"{code}.json"
        if args.skip_existing and out.exists():
            print(f"skip existing {code}")
            continue

        probe = probe_live(code)
        write_report(probe_dir / f"{code}.json", probe)
        if probe.get("status") != "match" or probe.get("safe_to_parse_pdfs") is not True:
            blocked += 1
            print(
                f"{code}: blocked before PDF parsing: {probe.get('status')} (report={probe_dir / (code + '.json')})",
                file=sys.stderr,
            )
            if args.exam:
                return 3
            continue

        try:
            data = build_exam(code)
            scheme = compare_payload(data)
        except Exception as exc:
            print(f"{code}: {exc}", file=sys.stderr)
            if args.exam:
                raise
            continue

        post_report = {
            "schema_version": 1,
            "exam_code": code,
            "page_probe_status": probe.get("status"),
            "payload_scheme_status": scheme.get("status"),
            "profile_id": scheme.get("profile_id"),
            "approved": scheme.get("approved") is True,
            "diffs": scheme.get("diffs") or [],
        }
        write_report(probe_dir / f"{code}.post-parse.json", post_report)
        if scheme.get("status") != "match" or scheme.get("approved") is not True:
            blocked += 1
            print(f"{code}: parsed payload quarantined: {scheme.get('status')}", file=sys.stderr)
            if args.exam:
                return 4
            continue

        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}: {len(data['questions'])} MC + {len(data['essays'])} essays")

    return 3 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
