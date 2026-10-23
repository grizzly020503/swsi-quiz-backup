#!/usr/bin/env python3
"""Deterministic tests for ops_task_watchdog.py without network access."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ops_task_watchdog.py"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    registry = {
        "schema_version": 1,
        "tasks": [
            {
                "id": "healthy",
                "workflow_file": "healthy.yml",
                "display_name": "Healthy",
                "accepted_events": ["schedule"],
                "expected_interval_hours": 6,
                "max_age_hours": 8,
                "criticality": "high",
            },
            {
                "id": "stale",
                "workflow_file": "stale.yml",
                "display_name": "Stale",
                "accepted_events": ["schedule"],
                "expected_interval_hours": 6,
                "max_age_hours": 8,
                "criticality": "critical",
            },
            {
                "id": "missing",
                "workflow_file": "missing.yml",
                "display_name": "Missing",
                "accepted_events": ["schedule"],
                "expected_interval_hours": 24,
                "max_age_hours": 30,
                "criticality": "medium",
            },
        ],
    }
    fixture = {
        "healthy.yml": [
            {
                "id": 1,
                "event": "schedule",
                "conclusion": "success",
                "run_started_at": "2026-10-02T05:00:00Z",
            },
            {
                "id": 2,
                "event": "push",
                "conclusion": "success",
                "run_started_at": "2026-10-02T05:59:00Z",
            },
        ],
        "stale.yml": [
            {
                "id": 3,
                "event": "schedule",
                "conclusion": "success",
                "run_started_at": "2026-10-01T00:00:00Z",
            }
        ],
        "missing.yml": [
            {
                "id": 4,
                "event": "workflow_dispatch",
                "conclusion": "success",
                "run_started_at": "2026-10-02T05:30:00Z",
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        registry_path = tmp / "registry.json"
        fixture_path = tmp / "fixture.json"
        out_path = tmp / "report.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

        proc = run(
            [
                "--registry",
                str(registry_path),
                "--fixture",
                str(fixture_path),
                "--now",
                "2026-10-02T06:00:00Z",
                "--out",
                str(out_path),
                "--fail-on-stale",
            ]
        )
        if proc.returncode != 2:
            raise SystemExit(
                f"expected stale exit 2, got {proc.returncode}: {proc.stderr}\n{proc.stdout}"
            )

        report = json.loads(out_path.read_text(encoding="utf-8"))
        statuses = {row["id"]: row["status"] for row in report["tasks"]}
        assert statuses == {
            "healthy": "healthy",
            "stale": "stale",
            "missing": "missing",
        }, statuses
        # Only high/critical stale/missing/error tasks block.  The medium
        # missing fixture stays visible in counts but must not fail the gate.
        assert report["summary"]["blocking"] == 1, report["summary"]
        assert report["summary"]["counts"]["missing"] == 1, report["summary"]
        assert report["independent_of_github_actions"] is False

        validate = run(["--registry", str(registry_path), "--validate-only"])
        if validate.returncode != 0:
            raise SystemExit(validate.stderr or validate.stdout)


    # GitHub history regression: a busy PR workflow must not hide a scheduled
    # success after the first 100 failures. Only accepted events are queried.
    import io
    import urllib.parse
    from unittest import mock
    import ops_task_watchdog as watchdog

    queried = []

    def fake_urlopen(req, timeout=20):
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)
        event, page = params["event"][0], int(params["page"][0])
        assert params["per_page"] == ["100"]
        queried.append((event, page))
        if event == "schedule" and page == 1:
            rows = [
                {"id": i, "event": event, "conclusion": "failure",
                 "created_at": "2026-10-02T05:59:00Z"}
                for i in range(100)
            ]
        elif event == "schedule" and page == 2:
            rows = [
                {"id": 500, "event": event, "conclusion": "success",
                 "created_at": "2026-10-02T05:00:00Z"}
            ]
        else:
            rows = []
        return io.BytesIO(json.dumps({"workflow_runs": rows}).encode("utf-8"))

    with mock.patch.object(watchdog.urllib.request, "urlopen",
                           side_effect=fake_urlopen):
        live_rows = watchdog.github_runs(
            "test-owner/test-repo", "monthly.yml", "fixture-token",
            ["schedule", "push"]
        )
    assert queried == [("schedule", 1), ("schedule", 2), ("push", 1)], queried
    assert len(live_rows) == 101
    assert watchdog.evaluate_task(
        {"id": "monthly", "display_name": "Monthly",
         "workflow_file": "monthly.yml", "criticality": "critical",
         "accepted_events": ["schedule", "push"],
         "expected_interval_hours": 744, "max_age_hours": 840},
        live_rows, watchdog.parse_time("2026-10-02T06:00:00Z")
    )["status"] == "healthy"

    # Exhausting the bounded API history must be explicit, never a false
    # "missing" classification or an unbounded request loop.
    queried.clear()
    def always_failed(req, timeout=20):
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)
        queried.append((params["event"][0], int(params["page"][0])))
        rows = [{"id": i, "event": "schedule", "conclusion": "failure"}
                for i in range(100)]
        return io.BytesIO(json.dumps({"workflow_runs": rows}).encode("utf-8"))

    with mock.patch.object(watchdog.urllib.request, "urlopen",
                           side_effect=always_failed):
        try:
            watchdog.github_runs(
                "test-owner/test-repo", "monthly.yml", "fixture-token",
                ["schedule"]
            )
        except RuntimeError as exc:
            assert "exceeded 1000 runs" in str(exc), exc
        else:
            raise AssertionError("truncated run history must fail closed")
    assert len(queried) == 10, queried

    print("OPS TASK WATCHDOG SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
