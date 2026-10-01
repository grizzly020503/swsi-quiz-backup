#!/usr/bin/env python3
"""Run Stage 4 and retain the exact verified MOJ article snapshot for Stage 6.

Stage 4 remains the source/provenance gate. This runner delegates all version,
effective-date, exam-window and page-identity decisions to the existing Stage 4
implementation, while capturing the exact HTTP response that Stage 4 accepted.
For every ready record it stores a normalized all-article snapshot plus hashes.

This removes the need for Stage 6 to make a second, independently unstable HTTP
request. The snapshot is read-only evidence only: no question/grading fields are
read or mutated and historical_version_checked remains false.
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
DEFAULT_OUTPUT = stage4.DEFAULT_OUTPUT


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
            # A ready Stage 4 row without its exact accepted page is a runner
            # integrity failure. Fail closed rather than manufacturing evidence.
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

    # Recompute status counts because attaching a snapshot can only fail closed.
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
        + "; retain normalized all-article snapshot from the exact MOJ page already accepted by Stage 4"
    )
    return report


def run(stage3_report: dict, watch: dict, exam_dates: dict, session: CaptureSession) -> dict:
    report = stage4.build_report(stage3_report, watch, exam_dates, session)
    return attach_verified_snapshots(report, session.pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage3", default=str(DEFAULT_STAGE3))
    parser.add_argument("--legal-watch-report", default=str(DEFAULT_WATCH))
    parser.add_argument("--exam-dates", default=str(DEFAULT_EXAM_DATES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage3_report = json.loads(Path(args.stage3).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    exam_dates = json.loads(Path(args.exam_dates).read_text(encoding="utf-8"))

    import requests
    session = CaptureSession(requests.Session())
    try:
        report = run(stage3_report, watch, exam_dates, session)
    finally:
        session.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage3_machine_candidate_count": report.get("stage3_machine_candidate_count"),
        "record_count": report.get("record_count"),
        "status_counts": report.get("status_counts"),
        "historical_text_evidence_ready_count": report.get("historical_text_evidence_ready_count"),
        "verified_snapshot_count": report.get("verified_snapshot_count"),
        "verified_snapshot_article_count": report.get("verified_snapshot_article_count"),
        "historical_version_checked_count": report.get("historical_version_checked_count"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
