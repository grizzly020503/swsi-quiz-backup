#!/usr/bin/env python3
"""Non-production probe for official international current-affairs feeds."""
from __future__ import annotations

import feedparser

CANDIDATES = [
    {
        "name": "UN News English",
        "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    },
]


def main() -> int:
    for row in CANDIDATES:
        parsed = feedparser.parse(
            row["url"],
            request_headers={"User-Agent": "swsi-international-feed-probe/1.0"},
        )
        entries = len(parsed.entries or [])
        bozo = bool(getattr(parsed, "bozo", False))
        title = str(getattr(getattr(parsed, "feed", {}), "title", "") or "")
        first = str(getattr(parsed.entries[0], "title", "") or "") if entries else ""
        print(
            "INTERNATIONAL PROBE: "
            f"name={row['name']!r} url={row['url']} entries={entries} "
            f"bozo={bozo} feed_title={title!r} first_title={first[:180]!r}"
        )
    print("INTERNATIONAL PROBE COMPLETE: no production registry changes made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
