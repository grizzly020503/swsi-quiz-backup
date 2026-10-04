#!/usr/bin/env python3
"""Fail-closed MOEX sync entrypoint with official-page structure discovery.

This wrapper adds two gates around the existing reviewed MOEX parser while
preserving the v2 grading/text-normalization extensions used in production:

1. official exam-page subject discovery must match an approved exam profile;
2. the fully parsed payload must still pass the existing exam-scheme gate.

A future structure change is quarantined before PDF parsing. A normal future
session that has not been published by MOEX yet keeps the legacy sync behavior:
scheduled discovery skips it instead of misclassifying it as a scheme change.
No new scheme is auto-approved here.

Diagnostic reports may include normalized durable-ops decisions, but this module
does not write to the durable ledger or Supabase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

from exam_scheme import compare_payload
from moex_ops_event_contract import classify_payload, classify_probe
from moex_structure_probe import exam_url, probe_live


class GuardedIntakeBlocked(RuntimeError):
    pass


def _production_base_module():
    """Return the parser after production v2 extensions have been installed.

    ``moex_sync_v2`` intentionally patches narrow extension points on its
    imported ``moex_sync`` base module. Importing it here (lazily) guarantees the
    guarded path keeps all_credit / any_answer semantics and MOEX Unicode
    normalization instead of accidentally falling back to raw v1 behavior.
    """
    import moex_sync_v2 as v2

    base = v2.base
    if base.parse_mc is not v2.parse_mc_with_grading:
        raise RuntimeError("MOEX v2 parse_mc grading patch is not active")
    if base._parse_correction_rules is not v2.parse_correction_rules_with_grading:
        raise RuntimeError("MOEX v2 correction/grading patch is not active")
    return base


def _default_exam_exists(exam_code: str) -> bool:
    # Preserve the proven sync distinction between "not published yet" and an
    # already published page whose structure is unexpected. The structure probe
    # runs only after this availability check succeeds.
    return bool(_production_base_module().exam_exists(exam_code))


def _default_build_exam(exam_code: str) -> dict[str, Any]:
    # Lazy import keeps deterministic guard tests independent of PDF libraries.
    return _production_base_module().build_exam(exam_code)


def _default_candidates() -> list[str]:
    return list(_production_base_module().default_candidates())


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def probe_ops_event(probe: dict[str, Any], *, retry_exhausted: bool = False) -> dict[str, Any]:
    """Return the durable-ops decision for a pre-parser probe without persisting it."""
    return classify_probe(probe, retry_exhausted=retry_exhausted)


def payload_ops_event(exam_code: str, scheme: dict[str, Any], *, source_ref: str) -> dict[str, Any]:
    """Return the durable-ops decision for the post-parser scheme result."""
    return classify_payload({
        "schema_version": 1,
        "exam_code": exam_code,
        "status": scheme.get("status"),
        "approved": scheme.get("approved") is True,
        "profile_id": scheme.get("profile_id"),
        "diffs": scheme.get("diffs") or [],
        "source_ref": source_ref,
    })


def guarded_build(
    exam_code: str,
    *,
    probe_fn: Callable[[str], dict[str, Any]] = probe_live,
    build_fn: Callable[[str], dict[str, Any]] | None = None,
    compare_fn: Callable[[dict[str, Any]], dict[str, Any]] = compare_payload,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    probe = probe_fn(exam_code)
    if probe.get("status") != "match" or probe.get("safe_to_parse_pdfs") is not True:
        raise GuardedIntakeBlocked(
            f"{exam_code}: official-page structure gate blocked intake: {probe.get('status')}"
        )

    payload = (build_fn or _default_build_exam)(exam_code)
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
    candidates = args.exam or _default_candidates()
    blocked = 0

    for code in candidates:
        if not re.fullmatch(r"\d{3}(030|100)", code):
            raise RuntimeError(f"拒絕匯入：不允許的考試代碼 {code}")
        out = outdir / f"{code}.json"
        if args.skip_existing and out.exists():
            print(f"skip existing {code}")
            continue

        try:
            published = _default_exam_exists(code)
        except Exception as exc:
            # A transport exception is not the same as "not published". Keep it
            # visible/fail-closed instead of silently treating an outage as no exam.
            availability_report = {
                "schema_version": 1,
                "probe": "moex_exam_page_availability_v1",
                "exam_code": code,
                "status": "source_error",
                "source_url": exam_url(code),
                "error_class": type(exc).__name__,
                "error_message": str(exc),
                "safe_to_parse_pdfs": False,
            }
            write_report(probe_dir / f"{code}.availability.json", availability_report)
            write_report(probe_dir / f"{code}.availability.ops-event.json", probe_ops_event(availability_report))
            print(f"{code}: official page availability check failed: {exc}", file=sys.stderr)
            if args.exam:
                raise
            blocked += 1
            continue

        if not published:
            print(f"{code}: official exam page not published yet; skip")
            if args.exam:
                return 2
            continue

        probe = probe_live(code)
        write_report(probe_dir / f"{code}.json", probe)
        write_report(probe_dir / f"{code}.ops-event.json", probe_ops_event(probe))
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
            data = _default_build_exam(code)
            scheme = compare_payload(data)
        except Exception as exc:
            print(f"{code}: {exc}", file=sys.stderr)
            if args.exam:
                raise
            blocked += 1
            continue

        post_report = {
            "schema_version": 1,
            "exam_code": code,
            "page_probe_status": probe.get("status"),
            "payload_scheme_status": scheme.get("status"),
            "status": scheme.get("status"),
            "profile_id": scheme.get("profile_id"),
            "approved": scheme.get("approved") is True,
            "diffs": scheme.get("diffs") or [],
            "source_ref": out.as_posix(),
        }
        write_report(probe_dir / f"{code}.post-parse.json", post_report)
        write_report(
            probe_dir / f"{code}.post-parse.ops-event.json",
            payload_ops_event(code, scheme, source_ref=out.as_posix()),
        )
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
