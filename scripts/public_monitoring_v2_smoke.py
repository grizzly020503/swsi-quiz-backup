#!/usr/bin/env python3
"""Cheap fail-closed contract checks for SWSI Monitoring V2.

No network, model call, database write, or secrets are required.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def snapshot_publish_contract_smoke(workflow: str) -> None:
    """Exercise the workflow's staging command, including newly created files."""
    marker = "      - name: Publish changed monitoring snapshots\n"
    assert marker in workflow, "monitoring snapshot publisher is missing"
    lines = workflow.split(marker, 1)[1].splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.strip().startswith("git add ")), None)
    assert start is not None, "monitoring snapshot staging command is missing"
    command = []
    for line in lines[start:]:
        line = line.strip()
        continued = line.endswith("\\")
        command.append(line[:-1] if continued else line)
        if not continued:
            break

    expected = {
        "auto/current_affairs.json", "auto/current_affairs_signals.json",
        "auto/current_affairs_events.json", "auto/current_affairs_trends.json",
        "auto/legal_watch.json", "cdn/auto/current_affairs.json",
        "cdn/auto/current_affairs_signals.json", "cdn/auto/current_affairs_events.json",
        "cdn/auto/current_affairs_trends.json", "cdn/auto/legal_watch.json",
        "cdn/auto/health.json", "cdn/auto/sync_state.json",
    }
    with tempfile.TemporaryDirectory(prefix="swsi-monitoring-stage-") as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", tmp], check=True)
        for rel in expected | {"index.html", "private-notes.json"}:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        # Run only git add, with no shell, remote, commit or production write.
        subprocess.run(shlex.split(" ".join(command)), cwd=root, check=True)
        staged = set(subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
        ).splitlines())
        assert staged == expected, (
            f"snapshot publish staging mismatch: missing={sorted(expected - staged)}, "
            f"unexpected={sorted(staged - expected)}"
        )


