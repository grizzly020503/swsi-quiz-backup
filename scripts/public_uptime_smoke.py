#!/usr/bin/env python3
"""Read-only public availability sentinel for SWSI.

No secrets, browser automation, model calls, database writes, or user data.
"""
from __future__ import annotations

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
    if b"SWSI" not in body:
        raise AssertionError("Netlify fallback: SWSI marker missing")
    checks.append("netlify-fallback")

    print("SWSI PUBLIC UPTIME SENTINEL OK: " + ", ".join(checks))
    print("No model call, no database write, no user data collected.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SWSI PUBLIC UPTIME SENTINEL FAILED: {exc}", file=sys.stderr)
        raise
