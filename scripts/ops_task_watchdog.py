#!/usr/bin/env python3
"""Read-only freshness watchdog for scheduled SWSI maintenance workflows.

It can query GitHub Actions or consume a fixture for deterministic tests.
When this script runs inside GitHub Actions it is same-platform observability,
not an independent external heartbeat.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_REGISTRY = Path("data/ops_task_registry.v1.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("timestamp is empty")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_registry(payload: Any) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("registry must be schema_version=1 object")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("registry tasks[] must be a non-empty list")

    seen: set[str] = set()
    normalized: list[dict] = []
    for raw in tasks:
        if not isinstance(raw, dict):
            raise ValueError("every registry task must be an object")
        task_id = str(raw.get("id") or "").strip()
        workflow_file = str(raw.get("workflow_file") or "").strip()
        display_name = str(raw.get("display_name") or task_id).strip()
        accepted_events = raw.get("accepted_events")
        criticality = str(raw.get("criticality") or "").strip().lower()
        try:
            expected = float(raw.get("expected_interval_hours"))
            max_age = float(raw.get("max_age_hours"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{task_id or '<unknown>'}: interval fields must be numeric") from exc

        if not task_id or task_id in seen:
            raise ValueError(f"task id missing or duplicated: {task_id!r}")
        seen.add(task_id)
        if not workflow_file.endswith((".yml", ".yaml")):
            raise ValueError(f"{task_id}: workflow_file must be a YAML filename")
        if not isinstance(accepted_events, list) or not accepted_events:
            raise ValueError(f"{task_id}: accepted_events must be non-empty")
        if expected <= 0 or max_age < expected:
            raise ValueError(f"{task_id}: max_age_hours must be >= expected_interval_hours > 0")
        if criticality not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"{task_id}: invalid criticality {criticality!r}")

        normalized.append(
            {
                "id": task_id,
                "workflow_file": workflow_file,
                "display_name": display_name,
                "accepted_events": [str(x).strip() for x in accepted_events],
                "expected_interval_hours": expected,
                "max_age_hours": max_age,
                "criticality": criticality,
            }
        )
    return normalized


def github_runs(repository: str, workflow_file: str, token: str) -> list[dict]:
    quoted = urllib.parse.quote(workflow_file, safe="")
    url = (
        f"https://api.github.com/repos/{repository}/actions/workflows/{quoted}/runs"
        "?branch=main&status=completed&per_page=50"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "swsi-ops-task-watchdog",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise RuntimeError("GitHub API response missing workflow_runs[]")
    return runs


def fixture_runs(payload: Any, workflow_file: str) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("fixture must be an object keyed by workflow filename")
    rows = payload.get(workflow_file, [])
    if not isinstance(rows, list):
        raise ValueError(f"fixture entry for {workflow_file} must be a list")
    return rows


def evaluate_task(task: dict, runs: list[dict], now: datetime) -> dict:
    accepted = set(task["accepted_events"])
    matching = [
        row
        for row in runs
        if str(row.get("event") or "") in accepted
        and str(row.get("conclusion") or "") == "success"
    ]
    matching.sort(
        key=lambda row: str(row.get("run_started_at") or row.get("created_at") or ""),
        reverse=True,
    )
    base = {
        "id": task["id"],
        "display_name": task["display_name"],
        "workflow_file": task["workflow_file"],
        "criticality": task["criticality"],
        "accepted_events": task["accepted_events"],
        "expected_interval_hours": task["expected_interval_hours"],
        "max_age_hours": task["max_age_hours"],
    }
    if not matching:
        return {
            **base,
            "status": "missing",
            "last_success_at": None,
            "age_hours": None,
            "run_id": None,
            "message": "no matching successful scheduled run found",
        }

    latest = matching[0]
    stamp = str(latest.get("run_started_at") or latest.get("created_at") or "")
    try:
        last = parse_time(stamp)
    except Exception as exc:
        return {
            **base,
            "status": "error",
            "last_success_at": stamp or None,
            "age_hours": None,
            "run_id": latest.get("id"),
            "message": f"invalid run timestamp: {exc}",
        }

    age_hours = max(0.0, (now - last).total_seconds() / 3600.0)
    status = "healthy" if age_hours <= task["max_age_hours"] else "stale"
    return {
        **base,
        "status": status,
        "last_success_at": last.isoformat().replace("+00:00", "Z"),
        "age_hours": round(age_hours, 2),
        "run_id": latest.get("id"),
        "message": (
            "last scheduled success is within freshness window"
            if status == "healthy"
            else "last scheduled success exceeded max_age_hours"
        ),
    }


def build_report(tasks: list[dict], fetcher: Callable[[str], list[dict]], now: datetime) -> dict:
    results: list[dict] = []
    for task in tasks:
        try:
            results.append(evaluate_task(task, fetcher(task["workflow_file"]), now))
        except Exception as exc:
            results.append(
                {
                    "id": task["id"],
                    "display_name": task["display_name"],
                    "workflow_file": task["workflow_file"],
                    "criticality": task["criticality"],
                    "status": "error",
                    "last_success_at": None,
                    "age_hours": None,
                    "run_id": None,
                    "message": str(exc),
                }
            )

    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    blocking = [
        row
        for row in results
        if row["criticality"] in {"high", "critical"}
        and row["status"] in {"stale", "missing", "error"}
    ]
    return {
        "schema_version": 1,
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "monitor_scope": "github-actions-task-freshness",
        "independent_of_github_actions": False,
        "summary": {"total": len(results), "counts": counts, "blocking": len(blocking)},
        "tasks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SWSI scheduled task freshness watchdog")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--now", help="ISO-8601 timestamp for deterministic tests")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on-stale", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    tasks = validate_registry(read_json(args.registry))
    if args.validate_only:
        print(json.dumps({"ok": True, "tasks": len(tasks)}, ensure_ascii=False))
        return 0

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if args.fixture:
        fixture = read_json(args.fixture)
        fetcher = lambda workflow_file: fixture_runs(fixture, workflow_file)
    else:
        repository = str(args.repository or "").strip()
        token = str(os.getenv(args.token_env, "") or "").strip()
        if not repository:
            raise SystemExit("--repository or GITHUB_REPOSITORY is required")
        if not token:
            raise SystemExit(f"environment variable {args.token_env} is required")
        fetcher = lambda workflow_file: github_runs(repository, workflow_file, token)

    report = build_report(tasks, fetcher, now)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    if args.fail_on_stale and report["summary"]["blocking"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
