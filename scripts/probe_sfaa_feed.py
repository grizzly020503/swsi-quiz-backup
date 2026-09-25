#!/usr/bin/env python3
"""Non-production probe for Social and Family Affairs Administration feed endpoints."""
from __future__ import annotations

import http.cookiejar
import urllib.request
import urllib.error

import feedparser

CANDIDATES = [
    "https://crc.sfaa.gov.tw/News/Rss",
    "https://crc.sfaa.gov.tw/News/Rss?AspxAutoDetectCookieSupport=1",
    "https://crc.sfaa.gov.tw/News/Rss?type=25&AspxAutoDetectCookieSupport=1",
    "https://crc.sfaa.gov.tw/News/RssList?AspxAutoDetectCookieSupport=1",
    "https://crc.sfaa.gov.tw/Rss?AspxAutoDetectCookieSupport=1",
    "https://www.sfaa.gov.tw/SFAA/Pages/RSS.aspx",
    "https://www.sfaa.gov.tw/SFAA/Pages/Rss.aspx",
]
UA = "swsi-sfaa-feed-probe/1.1"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def probe(url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with opener.open(req, timeout=10) as res:
            status = int(res.status)
            final_url = str(res.geturl())
            ctype = str(res.headers.get("content-type") or "")
            body = res.read(256_000)
    except urllib.error.HTTPError as exc:
        location = str(exc.headers.get("location") or "")
        print(
            f"SFAA PROBE: url={url} status={exc.code} "
            f"location={location!r} http_error=yes"
        )
        return
    except Exception as exc:
        print(f"SFAA PROBE: url={url} network_error={type(exc).__name__}:{exc}")
        return

    parsed = feedparser.parse(body)
    entries = len(parsed.entries or [])
    bozo = bool(getattr(parsed, "bozo", False))
    title = str(getattr(getattr(parsed, "feed", {}), "title", "") or "")
    preview = body[:80].decode("utf-8", "replace").replace("\n", " ").replace("\r", " ")
    print(
        "SFAA PROBE: "
        f"url={url} status={status} final_url={final_url!r} "
        f"content_type={ctype!r} entries={entries} bozo={bozo} "
        f"feed_title={title!r} preview={preview!r}"
    )


def main() -> int:
    for url in CANDIDATES:
        probe(url)
    print("SFAA PROBE COMPLETE: no registry or production changes made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
