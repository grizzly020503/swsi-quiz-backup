#!/usr/bin/env python3
"""Build the priority-law historical-provenance report without batch-wide failure.

One unavailable/unrecognized MOJ history page must not erase evidence from the
other laws. A failed law stays fail-closed as `official_history_unavailable`,
and the fetch error is recorded at law level for follow-up.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from historical_law_provenance import (
    MOJ_HISTORY,
    fetch_history_text,
    normalize_watch_records,
    parse_history_entries,
    pcode_from_url,
    triage_question,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE_ATTEMPTS = 3


def fetch_history_entries_with_retry(pcode: str) -> list[dict]:
    """Retry transient MOJ history-page/recognition failures, then fail closed."""
    last = None
    for attempt in range(LIVE_ATTEMPTS):
        try:
            entries = parse_history_entries(fetch_history_text(pcode))
            if not entries:
                raise RuntimeError("MOJ history page parsed zero amendment entries")
            return entries
        except Exception as exc:
            last = exc
            if attempt + 1 < LIVE_ATTEMPTS:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"MOJ history unavailable after {LIVE_ATTEMPTS} attempts: {last}")


def build_report(links: dict, watch: dict, live: bool = True) -> dict:
    watch_records = normalize_watch_records(watch)
    rows = []
    fetch_errors = []
    law_summaries = []

    for card in links.get("cards") or []:
        law = card["law_name"]
        watch_row = watch_records.get(law) or {}
        pcode = pcode_from_url(watch_row.get("official_url"))
        history_url = MOJ_HISTORY.format(pcode=pcode) if pcode else None
        entries = []
        error = None

        if live and pcode:
            try:
                entries = fetch_history_entries_with_retry(pcode)
            except Exception as exc:  # source failure stays visible and fail-closed
                error = f"{type(exc).__name__}: {exc}"
                fetch_errors.append({
                    "law_name": law,
                    "pcode": pcode,
                    "official_history_url": history_url,
                    "error": error,
                })
        elif live and not pcode:
            error = "missing pcode in legal watch official_url"
            fetch_errors.append({
                "law_name": law,
                "pcode": None,
                "official_history_url": None,
                "error": error,
            })

        law_rows = []
        for q in card.get("questions") or []:
            result = triage_question(q, entries)
            result.update({
                "law_name": law,
                "official_history_url": history_url,
                "history_fetch_error": error,
            })
            rows.append(result)
            law_rows.append(result)

        law_summaries.append({
            "law_name": law,
            "pcode": pcode,
            "official_history_url": history_url,
            "history_entry_count": len(entries),
            "question_count": len(law_rows),
            "status_counts": dict(sorted(Counter(r["status"] for r in law_rows).items())),
            "fetch_error": error,
        })

    return {
        "schema_version": 1,
        "method": "explicit article + official MOJ history; retry + per-law fail-closed; no answer mutation; no keyword-only article inference",
        "live_history_fetch": live,
        "question_count": len(rows),
        "law_count": len(law_summaries),
        "law_fetch_error_count": len(fetch_errors),
        "law_fetch_errors": fetch_errors,
        "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
        "laws": law_summaries,
        "questions": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", default=str(ROOT / "data/law_question_links_priority10.v1.json"))
    ap.add_argument("--legal-watch-report", default=str(ROOT / "data/legal_watch_report.json"))
    ap.add_argument("--output", default=str(ROOT / "data/historical_law_provenance_priority10.v1.json"))
    ap.add_argument("--no-live", action="store_true")
    args = ap.parse_args()

    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    report = build_report(links, watch, live=not args.no_live)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "question_count": report["question_count"],
        "law_count": report["law_count"],
        "law_fetch_error_count": report["law_fetch_error_count"],
        "status_counts": report["status_counts"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