def main() -> int:
    source_registry = read_json("data/current_affairs_sources.json")
    assert source_registry.get("schema_version") == 1
    source_rows = source_registry.get("sources") or []
    assert len(source_rows) >= 16, "current-affairs source registry unexpectedly shrank"
    source_names = [str(x.get("name") or "").strip() for x in source_rows]
    source_urls = [str(x.get("url") or "").strip() for x in source_rows]
    assert all(source_names), "current-affairs source name missing"
    assert all(url.startswith("https://") for url in source_urls), source_urls
    assert len(source_names) == len(set(source_names)), "duplicate current-affairs source name"
    assert len(source_urls) == len(set(source_urls)), "duplicate current-affairs source URL"
    for row in source_rows:
        assert row.get("region") in {"taiwan", "international"}, row
        assert row.get("source_type") in {"official", "news", "international"}, row
        assert row.get("source_format", "rss") in {"rss", "who_newsroom_json", "unicef_press_html"}, row
    required_official = {
        "https://www.edu.tw/Rss_News.aspx?n=9E7AC85F1954DDA8",
        "https://www.edu.tw/Rss_WebArchive.aspx?n=FB01D469347C76A7",
        "https://news.immigration.gov.tw/Rss/Content/8?lang=TW",
        "https://www.mol.gov.tw/1607/1632/1633/RssList",
        "https://www.moj.gov.tw/2204/2795/2796/rss",
        "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "https://www.who.int/api/newsroom/newsitems",
        "https://www.unicef.org/media/press-releases",
    }
    assert required_official.issubset(set(source_urls)), "new official feeds missing from registry"

    news = read_json("auto/current_affairs.json")
    events = read_json("auto/current_affairs_events.json")
    trends = read_json("auto/current_affairs_trends.json")
    laws = read_json("auto/legal_watch.json")
    health = read_json("auto/health.json")
    sync = read_json("auto/sync_state.json")

    assert news.get("schema_version") == 2
    assert int(news.get("source_feed_count") or 0) >= 16
    assert int(news.get("feed_error_count", -1)) == 0
    items = news.get("items") or []
    assert items, "current-affairs snapshot is empty"
    for row in items:
        assert str(row.get("title") or "").strip()
        assert str(row.get("source_url") or "").startswith("https://")
        assert row.get("category")

    assert events.get("schema_version") == 1
    event_rows = events.get("events") or []
    assert event_rows, "current-affairs event snapshot is empty"
    assert int(events.get("event_count") or 0) == len(event_rows)
    assert "不代表命題保證" in str(events.get("note") or "")
    event_ids = set()
    for row in event_rows:
        event_id = str(row.get("canonical_event_id") or "")
        assert event_id and event_id not in event_ids, event_id
        event_ids.add(event_id)
        evidence = row.get("evidence") or []
        assert evidence, event_id
        urls = {str(x.get("source_url") or "") for x in evidence}
        assert all(url.startswith("https://") for url in urls), (event_id, urls)
        assert int(row.get("source_count") or 0) >= 1
        assert int(row.get("official_source_count") or 0) >= 0
        assert int(row.get("observation_count") or 0) >= 1

    assert trends.get("schema_version") == 1
    trend_rows = trends.get("trends") or []
    assert trend_rows, "current-affairs trend snapshot is empty"
    assert int(trends.get("event_count") or 0) == len(trend_rows)
    assert "不代表命題保證" in str(trends.get("note") or "")
    allowed_states = {"rising", "sustained", "cooling", "one-off"}
    for row in trend_rows:
        assert str(row.get("canonical_event_id") or "") in event_ids
        assert row.get("trend_state") in allowed_states
        score = float(row.get("trend_score"))
        assert 0.0 <= score <= 10.0
        assert isinstance(row.get("factors"), dict) and row.get("factors")
        assert isinstance(row.get("why"), list) and row.get("why")

    assert laws.get("schema_version") == 1
    assert int(laws.get("watch_count") or 0) >= 20
    assert int(laws.get("matched_count") or 0) >= 20
    assert int(laws.get("changed_count") or 0) == len(laws.get("changes") or [])
    allowed_law_fields = {
        "name",
        "official_url",
        "official_modified_date",
        "previous_modified_date",
        "changed",
    }
    for row in (laws.get("changes") or []) + (laws.get("recently_modified") or []):
        url = str(row.get("official_url") or "")
        assert url.startswith("https://law.moj.gov.tw/"), url
        assert set(row).issubset(allowed_law_fields), row

    assert health.get("status") == "ok"
    assert int(health.get("expected_total_questions") or 0) == 4800
    assert isinstance(sync.get("included_exams"), list)

    owner = (ROOT / "monthly_patch_parts/89.public-branding-info.part").read_text(encoding="utf-8")
    assert "Monitoring Center V2" in owner
    assert "2026-09-01.monitoring-v2" in owner
    for key in ("news", "law", "questions", "system", "feedback"):
        assert f'data-monitor-key="{key}"' in owner, key
    assert "/auto/current_affairs.json" in owner
    assert "/auto/legal_watch.json" in owner
    assert "/auto/health.json" in owner
    assert "/auto/sync_state.json" in owner
    assert "不自動改答案" in owner

    for rel in (
        "current_affairs.json", "current_affairs_signals.json",
        "current_affairs_events.json", "current_affairs_trends.json",
        "legal_watch.json", "health.json", "sync_state.json",
    ):
        public = ROOT / "cdn/auto" / rel
        if public.exists():
            assert json.loads(public.read_text(encoding="utf-8")) == read_json("auto/" + rel), rel

    # Legal-watch changes must reach the public snapshot immediately after the
    # reviewed MOEX/MOJ report is committed to main. Keep the push trigger
    # narrow so the monitoring bot's own auto/*.json commit cannot trigger an
    # infinite self-loop. Parse only YAML list entries so explanatory comments
    # cannot create a false positive.
    workflow = (ROOT / ".github/workflows/public-monitoring-feed.yml").read_text(encoding="utf-8")
    snapshot_publish_contract_smoke(workflow)
    push_start = workflow.find("\n  push:\n")
    pr_start = workflow.find("\n  pull_request:\n")
    assert push_start >= 0 and pr_start > push_start, "public monitoring feed is missing its main push trigger"
    push_block = workflow[push_start:pr_start]
    push_entries = []
    for raw in push_block.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped.startswith("- "):
            continue
        push_entries.append(stripped[2:].strip().strip("'\""))
    assert "main" in push_entries, "legal snapshot push trigger must be main-only"
    assert "data/legal_watch_report.json" in push_entries, "MOJ report changes must trigger public legal snapshot refresh"
    assert "data/current_affairs_sources.json" in push_entries, "source registry changes must refresh public current-affairs snapshots"
    assert "scripts/current_affairs_watch.py" in push_entries, "scanner changes must refresh public current-affairs snapshots"
    assert "scripts/analyze_current_affairs_signals.py" in push_entries, "signal analyzer changes must refresh public current-affairs snapshots"
    assert "auto/legal_watch.json" not in push_entries, "public snapshot output must not self-trigger the workflow"

    # Commits pushed by a workflow with GITHUB_TOKEN do not recursively trigger
    # ordinary push workflows. The public feed therefore must also subscribe
    # to successful MOEX workflow completion on main.
    wr_start = workflow.find("\n  workflow_run:\n")
    push_start_for_wr = workflow.find("\n  push:\n")
    assert wr_start >= 0 and push_start_for_wr > wr_start, "public monitoring feed is missing workflow_run chaining"
    workflow_run_block = workflow[wr_start:push_start_for_wr]
    assert "MOEX Social Worker Exam Sync" in workflow_run_block, "workflow_run must follow the MOEX sync workflow"
    assert "- completed" in workflow_run_block, "workflow_run must wait for MOEX completion"
    assert "- main" in workflow_run_block, "workflow_run must be main-only"
    assert "github.event.workflow_run.conclusion == 'success'" in workflow, "publish must require successful upstream MOEX sync"
    assert "github.event.workflow_run.head_branch == 'main'" in workflow, "workflow_run publish must be main-only"
    assert "github.event_name == 'workflow_run' && 'main' || github.ref" in workflow, "workflow_run checkout must refresh latest main"

    print(
        "PUBLIC MONITORING V2 CONTRACT OK: "
        f"sources={len(source_rows)}/{news['source_feed_count']}, news={len(items)}, events={len(event_rows)}, trends={len(trend_rows)}, "
        f"laws={laws['matched_count']}/{laws['watch_count']}, questions=4800, five-radar-ui=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
