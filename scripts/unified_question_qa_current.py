#!/usr/bin/env python3
"""Run Unified Question QA for a current/new intake using the approved scheme.

Historical QA fixtures may keep using the pinned legacy policy directly. This
wrapper is the current-intake owner: it derives only structural expectations
from the versioned exam-scheme registry, runs the existing Unified QA engine,
and records the scheme provenance in the resulting report.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from exam_scheme import DEFAULT_REGISTRY
from exam_scheme_qa_policy import DEFAULT_BASE_POLICY, derive_from_paths

ROOT = Path(__file__).resolve().parents[1]
UNIFIED_QA = ROOT / "scripts" / "unified_question_qa.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scheme-derived current-intake Unified Question QA")
    parser.add_argument("--mcq", type=Path)
    parser.add_argument("--essays", type=Path)
    parser.add_argument("--year", required=True)
    parser.add_argument("--round", required=True)
    parser.add_argument("--base-policy", type=Path, default=DEFAULT_BASE_POLICY)
    parser.add_argument("--scheme-registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--legal-watch", type=Path)
    parser.add_argument("--trust-current-legal-watch", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on", choices=["blocked", "review", "never"], default="blocked")
    args = parser.parse_args()

    if not args.mcq and not args.essays:
        parser.error("at least one of --mcq or --essays is required")
    if args.trust_current_legal_watch and not args.legal_watch:
        parser.error("--trust-current-legal-watch requires --legal-watch")

    policy, provenance = derive_from_paths(
        args.year,
        args.round,
        base_policy_path=args.base_policy,
        registry_path=args.scheme_registry,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        effective_policy = tmp / "effective-question-qa-policy.json"
        raw_report = tmp / "unified-question-qa-report.json"
        effective_policy.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        command = [
            sys.executable,
            str(UNIFIED_QA),
            "--year",
            str(args.year),
            "--round",
            str(args.round),
            "--policy",
            str(effective_policy),
            "--out",
            str(raw_report),
            "--fail-on",
            str(args.fail_on),
        ]
        if args.mcq:
            command += ["--mcq", str(args.mcq)]
        if args.essays:
            command += ["--essays", str(args.essays)]
        if args.legal_watch:
            command += ["--legal-watch", str(args.legal_watch)]
        if args.trust_current_legal_watch:
            command.append("--trust-current-legal-watch")

        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        if not raw_report.is_file():
            if proc.stderr:
                sys.stderr.write(proc.stderr)
            return proc.returncode or 2

        report = json.loads(raw_report.read_text(encoding="utf-8"))
        report["policy"] = "scheme-derived-current-intake"
        report["exam_scheme"] = {
            **provenance,
            "registry": str(args.scheme_registry),
            "base_policy": str(args.base_policy),
        }
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
