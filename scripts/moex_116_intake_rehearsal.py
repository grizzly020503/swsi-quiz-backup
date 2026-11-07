#!/usr/bin/env python3
"""Synthetic ROC 116+ MOEX intake rehearsal. No network, DB, tokens or official writes."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import moex_sync_guarded as intake

ROOT = Path(__file__).resolve().parents[1]


def assert_availability_http_contract() -> None:
    """Exercise the actual base parser's exam_exists without importing PDF libraries."""
    path = ROOT / "scripts/moex_sync.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "exam_exists")
    code = compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec")

    class Response:
        def __init__(self, status: int, size: int):
            self.status_code = status
            self.content = b"x" * size

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    cases = ((200, 2000, True), (200, 200, False), (404, 2000, False))
    for status, size, expected in cases:
        ns = {
            "requests": SimpleNamespace(get=lambda *args, **kwargs: Response(status, size)),
            "exam_url": lambda code: f"fixture://{code}",
            "UA": "synthetic-test",
        }
        exec(code, ns)
        assert ns["exam_exists"]("116030") is expected, (status, size)

    for status in (302, 403, 429, 500, 503):
        ns = {
            "requests": SimpleNamespace(get=lambda *args, **kwargs: Response(status, 2000)),
            "exam_url": lambda code: f"fixture://{code}",
            "UA": "synthetic-test",
        }
        exec(code, ns)
        try:
            ns["exam_exists"]("116030")
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"HTTP {status} silently treated as exam absence")


def run_case(availability, probes=None, builds=None, schemes=None):
    probes, builds, schemes = probes or {}, builds or {}, schemes or {}
    calls = {"availability": [], "probe": [], "pdf": [], "scheme": []}

    def exists(code):
        calls["availability"].append(code)
        value = availability[code]
        if isinstance(value, Exception):
            raise value
        return value

    def probe(code):
        calls["probe"].append(code)
        return {
            "schema_version": 1,
            "exam_code": code,
            "status": probes.get(code, "match"),
            "safe_to_parse_pdfs": probes.get(code, "match") == "match",
            "source_url": f"fixture://{code}",
            "content_sha256": "a" * 64,
            "diffs": [{"field": "subjects"}] if probes.get(code) == "possible_scheme_change" else [],
        }

    def build(code):
        calls["pdf"].append(code)
        value = builds.get(code)
        if isinstance(value, Exception):
            raise value
        return value or {"exam_code": code, "questions": [], "essays": []}

    def compare(payload):
        code = payload["exam_code"]
        calls["scheme"].append(code)
        status = schemes.get(code, "match")
        return {"status": status, "approved": status == "match", "profile_id": "synthetic-profile", "diffs": []}

    with TemporaryDirectory(prefix="swsi-116-intake-") as temp:
        out = Path(temp) / "incoming"
        reports = Path(temp) / "probe"
        args = ["moex_sync_guarded.py", "--output-dir", str(out), "--probe-output-dir", str(reports)]
        with (
            patch.object(sys, "argv", args),
            patch.object(intake, "_default_candidates", return_value=["116030", "116100"]),
            patch.object(intake, "_default_exam_exists", side_effect=exists),
            patch.object(intake, "probe_live", side_effect=probe),
            patch.object(intake, "_default_build_exam", side_effect=build),
            patch.object(intake, "compare_payload", side_effect=compare),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = intake.main()
        written = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in out.glob("*.json")}
        diagnostic = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in reports.glob("*.json")}
    return result, calls, written, diagnostic


def main() -> int:
    assert_availability_http_contract()

    # New 116-1 is published; 116-2 has not been published yet.
    rc, calls, published, reports = run_case({"116030": True, "116100": False})
    assert rc == 0
    assert sorted(published) == ["116030.json"], published
    assert calls["pdf"] == ["116030"] and "116100" not in calls["probe"]
    assert reports["116030.json"]["status"] == "match"

    rc, calls, published, reports = run_case(
        {"116030": RuntimeError("HTTP 503"), "116100": False}
    )
    assert rc != 0 and not published and not calls["pdf"]
    assert reports["116030.availability.json"]["status"] == "source_error"

    rc, calls, published, reports = run_case(
        {"116030": True, "116100": False},
        probes={"116030": "possible_scheme_change"},
    )
    assert rc != 0 and not calls["pdf"] and not published
    assert reports["116030.json"]["status"] == "possible_scheme_change"

    rc, calls, published, reports = run_case(
        {"116030": True, "116100": False},
        probes={"116030": "source_error"},
    )
    assert rc != 0 and not calls["pdf"] and not published

    rc, calls, published, reports = run_case(
        {"116030": True, "116100": False},
        builds={"116030": RuntimeError("synthetic PDF parsing failed")},
    )
    assert rc != 0 and not published and calls["pdf"] == ["116030"]

    rc, calls, published, reports = run_case(
        {"116030": True, "116100": False},
        schemes={"116030": "candidate_change"},
    )
    assert rc != 0 and not published and calls["scheme"] == ["116030"]
    assert reports["116030.post-parse.json"]["status"] == "candidate_change"

    # Partial success plus a later failure still makes the whole workflow fail;
    # no subsequent Supabase import/commit step may run on a nonzero shell exit.
    rc, calls, published, reports = run_case(
        {"116030": True, "116100": True},
        probes={"116100": "possible_scheme_change"},
    )
    assert rc != 0 and sorted(published) == ["116030.json"]
    assert calls["pdf"] == ["116030"]

    rc, calls, published, reports = run_case({"116030": False, "116100": False})
    assert rc == 0 and not published and not calls["pdf"]

    print("MOEX ROC 116+ SYNTHETIC INTAKE REHEARSAL PASS: normal/new, unpublished, HTTP failures, scheme drift, PDF failure, mixed-run fail-closed; no network/DB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
