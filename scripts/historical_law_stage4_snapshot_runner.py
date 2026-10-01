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
import time
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
FULLTEXT_IDENTITY_ATTEMPTS = 4


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_sha256(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(raw)


def verified_history_bundles(snapshot: dict) -> dict[str, tuple[str, list[dict]]]:
    if snapshot.get("schema_version") != 1:
        raise ValueError("unsupported Stage 2 history snapshot schema")
    bundles: dict[str, tuple[str, list[dict]]] = {}
    for row in snapshot.get("records") or []:
        pcode = str(row.get("pcode") or "").upper()
        if not pcode or row.get("status") != "official_history_ready":
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
    def __init__(self, session: Any):
        self._session = session
        self.pages: dict[str, str] = {}
        self.request_counts: dict[str, int] = {}

    def get(self, url: str, *args: Any, **kwargs: Any):
        key = str(url)
        self.request_counts[key] = self.request_counts.get(key, 0) + 1
        response = self._session.get(url, *args, **kwargs)
        self.pages[key] = str(getattr(response, "text", "") or "")
        return response

    def close(self) -> None:
        self._session.close()


def _identity_retry_get(session: CaptureSession, url: str) -> str:
    """Retry transient MOJ HTTP-200 error/interstitial pages without weakening identity checks."""
    last_page = ""
    last_error: Exception | None = None
    for attempt in range(FULLTEXT_IDENTITY_ATTEMPTS):
        try:
            response = session.get(
                url,
                timeout=stage4.LIVE_TIMEOUT,
                headers={"User-Agent": stage4.UA},
            )
            response.raise_for_status()
            page = str(response.text or "")
            last_page = page
            if stage4._page_identity_ok(page):
                return page
        except Exception as exc:
            last_error = exc
        if attempt + 1 < FULLTEXT_IDENTITY_ATTEMPTS:
            time.sleep(2 ** attempt)
    if last_page:
        return last_page
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"MOJ full-text fetch produced no response: {url}")


def annotate_identity_diagnostics(
    report: dict,
    pages: dict[str, str],
    request_counts: dict[str, int],
) -> dict:
    diagnostic_count = 0
    for row in report.get("records") or []:
        if row.get("status") != "source_identity_mismatch":
            continue
        selected = row.get("selected_version") or {}
        url = str(selected.get("url") or "")
        raw = str(pages.get(url, "") or "")
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
        title_text = stage4.hp.clean_text(title_match.group(1)) if title_match else ""
        articles = all_articles_from_verified_page(raw) if raw else []
        target = str(row.get("suggested_article") or "")
        visible = stage4.hp.clean_text(stage4.hp.html_to_text(raw))[:220] if raw else ""
        lowered = raw.lower()
        row["identity_diagnostic"] = {
            "request_count": request_counts.get(url, 0),
            "response_char_count": len(raw),
            "response_sha256": _sha256_text(raw) if raw else None,
            "title": title_text[:180],
            "title_has_moj_brand": "全國法規資料庫" in title_text,
            "parsed_article_count": len(articles),
            "target_article_present": any(a.get("article_no") == target for a in articles),
            "visible_text_prefix": visible,
            "markers": {
                "has_moj_brand_anywhere": "全國法規資料庫" in raw,
                "has_system_message": "系統訊息" in raw,
                "has_unreachable_server": "unreachable server" in lowered,
                "has_access_denied": "access denied" in lowered,
                "has_request_blocked": "request blocked" in lowered,
                "has_captcha": "captcha" in lowered or "驗證碼" in raw,
                "has_cloudflare_challenge": "cf-chl" in lowered or "cloudflare" in lowered,
            },
        }
        diagnostic_count += 1
    report["identity_diagnostic_count"] = diagnostic_count
    return report


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
        + "; reuse hash-bound Stage2 LawHistory evidence; retry HTTP-200 MOJ error pages with exponential backoff; retain normalized all-article snapshot from the exact MOJ page accepted by Stage4"
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
    original_get = stage4._get

    def from_stage2_snapshot(_session: Any, pcode: str):
        key = str(pcode or "").upper()
        bundle = bundles.get(key)
        if bundle is None:
            raise RuntimeError(f"Stage2 history snapshot unavailable for {key}")
        return bundle

    stage4._history_bundle = from_stage2_snapshot
    stage4._get = _identity_retry_get
    try:
        report = stage4.build_report(stage3_report, watch, exam_dates, session)
    finally:
        stage4._history_bundle = original_history_bundle
        stage4._get = original_get
    report["stage2_history_snapshot_bundle_count"] = len(bundles)
    report["fulltext_unique_url_count"] = len(session.request_counts)
    report["fulltext_request_count_total"] = sum(session.request_counts.values())
    report["fulltext_request_counts"] = dict(sorted(session.request_counts.items()))
    report = annotate_identity_diagnostics(report, session.pages, session.request_counts)
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
    diagnostics = []
    for row in report.get("records") or []:
        error = str(row.get("source_error") or "")
        if error and error not in source_errors:
            source_errors.append(error)
        diagnostic = row.get("identity_diagnostic")
        if diagnostic and diagnostic not in diagnostics:
            diagnostics.append(diagnostic)
    print(json.dumps({
        "stage3_machine_candidate_count": report.get("stage3_machine_candidate_count"),
        "record_count": report.get("record_count"),
        "status_counts": report.get("status_counts"),
        "stage2_history_snapshot_bundle_count": report.get("stage2_history_snapshot_bundle_count"),
        "fulltext_unique_url_count": report.get("fulltext_unique_url_count"),
        "fulltext_request_count_total": report.get("fulltext_request_count_total"),
        "historical_text_evidence_ready_count": report.get("historical_text_evidence_ready_count"),
        "verified_snapshot_count": report.get("verified_snapshot_count"),
        "verified_snapshot_article_count": report.get("verified_snapshot_article_count"),
        "identity_diagnostic_count": report.get("identity_diagnostic_count"),
        "identity_diagnostic_samples": diagnostics[:5],
        "source_error_samples": source_errors[:5],
        "historical_version_checked_count": report.get("historical_version_checked_count"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
