#!/usr/bin/env python3
"""Non-production probe for UN News RSS."""
from __future__ import annotations

import feedparser

URL = "https://news.un.org/feed/subscribe/en/news/all/rss.xml"


def main() -> int:
    parsed = feedparser.parse(
        URL,
        request_headers={"User-Agent": "swsi-un-news-probe/1.0"},
    )
    entries = len(parsed.entries or [])
    bozo = bool(getattr(parsed, "bozo", False))
    title = str(getattr(getattr(parsed, "feed", {}), "title", "") or "")
    first_titles = [
        str(getattr(entry, "title", "") or "")[:180]
        for entry in (parsed.entries or [])[:5]
    ]
    print(
        "UN NEWS PROBE: "
        f"url={URL} entries={entries} bozo={bozo} feed_title={title!r}"
    )
    for idx, item in enumerate(first_titles, start=1):
        print(f"UN NEWS PROBE ITEM {idx}: {item}")
    if entries <= 0:
        raise SystemExit("UN News RSS returned zero entries")
    print("UN NEWS PROBE COMPLETE: parseable, production registry unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
