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
    require_status("Service Worker", PRIMARY + "/sw.js")
    checks.append("pwa")

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
        checks.append(f"news-{len(news_items)}")

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
