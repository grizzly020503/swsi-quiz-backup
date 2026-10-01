#!/usr/bin/env python3
"""Run Stage 4 from Stage 2 history evidence and retain the exact MOJ page snapshot.

Evidence handoff:
- Stage 2 already fetched/parses MOJ LawHistory. This runner verifies that
  hash-bound sidecar and feeds those entries to the existing Stage 4 logic,
  avoiding a second LawHistory request.
- Stage 4 still selects the exact exam-window version and fetches that official
  LawAll/LawOldVer page once. The exact accepted page is captured as normalized
  all-article evidence for Stage 6, avoiding a second full-text request there.

No question/grading fields are read or mutated and historical_version_checked
remains false.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import historical_law_article_resolver as stage3
import historical_law_oldver_stage4 as stage4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE3 = stage4.DEFAULT_STAGE3
DEFAULT_WATCH = stage4.DEFAULT_WATCH
DEFAULT_EXAM_DATES = stage4.DEFAULT_EXAM_DATES
DEFAULT_HISTORY_SNAPSHOT = ROOT / "auto/qa/historical_law_history_snapshot.v1.json"
DEFAULT_OUTPUT = stage4.DEFAULT_OUTPUT


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_sha256(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(raw)


def verified_history_bundles(snapshot: dict) -> dict[str, tuple[str, list[dict]]]:
    """Verify Stage 2 history sidecar and return pcode -> (official URL, entries)."""
    if snapshot.get("schema_version") != 1:
        raise ValueError("unsupported Stage 2 history snapshot schema")
    bundles: dict[str, tuple[str, list[dict]]] = {}
    for row in snapshot.get("records") or []:
        pcode = str(row.get("pcode") or "").upper()
        if not pcode:
            continue
        if row.get("status") != "official_history_ready":
            continue
        url = str(row.get("official_history_url") or "")
        expected_url = stage4.MOJ_HISTORY.format(pcode=pcode)
        if url != expected_url:
            raise ValueError(f"Stage 2 history URL mismatch for {pcode}")
        entries = row.get("entries") or []
        expected_hash = str(row.get("entries_sha256") or "")
        if not entries or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError(f"Stage 2 history evidence missing for {pcode}")
        if _payload_sha256(entries) != expected_hash:
            raise ValueError(f"Stage 2 history hash mismatch for {pcode}")
        bundles[pcode] = (url, entries)
    return bundles


def all_articles_from_verified_page(page_html: str) -> list[dict]:
    """Normalize all articles from the exact MOJ page accepted by Stage 4."""
    primary = stage3.parse_law_articles(page_html)
    fallback = stage4._oldver_articles_from_html(page_html)
    merged: dict[str, dict] = {}
    for row in primary + fallback:
        article_no = str(row.get("article_no") or "")
        text = stage3.normalize_text(row.get("text") or "")
        if not article_no or not text:
            continue
        if article_no not in merged or len(text) > len(str(merged[article_no].get("text") or "")):
            merged[article_no] = {
                "article_no": article_no,
                "text": text,
                "sha256": stage4.article_fingerprint(text),
            }
    return sorted(merged.values(), key=lambda row: stage4.hp.article_key(str(row["article_no"])))


class CaptureSession:
    """requests.Session proxy that remembers the latest response body per URL."""

    def __init__(self, session: Any):
        self._session = session
        self.pages: dict[str, str] = {}

    def get(self, url: str, *args: Any, **kwargs: Any):
        response = self._session.get(url, *args, **kwargs)
        self.pages[str(url)] = str(getattr(response, "text", "") or "")
        return response

    def close(self) -> None:
        self._session.close()


def attach_verified_snapshots(report: dict, pages: dict[str, str]) -> dict:
    snapshot_count = 0
    snapshot_article_count = 0
    for row in report.get("records") or []:
        if row.get("status") != "historical_text_evidence_ready":
            continue
        selected = row.get("selected_version") or {}
        url = str(selected.get("url") or "")
        page = pages.get(url, "")
        if not page or not stage4._page_identity_ok(page):
            row["status"] = "source_snapshot_unavailable"
            row.pop("eligible_for_historical_version_checked", None)
            continue

        articles = all_articles_from_verified_page(page)
        target = str(row.get("suggested_article") or "")
        target_row = next((a for a in articles if a.get("article_no") == target), None)
        expected = str(row.get("historical_article_sha256") or "")
        if not target_row or target_row.get("sha256") != expected:
            row["status"] = "source_snapshot_identity_mismatch"
            row.pop("eligible_for_historical_version_checked", None)
            continue

        page_sha = _sha256_text(page)
        snapshot_id = _sha256_text(f"{url}\n{page_sha}")
        row["historical_version_snapshot"] = {
            "snapshot_id": snapshot_id,
            "source_url": url,
            "source_identity_method": "stage4_moj_title",
            "page_sha256": page_sha,
            "article_count": len(articles),
            "articles": articles,
        }
        snapshot_count += 1
        snapshot_article_count += len(articles)

    from collections import Counter
    counts = Counter(str(row.get("status") or "") for row in report.get("records") or [])
    report["schema_version"] = 4
    report["status_counts"] = dict(sorted(counts.items()))
    report["historical_text_evidence_ready_count"] = counts.get("historical_text_evidence_ready", 0)
    report["eligible_for_historical_version_checked_count"] = sum(
        bool(row.get("eligible_for_historical_version_checked"))
        for row in report.get("records") or []
    )
    report["verified_snapshot_count"] = snapshot_count
    report["verified_snapshot_article_count"] = snapshot_article_count
    report["method"] = (
        str(report.get("method") or "")
        + "; reuse hash-bound Stage2 LawHistory evidence and retain normalized all-article snapshot from the exact MOJ page accepted by Stage4"
    )
    return report


def run(
    stage3_report: dict,
    watch: dict,
    exam_dates: dict,
    history_snapshot: dict,
    session: CaptureSession,
) -> dict:
    bundles = verified_history_bundles(history_snapshot)
    original_history_bundle = stage4._history_bundle

    def from_stage2_snapshot(_session: Any, pcode: str):
        key = str(pcode or "").upper()
        bundle = bundles.get(key)
        if bundle is None:
            raise RuntimeError(f"Stage2 history snapshot unavailable for {key}")
        return bundle

    stage4._history_bundle = from_stage2_snapshot
    try:
        report = stage4.build_report(stage3_report, watch, exam_dates, session)
    finally:
        stage4._history_bundle = original_history_bundle
    report["stage2_history_snapshot_bundle_count"] = len(bundles)
    return attach_verified_snapshots(report, session.pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage3", default=str(DEFAULT_STAGE3))
    parser.add_argument("--legal-watch-report", default=str(DEFAULT_WATCH))
    parser.add_argument("--exam-dates", default=str(DEFAULT_EXAM_DATES))
    parser.add_argument("--history-snapshot", default=str(DEFAULT_HISTORY_SNAPSHOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage3_report = json.loads(Path(args.stage3).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    exam_dates = json.loads(Path(args.exam_dates).read_text(encoding="utf-8"))
    history_snapshot = json.loads(Path(args.history_snapshot).read_text(encoding="utf-8"))

    import requests
    session = CaptureSession(requests.Session())
    try:
        report = run(stage3_report, watch, exam_dates, history_snapshot, session)
    finally:
        session.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_errors = []
    for row in report.get("records") or []:
        error = str(row.get("source_error") or "")
        if error and error not in source_errors:
            source_errors.append(error)
        if len(source_errors) >= 5:
            break
    print(json.dumps({
        "stage3_machine_candidate_count": report.get("stage3_machine_candidate_count"),
        "record_count": report.get("record_count"),
        "status_counts": report.get("status_counts"),
        "stage2_history_snapshot_bundle_count": report.get("stage2_history_snapshot_bundle_count"),
        "historical_text_evidence_ready_count": report.get("historical_text_evidence_ready_count"),
        "verified_snapshot_count": report.get("verified_snapshot_count"),
        "verified_snapshot_article_count": report.get("verified_snapshot_article_count"),
        "source_error_samples": source_errors,
        "historical_version_checked_count": report.get("historical_version_checked_count"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
