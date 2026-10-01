#!/usr/bin/env python3
"""Stage 2 runner that persists the exact parsed MOJ history evidence it used.

The existing Stage 2 logic already fetches official MOJ LawHistory pages to
route 86 mappings. Historically those parsed amendment entries were discarded,
forcing Stage 4 to fetch the same LawHistory pages again. This runner preserves
that already-used read-only evidence in a hash-bound sidecar so Stage 4 can
consume it without a second LawHistory request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import historical_law_exam_date_refiner as stage2
import historical_law_provenance_core as hp

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_exam_date_stage2.v1.json"
DEFAULT_HISTORY_SNAPSHOT = ROOT / "auto/qa/historical_law_history_snapshot.v1.json"


def payload_sha256(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_history_snapshot(watch: dict, cards: list[dict], captured: tuple[dict, dict, dict]) -> dict:
    histories, history_urls, history_errors = captured
    watch_map = hp.watch_record_map(watch)
    records: list[dict] = []
    seen: set[str] = set()
    for card in cards:
        law = str(card.get("law_name") or "")
        if not law or law in seen:
            continue
        seen.add(law)
        watch_row = watch_map.get(law) or {}
        pcode = hp.pcode_from_url(watch_row.get("official_url"))
        entries = histories.get(law, []) or []
        error = history_errors.get(law)
        url = history_urls.get(law)
        records.append({
            "law_name": law,
            "pcode": pcode,
            "official_history_url": url,
            "status": "official_history_ready" if pcode and entries and not error else "source_failure",
            "entries_sha256": payload_sha256(entries) if entries else None,
            "entry_count": len(entries),
            "entries": entries,
            "source_error": error,
        })
    return {
        "schema_version": 1,
        "method": "exact parsed MOJ LawHistory entries already fetched by Stage 2; hash-bound read-only handoff to Stage 4",
        "record_count": len(records),
        "ready_count": sum(r["status"] == "official_history_ready" for r in records),
        "source_failure_count": sum(r["status"] == "source_failure" for r in records),
        "historical_version_checked_count": 0,
        "protected_core_mutation_count": 0,
        "records": records,
    }


def main() -> int:
    import requests

    parser = argparse.ArgumentParser()
    parser.add_argument("--links", default=str(hp.DEFAULT_LINKS))
    parser.add_argument("--legal-watch-report", default=str(hp.DEFAULT_WATCH))
    parser.add_argument("--exam-date-registry", default=str(stage2.DEFAULT_EXAM_DATE_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--history-snapshot-output", default=str(DEFAULT_HISTORY_SNAPSHOT))
    args = parser.parse_args()

    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    registry = stage2.load_exam_date_registry(args.exam_date_registry)
    captured: list[tuple[dict, dict, dict]] = []
    original_fetch_histories = stage2.fetch_histories

    def capturing_fetch_histories(watch_map: dict, cards: list[dict]):
        result = original_fetch_histories(watch_map, cards)
        captured.append(result)
        return result

    session = requests.Session()
    session.headers.update({"User-Agent": stage2.UA})
    stage2.fetch_histories = capturing_fetch_histories
    try:
        report = stage2.build_live_report(links, watch, session, registry)
    finally:
        stage2.fetch_histories = original_fetch_histories
        session.close()

    if len(captured) != 1:
        raise RuntimeError(f"Stage 2 history capture count must be 1, got {len(captured)}")
    snapshot = build_history_snapshot(watch, links.get("cards") or [], captured[0])

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snap_out = Path(args.history_snapshot_output)
    snap_out.parent.mkdir(parents=True, exist_ok=True)
    snap_out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "mapping_count": report.get("mapping_count"),
        "unique_question_count": report.get("unique_question_count"),
        "law_fetch_error_count": report.get("law_fetch_error_count"),
        "status_counts": report.get("status_counts"),
        "history_snapshot_record_count": snapshot.get("record_count"),
        "history_snapshot_ready_count": snapshot.get("ready_count"),
        "history_snapshot_source_failure_count": snapshot.get("source_failure_count"),
        "historical_version_checked_count": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
