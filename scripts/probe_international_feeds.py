#!/usr/bin/env python3
"""Non-production parser/quality probe for WHO and UN News RSS candidates."""
from __future__ import annotations

import time

import feedparser

from current_affairs_watch import clean_html, score_item
from current_affairs_taxonomy import (
    canonical_agencies,
    canonical_concepts,
    canonical_fact_keys,
)

CANDIDATES = [
    {
        "name": "WHO News",
        "url": "https://www.who.int/rss-feeds/news-english.xml",
        "source_type": "international",
    },
    {
        "name": "UN News",
        "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "source_type": "international",
    },
]
UA = "swsi-international-feed-probe/1.0"


def parse_with_retry(row: dict, attempts: int = 3):
    last_error = None
    parsed = None
    for attempt in range(1, attempts + 1):
        try:
            parsed = feedparser.parse(
                row["url"],
                request_headers={"User-Agent": UA},
            )
            if parsed.entries:
                return parsed, None
            last_error = getattr(parsed, "bozo_exception", "empty feed")
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            print(
                f"INTL PROBE RETRY: {row['name']} attempt={attempt} "
                f"error={last_error}"
            )
            time.sleep(0.5 * attempt)
    return parsed, last_error


def probe(row: dict) -> bool:
    parsed, error = parse_with_retry(row)
    entries = list(getattr(parsed, "entries", []) or []) if parsed is not None else []
    bozo = bool(getattr(parsed, "bozo", False)) if parsed is not None else True
    feed = getattr(parsed, "feed", {}) if parsed is not None else {}
    feed_title = str(getattr(feed, "title", "") or feed.get("title", "") if isinstance(feed, dict) else "")
    print(
        f"INTL PROBE: name={row['name']} entries={len(entries)} "
        f"bozo={bozo} feed_title={feed_title!r} error={error!r}"
    )
    if not entries:
        return False

    accepted = 0
    for entry in entries[:12]:
        title = clean_html(getattr(entry, "title", ""))
        summary = clean_html(
            getattr(entry, "summary", "") or getattr(entry, "description", "")
        )[:600]
        text = f"{title} {summary}"
        scored = score_item(
            title,
            summary,
            "international",
            row["name"],
            row["source_type"],
        )
        concepts = sorted(canonical_concepts(text))
        agencies = sorted(canonical_agencies(text))
        facts = sorted(canonical_fact_keys(text))
        if scored:
            accepted += 1
        print(
            f"INTL ITEM: source={row['name']} accepted={bool(scored)} "
            f"score={scored[0] if scored else '-'} "
            f"category={scored[1] if scored else '-'} "
            f"concepts={concepts} agencies={agencies} facts={facts} "
            f"title={title[:180]!r}"
        )
    print(
        f"INTL PROBE SUMMARY: name={row['name']} entries={len(entries)} "
        f"accepted_top12={accepted}"
    )
    return True


def main() -> int:
    ok = True
    for row in CANDIDATES:
        ok = probe(row) and ok
    if not ok:
        raise SystemExit("INTERNATIONAL FEED PROBE FAILED: one or more candidates had no parseable entries")
    print("INTERNATIONAL FEED PROBE OK: WHO and UN News returned parseable entries; registry unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
