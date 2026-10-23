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
                "id": "failed",
                "workflow_file": "failed.yml",
                "display_name": "Failed",
                "accepted_events": ["schedule"],
                "expected_interval_hours": 6,
                "max_age_hours": 8,
                "criticality": "high",
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
        "failed.yml": [
            {
                "id": 6,
                "event": "schedule",
                "conclusion": "success",
                "run_started_at": "2026-10-02T04:00:00Z",
            },
            {
                "id": 7,
                "event": "schedule",
                "conclusion": "failure",
                "run_started_at": "2026-10-02T05:40:00Z",
            },
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
            "failed": "failed",
            "missing": "missing",
        }, statuses
        # Only high/critical stale/missing/error tasks block.  The medium
        # missing fixture stays visible in counts but must not fail the gate.
        assert report["summary"]["blocking"] == 2, report["summary"]
        assert report["summary"]["counts"]["missing"] == 1, report["summary"]
        failed_row = next(row for row in report["tasks"] if row["id"] == "failed")
        assert failed_row["run_id"] == 7, failed_row
        assert failed_row["last_failure_at"] == "2026-10-02T05:40:00Z"
        assert failed_row["last_success_at"] is None
        assert report["independent_of_github_actions"] is False

        validate = run(["--registry", str(registry_path), "--validate-only"])
        if validate.returncode != 0:
            raise SystemExit(validate.stderr or validate.stdout)

    # Fail closed when the monitoring *policy* is corrupted, rather than
    # making an impossible freshness calculation look healthy.
    import copy
    import ops_task_watchdog as watchdog
    base_registry = {"schema_version": 1, "tasks": [registry["tasks"][0]]}
    for key, invalid in (
        ("expected_interval_hours", float("nan")),
        ("expected_interval_hours", float("inf")),
        ("expected_interval_hours", True),
        ("expected_interval_hours", "6"),
        ("expected_interval_hours", 0),
        ("max_age_hours", float("nan")),
        ("max_age_hours", float("inf")),
        ("max_age_hours", False),
        ("max_age_hours", "8"),
        ("max_age_hours", 4),
        ("max_age_hours", 10 ** 1000),
    ):
        broken = copy.deepcopy(base_registry)
        broken["tasks"][0][key] = invalid
        try:
            watchdog.validate_registry(broken)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{key}={invalid!r} must fail closed")

    for bad_events in ([], [""], ["pull_request"], ["schedule", "schedule"],
                       [" schedule"], [True], [1], ["workflow_run", "pull_request"]):
        broken = copy.deepcopy(base_registry)
        broken["tasks"][0]["accepted_events"] = bad_events
        try:
            watchdog.validate_registry(broken)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid accepted_events={bad_events!r} must fail")

    for version in (True, False, 1.0, "1", None):
        broken = copy.deepcopy(base_registry)
        broken["schema_version"] = version
        try:
            watchdog.validate_registry(broken)
        except ValueError:
            pass
        else:
            raise AssertionError(f"schema_version={version!r} must fail closed")

    for good_event in ("schedule", "workflow_dispatch", "push", "workflow_run"):
        valid = copy.deepcopy(base_registry)
        valid["tasks"][0]["accepted_events"] = [good_event]
        assert watchdog.validate_registry(valid)[0]["accepted_events"] == [good_event]

    # Regression: PR traffic must not push a scheduled run out of history.
    # The API is queried separately for accepted events, returning the most
    # recent run (including failures) without searching for an older success.
    import io
    import urllib.parse
    from unittest import mock
    import ops_task_watchdog as watchdog

    observed = []

    def fake_urlopen(request, timeout=20):
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
        event = params["event"][0]
        observed.append((event, params["branch"][0], params["per_page"][0]))
        if event == "schedule":
            rows = [{"id": 90, "event": event, "conclusion": "failure",
                     "run_started_at": "2026-10-02T05:40:00Z"}]
        else:
            rows = [{"id": 10, "event": event, "conclusion": "success",
                     "run_started_at": "2026-10-02T05:00:00Z"}]
        return io.BytesIO(json.dumps({"workflow_runs": rows}).encode("utf-8"))

    with mock.patch.object(watchdog.urllib.request, "urlopen", side_effect=fake_urlopen):
        rows = watchdog.github_runs(
            "test-owner/test-repo", "monthly.yml", "fixture-token", ["schedule", "push"]
        )
    assert observed == [("schedule", "main", "1"), ("push", "main", "1")], observed
    check = watchdog.evaluate_task(
        {"id": "monthly", "display_name": "Monthly", "workflow_file": "monthly.yml",
         "criticality": "high", "accepted_events": ["schedule", "push"],
         "expected_interval_hours": 6, "max_age_hours": 8},
        rows, watchdog.parse_time("2026-10-02T06:00:00Z")
    )
    assert check["status"] == "failed" and check["run_id"] == 90, check

    def mismatched_event(request, timeout=20):
        return io.BytesIO(json.dumps({"workflow_runs": [
            {"id": 5, "event": "pull_request", "conclusion": "success"}
        ]}).encode("utf-8"))
    with mock.patch.object(watchdog.urllib.request, "urlopen", side_effect=mismatched_event):
        try:
            watchdog.github_runs("test-owner/test-repo", "monthly.yml", "fixture", ["schedule"])
        except RuntimeError as exc:
            assert "event mismatch" in str(exc), exc
        else:
            raise AssertionError("untrusted/unmatched API event must fail closed")

    # Future-dated GitHub data must not be accepted as a fresh healthy run.
    future_task = {
        "id": "clock", "display_name": "Clock", "workflow_file": "clock.yml",
        "criticality": "high", "accepted_events": ["schedule"],
        "expected_interval_hours": 6, "max_age_hours": 8,
    }
    fixed_now = watchdog.parse_time("2026-10-02T06:00:00Z")
    def with_time(timestamp):
        return watchdog.evaluate_task(future_task, [{
            "id": 99, "event": "schedule", "conclusion": "success",
            "run_started_at": timestamp,
        }], fixed_now)
    future = with_time("2026-10-02T06:05:01Z")
    assert future["status"] == "error" and future["run_id"] == 99, future
    assert with_time("2026-10-02T06:05:00Z")["status"] == "healthy"
    assert with_time("2026-10-02T05:00:00Z")["status"] == "healthy"
    assert with_time("2026-10-01T21:00:00Z")["status"] == "stale"

    # GitHub branch/status filtering is verified, not merely assumed.
    for key, value, fragment in (
        ("head_branch", "release/not-main", "branch mismatch"),
        ("status", "in_progress", "completion mismatch"),
    ):
        def bad_filtered_response(req, timeout=20):
            row = {"id": 80, "event": "schedule", "conclusion": "success",
                   "head_branch": "main", "status": "completed"}
            row[key] = value
            return io.BytesIO(json.dumps({"workflow_runs": [row]}).encode("utf-8"))
        with mock.patch.object(watchdog.urllib.request, "urlopen",
                               side_effect=bad_filtered_response):
            try:
                watchdog.github_runs("test-owner/test-repo", "clock.yml",
                                     "fixture-token", ["schedule"])
            except RuntimeError as exc:
                assert fragment in str(exc), exc
            else:
                raise AssertionError(f"{key} mismatch must fail closed")

    print("OPS TASK WATCHDOG SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
