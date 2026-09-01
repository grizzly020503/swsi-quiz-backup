#!/usr/bin/env python3
"""Cheap production uptime sentinel for public SWSI dependencies.

This intentionally avoids browsers, API keys, student data and live AI model
requests. It complements (does not replace) the manual release verification.
"""

from __future__ import annotations

import json
import ssl
import sys
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NETLIFY = "https://swsi-quiznetlify.netlify.app"
WORKER = "https://wandering-wave-4418.c022050333.workers.dev"
ORIGIN = NETLIFY
TIMEOUT = 20
USER_AGENT = "SWSI-Zero-Cost-Uptime/1.0"

# Production is currently on the pre-PR#33 title. The release candidate changes
# the public title to the SWSI-branded form. Both are known-good release states
# during this transition; unrelated HTML must still fail closed.
VALID_HOME_TITLES = (
    "<title>社工師國考題庫</title>",
    "<title>社工師國考免費題庫｜SWSI</title>",
)


@dataclass
class HttpResult:
    status: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: int


def fail(message: str) -> None:
    raise SystemExit(f"PUBLIC UPTIME SMOKE FAILED: {message}")


def request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None) -> HttpResult:
    merged = {
        "User-Agent": USER_AGENT,
        "Cache-Control": "no-cache",
    }
    if headers:
        merged.update(headers)
    req = Request(url, method=method, headers=merged)
    start = time.monotonic()
    try:
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as response:
            body = response.read(8_000_000)
            elapsed = int((time.monotonic() - start) * 1000)
            return HttpResult(
                status=int(response.status),
                headers={key.lower(): value for key, value in response.headers.items()},
                body=body,
                elapsed_ms=elapsed,
            )
    except HTTPError as exc:
        body = exc.read(256_000)
        elapsed = int((time.monotonic() - start) * 1000)
        return HttpResult(
            status=int(exc.code),
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=body,
            elapsed_ms=elapsed,
        )
    except (URLError, TimeoutError, OSError) as exc:
        fail(f"network error for {url}: {exc}")


def cache_bust(path: str) -> str:
    token = str(int(time.time()))
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{urlencode({'uptime_check': token})}"


def require_200(label: str, result: HttpResult) -> None:
    if result.status != 200:
        fail(f"{label} expected HTTP 200, got {result.status}")
    print(f"UP {label}: HTTP 200 ({result.elapsed_ms} ms)")


def check_netlify_shell() -> None:
    home = request(NETLIFY + cache_bust("/"))
    require_200("netlify-home", home)
    content_type = home.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        fail(f"Netlify home content-type is not HTML: {content_type!r}")
    html = home.body.decode("utf-8", errors="replace")
    if not any(title in html for title in VALID_HOME_TITLES):
        fail("Netlify home does not match a known SWSI production title")

    manifest_result = request(NETLIFY + cache_bust("/manifest.json"))
    require_200("netlify-manifest", manifest_result)
    try:
        manifest = json.loads(manifest_result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"Netlify manifest is not valid JSON: {exc}")
    if not isinstance(manifest, dict):
        fail("Netlify manifest must be a JSON object")
    if manifest.get("display") != "standalone":
        fail(f"Netlify manifest display contract drifted: {manifest.get('display')!r}")
    if not str(manifest.get("start_url") or "").strip():
        fail("Netlify manifest is missing start_url")

    sw = request(NETLIFY + cache_bust("/sw.js"))
    require_200("netlify-service-worker", sw)
    sw_text = sw.body.decode("utf-8", errors="replace")
    if "self.addEventListener" not in sw_text:
        fail("Netlify sw.js does not look like the SWSI service worker")


def check_question_cdn() -> None:
    result = request(WORKER + cache_bust("/question-shards/manifest.json"))
    require_200("cloudflare-question-manifest", result)
    try:
        manifest = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"Cloudflare question manifest is not valid JSON: {exc}")
    if not isinstance(manifest, dict):
        fail("Cloudflare question manifest must be a JSON object")
    if manifest.get("total_questions") != 4800:
        fail(f"Cloudflare question total drifted: {manifest.get('total_questions')!r}")
    if manifest.get("shard_count") != 24:
        fail(f"Cloudflare shard count drifted: {manifest.get('shard_count')!r}")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != 24:
        fail("Cloudflare question manifest does not contain 24 shard descriptors")


def check_ai_worker_preflight() -> None:
    result = request(
        WORKER + "/",
        method="OPTIONS",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-SWSI-Client-ID",
        },
    )
    if result.status != 204:
        fail(f"Cloudflare AI preflight expected HTTP 204, got {result.status}")
    allow_origin = result.headers.get("access-control-allow-origin")
    if allow_origin != ORIGIN:
        fail(f"Cloudflare AI CORS origin drifted: {allow_origin!r}")
    allow_methods = result.headers.get("access-control-allow-methods", "")
    if "POST" not in allow_methods or "OPTIONS" not in allow_methods:
        fail(f"Cloudflare AI CORS methods drifted: {allow_methods!r}")
    print(f"UP cloudflare-ai-preflight: HTTP 204 ({result.elapsed_ms} ms)")


def main() -> int:
    check_netlify_shell()
    check_question_cdn()
    check_ai_worker_preflight()
    print("PUBLIC UPTIME SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
