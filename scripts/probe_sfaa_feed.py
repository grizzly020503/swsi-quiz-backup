#!/usr/bin/env python3
"""Non-production probe for Social and Family Affairs Administration feed endpoints."""
from __future__ import annotations

import urllib.request
import urllib.error

import feedparser

CANDIDATES = [
    "https://crc.sfaa.gov.tw/News/Rss",
    "https://crc.sfaa.gov.tw/News/RSS",
    "https://crc.sfaa.gov.tw/Rss",
    "https://crc.sfaa.gov.tw/News/Rss?type=25",
    "https://crc.sfaa.gov.tw/News/RssList",
    "https://www.sfaa.gov.tw/SFAA/Pages/RSS.aspx",
    "https://www.sfaa.gov.tw/SFAA/Pages/Rss.aspx",
    "https://www.sfaa.gov.tw/SFAA/Pages/rss.aspx",
]

UA = "swsi-sfaa-feed-probe/1.0"


def probe(url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            status = int(res.status)
            ctype = str(res.headers.get("content-type") or "")
            body = res.read(256_000)
    except urllib.error.HTTPError as exc:
        print(f"SFAA PROBE: url={url} status={exc.code} http_error=yes")
        return
    except Exception as exc:
        print(f"SFAA PROBE: url={url} network_error={type(exc).__name__}:{exc}")
        return

    parsed = feedparser.parse(body)
    entries = len(parsed.entries or [])
    bozo = bool(getattr(parsed, "bozo", False))
    title = str(getattr(getattr(parsed, "feed", {}), "title", "") or "")
    print(
        "SFAA PROBE: "
        f"url={url} status={status} content_type={ctype!r} "
        f"entries={entries} bozo={bozo} feed_title={title!r}"
    )


def main() -> int:
    for url in CANDIDATES:
        probe(url)
    print("SFAA PROBE COMPLETE: no registry or production changes made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
