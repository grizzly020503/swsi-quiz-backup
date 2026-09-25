#!/usr/bin/env python3
"""Read-only public availability sentinel for SWSI.

No secrets, browser automation, model calls, database writes, or user data.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PRIMARY = "https://wandering-wave-4418.c022050333.workers.dev"
BACKUP = "https://swsi-quiznetlify.netlify.app"
FEEDBACK = "https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-feedback"
UA = "SWSI-Uptime-Sentinel/1.0"
TIMEOUT = 12


def request(url: str, method: str = "GET", headers: dict[str, str] | None = None):
    merged = {"User-Agent": UA, "Cache-Control": "no-cache"}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, method=method, headers=merged)
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        return exc


def require_status(label: str, url: str, expected: int = 200, *, method: str = "GET", headers=None):
    with request(url, method=method, headers=headers) as res:
        status = int(res.status)
        if status != expected:
            raise AssertionError(f"{label}: expected HTTP {expected}, got {status}")
        return res.read(), res.headers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--monitoring-v2",
        action="store_true",
        help="Require Monitoring V2 public snapshots. Use after V2 is deployed, not while a PR still targets old production.",
    )
    args = ap.parse_args()
    checks: list[str] = []

    body, _ = require_status("Cloudflare home", PRIMARY + "/")
    html = body.decode("utf-8", "replace")
    if "SWSI" not in html:
        raise AssertionError("Cloudflare home: SWSI marker missing")
    checks.append("primary-home")

    body, _ = require_status("PWA manifest", PRIMARY + "/manifest.json")
    pwa = json.loads(body)
    if pwa.get("display") != "standalone" or not pwa.get("start_url"):
        raise AssertionError("PWA manifest: contract mismatch")
    body, _ = require_status("Service Worker", PRIMARY + "/sw.js")
    sw = body.decode("utf-8", "replace")
    if "const VERSION = 'v7';" not in sw:
        raise AssertionError("Service Worker: expected VERSION v7")
    checks.append("pwa-sw-v7")

    body, _ = require_status("Question manifest", PRIMARY + "/question-shards/manifest.json")
    questions = json.loads(body)
    if int(questions.get("total_questions", -1)) != 4800:
        raise AssertionError("Question manifest: total_questions != 4800")
    if int(questions.get("shard_count", -1)) != 24:
        raise AssertionError("Question manifest: shard_count != 24")
    if len(questions.get("shards") or []) != 24:
        raise AssertionError("Question manifest: shards length != 24")
    checks.append("questions-4800-24")

    if args.monitoring_v2:
        body, _ = require_status("Current-affairs snapshot", PRIMARY + "/auto/current_affairs.json")
        news = json.loads(body)
        news_items = news.get("items") or []
        if int(news.get("schema_version", -1)) != 2 or not news_items:
            raise AssertionError("Current-affairs snapshot: contract mismatch")
        source_feed_count = int(news.get("source_feed_count", -1))
        feed_error_count = int(news.get("feed_error_count", -1))
        if source_feed_count < 15:
            raise AssertionError(f"Current-affairs snapshot: expected at least 15 feeds, got {source_feed_count}")
        if feed_error_count != 0:
            raise AssertionError(f"Current-affairs snapshot: expected 0 feed errors, got {feed_error_count}")
        checks.append(f"sources-{source_feed_count}/errors-{feed_error_count}")
        checks.append(f"news-{len(news_items)}")

        body, _ = require_status("Current-affairs signals", PRIMARY + "/auto/current_affairs_signals.json")
        signals = json.loads(body)
        signal_items = signals.get("items") or []
        if int(signals.get("schema_version", -1)) != 1:
            raise AssertionError("Current-affairs signals: schema_version != 1")
        if int(signals.get("item_count", -1)) != len(signal_items) or not signal_items:
            raise AssertionError("Current-affairs signals: item_count mismatch or empty")
        if int(signals.get("questions_loaded", -1)) != 4800:
            raise AssertionError("Current-affairs signals: questions_loaded != 4800")
        if signals.get("question_source") != "cdn/question-shards":
            raise AssertionError("Current-affairs signals: unexpected question_source")
        if "不代表命題保證" not in str(signals.get("note") or ""):
            raise AssertionError("Current-affairs signals: non-guarantee note missing")
        for item in signal_items:
            if item.get("signal_confidence") not in {"low", "medium", "high"}:
                raise AssertionError("Current-affairs signals: invalid signal_confidence")
            if not str(item.get("essay_direction") or "").strip():
                raise AssertionError("Current-affairs signals: essay_direction missing")
            if not isinstance(item.get("mcq_focus"), list):
                raise AssertionError("Current-affairs signals: mcq_focus must be a list")
            if not isinstance(item.get("related_exam_questions"), list):
                raise AssertionError("Current-affairs signals: related_exam_questions must be a list")
        checks.append(f"signals-{len(signal_items)}/4800")

        body, _ = require_status("Current-affairs events", PRIMARY + "/auto/current_affairs_events.json")
        events = json.loads(body)
        event_items = events.get("events") or []
        if int(events.get("schema_version", -1)) != 1:
            raise AssertionError("Current-affairs events: schema_version != 1")
        if int(events.get("event_count", -1)) != len(event_items) or not event_items:
            raise AssertionError("Current-affairs events: event_count mismatch or empty")
        if "不代表命題保證" not in str(events.get("note") or ""):
            raise AssertionError("Current-affairs events: non-guarantee note missing")
        event_ids = set()
        for item in event_items:
            event_id = str(item.get("canonical_event_id") or "")
            if not event_id or event_id in event_ids:
                raise AssertionError("Current-affairs events: invalid or duplicate canonical_event_id")
            event_ids.add(event_id)
            evidence = item.get("evidence") or []
            if not evidence:
                raise AssertionError("Current-affairs events: evidence missing")
            if any(not str(x.get("source_url") or "").startswith("https://") for x in evidence):
                raise AssertionError("Current-affairs events: invalid evidence URL")
        checks.append(f"events-{len(event_items)}")

        body, _ = require_status("Current-affairs trends", PRIMARY + "/auto/current_affairs_trends.json")
        trends = json.loads(body)
        trend_items = trends.get("trends") or []
        if int(trends.get("schema_version", -1)) != 1:
            raise AssertionError("Current-affairs trends: schema_version != 1")
        if int(trends.get("event_count", -1)) != len(trend_items) or not trend_items:
            raise AssertionError("Current-affairs trends: event_count mismatch or empty")
        if "不代表命題保證" not in str(trends.get("note") or ""):
            raise AssertionError("Current-affairs trends: non-guarantee note missing")
        for item in trend_items:
            if str(item.get("canonical_event_id") or "") not in event_ids:
                raise AssertionError("Current-affairs trends: orphan event reference")
            if item.get("trend_state") not in {"rising", "sustained", "cooling", "one-off"}:
                raise AssertionError("Current-affairs trends: invalid trend_state")
            score = float(item.get("trend_score", -1))
            if score < 0 or score > 10:
                raise AssertionError("Current-affairs trends: trend_score out of range")
            if not isinstance(item.get("why"), list) or not item.get("why"):
                raise AssertionError("Current-affairs trends: explanation missing")
        checks.append(f"trends-{len(trend_items)}")

        if "命題趨勢雷達" not in html:
            raise AssertionError("Current-affairs V2 UI: trend radar marker missing from production home")
        if "current_affairs_events.json" not in html or "current_affairs_trends.json" not in html:
            raise AssertionError("Current-affairs V2 UI: event/trend feed loader missing from production home")
        checks.append("trend-ui-v2")

        body, _ = require_status("Legal-watch snapshot", PRIMARY + "/auto/legal_watch.json")
        laws = json.loads(body)
        law_watch = int(laws.get("watch_count", -1))
        law_matched = int(laws.get("matched_count", -1))
        law_changed = int(laws.get("changed_count", -1))
        if law_watch < 20 or law_matched < 20 or law_changed != len(laws.get("changes") or []):
            raise AssertionError("Legal-watch snapshot: contract mismatch")
        checks.append(f"laws-{law_matched}/{law_watch}")

        body, _ = require_status("Question health", PRIMARY + "/auto/health.json")
        qhealth = json.loads(body)
        if qhealth.get("status") != "ok" or int(qhealth.get("expected_total_questions", -1)) != 4800:
            raise AssertionError("Question health: contract mismatch")
        checks.append("question-health")

    cors_headers = {
        "Origin": PRIMARY,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    _, ai_headers = require_status("AI preflight", PRIMARY + "/api/ai", 204, method="OPTIONS", headers=cors_headers)
    if ai_headers.get("Access-Control-Allow-Origin") != PRIMARY:
        raise AssertionError("AI preflight: ACAO mismatch")
    checks.append("ai-preflight")

    _, fb_headers = require_status("Feedback preflight", FEEDBACK, 204, method="OPTIONS", headers=cors_headers)
    if fb_headers.get("Access-Control-Allow-Origin") != PRIMARY:
        raise AssertionError("Feedback preflight: ACAO mismatch")
    checks.append("feedback-preflight")

    body, _ = require_status("Netlify fallback", BACKUP + "/")
    fallback_html = body.decode("utf-8", "replace")
    if "SWSI" not in fallback_html and "社工師" not in fallback_html:
        raise AssertionError("Netlify fallback: expected social-work-study marker missing")
    checks.append("netlify-fallback")

    mode = "monitoring-v2" if args.monitoring_v2 else "baseline"
    print(f"SWSI PUBLIC UPTIME SENTINEL OK [{mode}]: " + ", ".join(checks))
    print("No model call, no database write, no user data collected.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SWSI PUBLIC UPTIME SENTINEL FAILED: {exc}", file=sys.stderr)
        raise
