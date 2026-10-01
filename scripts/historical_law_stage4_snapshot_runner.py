#!/usr/bin/env python3
"""Hybrid Stage 4 evidence runner with one-source-one-fetch handoff.

- Stage 2 already fetched MOJ LawHistory; this runner verifies/reuses its
  hash-bound parsed amendment snapshot instead of fetching LawHistory again.
- Current selected versions use the target-only snapshot produced from the
  official MOJ Open API ZIP/JSON corpus. No LawAll HTML request is made.
- Historical selected versions still use official MOJ LawOldVer HTML because the
  Open API publishes the current corpus only. HTTP-200 MOJ error pages are
  retried with backoff and remain fail-closed if identity never validates.
- Every accepted source becomes a hash-bound all-article snapshot for Stage 6.

No official answer/grading field is read or mutated and
historical_version_checked is never set true.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import historical_law_article_resolver as stage3
import historical_law_oldver_stage4 as stage4
import historical_law_provenance_core as hp

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE3 = stage4.DEFAULT_STAGE3
DEFAULT_WATCH = stage4.DEFAULT_WATCH
DEFAULT_EXAM_DATES = stage4.DEFAULT_EXAM_DATES
DEFAULT_HISTORY_SNAPSHOT = ROOT / "auto/qa/historical_law_history_snapshot.v1.json"
DEFAULT_API_TARGETS = ROOT / "auto/qa/historical_law_moj_api_targets.v1.json"
DEFAULT_OUTPUT = stage4.DEFAULT_OUTPUT
FULLTEXT_IDENTITY_ATTEMPTS = 4
MOJ_API_ENDPOINTS = {
    "https://law.moj.gov.tw/api/ch/law/json",
    "https://law.moj.gov.tw/api/ch/order/json",
}


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


def verified_api_targets(snapshot: dict) -> dict[str, dict]:
    if snapshot.get("schema_version") != 1:
        raise ValueError("unsupported MOJ Open API target snapshot schema")
    targets: dict[str, dict] = {}
    for row in snapshot.get("records") or []:
        pcode = str(row.get("pcode") or "").upper()
        endpoint = str(row.get("endpoint") or "")
        law_name = str(row.get("law_name") or "")
        law_url = str(row.get("law_url") or "")
        articles = row.get("articles") or []
        if not pcode or endpoint not in MOJ_API_ENDPOINTS or not law_name or not law_url:
            raise ValueError(f"invalid MOJ API target identity for {pcode or 'missing'}")
        if (hp.pcode_from_url(law_url) or "").upper() != pcode:
            raise ValueError(f"MOJ API target URL PCode mismatch for {pcode}")
        if int(row.get("article_count") or -1) != len(articles) or not articles:
            raise ValueError(f"MOJ API target article count mismatch for {pcode}")
        if _payload_sha256(articles) != str(row.get("articles_sha256") or ""):
            raise ValueError(f"MOJ API target article payload hash mismatch for {pcode}")
        identity = {
            "endpoint": endpoint,
            "collection": row.get("collection"),
            "update_date": row.get("update_date"),
            "pcode": pcode,
            "law_name": law_name,
            "law_url": law_url,
            "modified_date": row.get("modified_date"),
            "article_count": len(articles),
            "articles_sha256": row.get("articles_sha256"),
        }
        if _payload_sha256(identity) != str(row.get("source_identity_sha256") or ""):
            raise ValueError(f"MOJ API source identity hash mismatch for {pcode}")
        normalized: list[dict] = []
        for article in articles:
            no = str(article.get("article_no") or "")
            text = stage3.normalize_text(article.get("text") or "")
            sha = str(article.get("sha256") or "")
            if not no or not text or _sha256_text(text) != sha:
                raise ValueError(f"MOJ API article hash mismatch for {pcode} article {no or 'missing'}")
            normalized.append({"article_no": no, "text": text, "sha256": sha})
        targets[pcode] = {**row, "articles": normalized}
    return targets


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
                "sha256": _sha256_text(text),
            }
    return sorted(merged.values(), key=lambda row: hp.article_key(str(row["article_no"])))


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
    last_page = ""
    last_error: Exception | None = None
    for attempt in range(FULLTEXT_IDENTITY_ATTEMPTS):
        try:
            response = session.get(url, timeout=stage4.LIVE_TIMEOUT, headers={"User-Agent": stage4.UA})
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
    raise RuntimeError(f"MOJ historical full-text fetch produced no response: {url}")


def _api_ready_record(
    base: dict,
    selected: dict,
    history_url: str,
    pcode: str,
    law_name: str,
    api_row: dict | None,
    exam: dict,
    start_date: str,
    end_date: str,
) -> dict:
    if api_row is None:
        return {
            **base,
            "status": "source_failure",
            "source_error": f"MOJ Open API target snapshot missing for {pcode}",
            "official_history_url": history_url,
            "selected_version": selected,
        }
    if hp.clean_text(api_row.get("law_name") or "") != hp.clean_text(law_name):
        return {
            **base,
            "status": "source_identity_mismatch",
            "official_history_url": history_url,
            "selected_version": selected,
            "source_error": "MOJ Open API law-name identity mismatch",
        }
    if (hp.pcode_from_url(str(api_row.get("law_url") or "")) or "").upper() != pcode.upper():
        return {
            **base,
            "status": "source_identity_mismatch",
            "official_history_url": history_url,
            "selected_version": selected,
            "source_error": "MOJ Open API PCode identity mismatch",
        }
    target = str(base.get("suggested_article") or "")
    articles = api_row.get("articles") or []
    target_row = next((row for row in articles if str(row.get("article_no") or "") == target), None)
    if target_row is None:
        return {
            **base,
            "status": "article_missing_in_selected_version",
            "official_history_url": history_url,
            "selected_version": selected,
            "source_identity_method": "moj_open_api_current",
        }
    article_text = stage3.normalize_text(target_row.get("text") or "")
    fingerprint = _sha256_text(article_text)
    if fingerprint != str(target_row.get("sha256") or ""):
        return {
            **base,
            "status": "source_identity_mismatch",
            "official_history_url": history_url,
            "selected_version": selected,
            "source_error": "MOJ Open API target article fingerprint mismatch",
        }
    snapshot_id = _payload_sha256({
        "source_identity_sha256": api_row.get("source_identity_sha256"),
        "selected_version_url": selected.get("url"),
        "articles_sha256": api_row.get("articles_sha256"),
    })
    return {
        **base,
        "status": "historical_text_evidence_ready",
        "eligible_for_historical_version_checked": True,
        "exam_start_date": start_date,
        "exam_end_date": end_date,
        "exam_date_source_url": exam.get("source_url"),
        "official_history_url": history_url,
        "selected_version": selected,
        "historical_article_sha256": fingerprint,
        "historical_article_char_count": len(article_text),
        "historical_article_excerpt": article_text[:180],
        "source_identity_method": "moj_open_api_current",
        "historical_version_snapshot": {
            "snapshot_id": snapshot_id,
            "source_url": selected.get("url"),
            "source_identity_method": "moj_open_api_current",
            "api_endpoint": api_row.get("endpoint"),
            "api_update_date": api_row.get("update_date"),
            "api_law_url": api_row.get("law_url"),
            "api_source_identity_sha256": api_row.get("source_identity_sha256"),
            "evidence_sha256": api_row.get("articles_sha256"),
            "article_count": len(articles),
            "articles": articles,
        },
    }


def _oldver_ready_record(
    base: dict,
    selected: dict,
    history_url: str,
    page: str,
    exam: dict,
    start_date: str,
    end_date: str,
) -> dict:
    if not stage4._page_identity_ok(page):
        return {
            **base,
            "status": "source_identity_mismatch",
            "official_history_url": history_url,
            "selected_version": selected,
            "source_identity_method": "stage4_moj_title",
        }
    articles = all_articles_from_verified_page(page)
    target = str(base.get("suggested_article") or "")
    target_row = next((row for row in articles if row.get("article_no") == target), None)
    if target_row is None:
        return {
            **base,
            "status": "article_missing_in_selected_version",
            "official_history_url": history_url,
            "selected_version": selected,
            "source_identity_method": "stage4_moj_title",
        }
    article_text = str(target_row.get("text") or "")
    page_sha = _sha256_text(page)
    return {
        **base,
        "status": "historical_text_evidence_ready",
        "eligible_for_historical_version_checked": True,
        "exam_start_date": start_date,
        "exam_end_date": end_date,
        "exam_date_source_url": exam.get("source_url"),
        "official_history_url": history_url,
        "selected_version": selected,
        "historical_article_sha256": str(target_row.get("sha256") or ""),
        "historical_article_char_count": len(article_text),
        "historical_article_excerpt": article_text[:180],
        "source_identity_method": "stage4_moj_title",
        "historical_version_snapshot": {
            "snapshot_id": _sha256_text(f"{selected.get('url')}\n{page_sha}"),
            "source_url": selected.get("url"),
            "source_identity_method": "stage4_moj_title",
            "page_sha256": page_sha,
            "evidence_sha256": _payload_sha256(articles),
            "article_count": len(articles),
            "articles": articles,
        },
    }


def build_hybrid_report(
    stage3_report: dict,
    watch: dict,
    exam_dates: dict,
    history_snapshot: dict,
    api_snapshot: dict,
    session: CaptureSession,
) -> dict:
    history_bundles = verified_history_bundles(history_snapshot)
    api_targets = verified_api_targets(api_snapshot)
    watch_map = hp.watch_record_map(watch)
    dates = stage4.exam_date_map(exam_dates)
    candidates = [row for row in (stage3_report.get("records") or []) if row.get("route") == "machine_candidate"]
    page_cache: dict[str, str | Exception] = {}
    records: list[dict] = []

    for row in candidates:
        law_name = str(row.get("law_name") or "")
        article = str(row.get("suggested_article") or "")
        exam_code = str(row.get("exam_code") or "")
        base = {
            "law_name": law_name,
            "question_id": row.get("question_id"),
            "exam_code": exam_code,
            "suggested_article": article or None,
            "stage3_confidence": row.get("confidence"),
            "stage3_decision_reason": row.get("decision_reason"),
            "historical_version_checked": False,
        }
        if not article:
            records.append({**base, "status": "stage3_candidate_missing_article"})
            continue
        exam = dates.get(exam_code)
        if not exam or exam.get("status") != "official_pinned":
            records.append({**base, "status": "exam_date_missing"})
            continue
        start_date = str(exam.get("start_date") or "")
        end_date = str(exam.get("end_date") or start_date)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_date):
            records.append({**base, "status": "exam_date_missing"})
            continue
        watch_row = watch_map.get(hp.clean_text(law_name)) or {}
        official_url = str(watch_row.get("official_url") or "")
        pcode = (hp.pcode_from_url(official_url) or "").upper()
        if not pcode:
            records.append({**base, "status": "law_source_missing"})
            continue
        bundle = history_bundles.get(pcode)
        if bundle is None:
            records.append({
                **base,
                "status": "source_failure",
                "source_error": f"Stage2 history snapshot unavailable for {pcode}",
            })
            continue
        history_url, entries = bundle
        versions = stage4.versions_for_article(entries, pcode, official_url, watch_row.get("official_modified_date"), article)
        status, start_version, end_version = stage4.select_exam_window_version(versions, start_date, end_date)
        if status != "ok":
            result = {
                **base,
                "status": status,
                "exam_start_date": start_date,
                "exam_end_date": end_date,
                "official_history_url": history_url,
                "start_version": start_version,
                "end_version": end_version,
            }
            if status == "effective_date_review":
                result["unresolved_effective_versions"] = stage4.unresolved_effective_date_risk(versions, end_date)
            records.append(result)
            continue
        assert start_version is not None
        selected = start_version
        if selected.get("kind") == "current":
            records.append(_api_ready_record(
                base, selected, history_url, pcode, law_name, api_targets.get(pcode), exam, start_date, end_date
            ))
            continue

        version_url = str(selected.get("url") or "")
        if version_url not in page_cache:
            try:
                page_cache[version_url] = _identity_retry_get(session, version_url)
            except Exception as exc:
                page_cache[version_url] = exc
        page = page_cache[version_url]
        if isinstance(page, Exception):
            records.append({
                **base,
                "status": "source_failure",
                "official_history_url": history_url,
                "selected_version": selected,
                "source_error": f"{type(page).__name__}: {page}",
            })
            continue
        records.append(_oldver_ready_record(base, selected, history_url, page, exam, start_date, end_date))

    counts = Counter(str(row.get("status") or "") for row in records)
    identity_counts = Counter(
        str(row.get("source_identity_method")) for row in records if row.get("source_identity_method")
    )
    ready_rows = [row for row in records if row.get("status") == "historical_text_evidence_ready"]
    return {
        "schema_version": 5,
        "method": (
            "Stage3 machine candidate -> hash-bound Stage2 MOJ history -> article-scoped exam-window version; "
            "current versions from hash-bound official MOJ Open API target snapshot; historical versions from "
            "identity-verified MOJ LawOldVer HTML with transient-error retry; all accepted sources become "
            "hash-bound all-article snapshots for Stage6; evidence only"
        ),
        "stage3_machine_candidate_count": len(candidates),
        "record_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "source_identity_method_counts": dict(sorted(identity_counts.items())),
        "stage2_history_snapshot_bundle_count": len(history_bundles),
        "moj_api_target_snapshot_count": len(api_targets),
        "historical_text_evidence_ready_count": counts.get("historical_text_evidence_ready", 0),
        "verified_snapshot_count": len(ready_rows),
        "verified_snapshot_article_count": sum(
            int((row.get("historical_version_snapshot") or {}).get("article_count") or 0) for row in ready_rows
        ),
        "current_api_ready_count": sum(
            row.get("status") == "historical_text_evidence_ready" and row.get("source_identity_method") == "moj_open_api_current"
            for row in records
        ),
        "oldver_html_ready_count": sum(
            row.get("status") == "historical_text_evidence_ready" and row.get("source_identity_method") == "stage4_moj_title"
            for row in records
        ),
        "fulltext_unique_url_count": len(session.request_counts),
        "fulltext_request_count_total": sum(session.request_counts.values()),
        "fulltext_request_counts": dict(sorted(session.request_counts.items())),
        "eligible_for_historical_version_checked_count": sum(bool(row.get("eligible_for_historical_version_checked")) for row in records),
        "historical_version_checked_count": 0,
        "protected_core_mutation_count": 0,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage3", default=str(DEFAULT_STAGE3))
    parser.add_argument("--legal-watch-report", default=str(DEFAULT_WATCH))
    parser.add_argument("--exam-dates", default=str(DEFAULT_EXAM_DATES))
    parser.add_argument("--history-snapshot", default=str(DEFAULT_HISTORY_SNAPSHOT))
    parser.add_argument("--api-targets", default=str(DEFAULT_API_TARGETS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage3_report = json.loads(Path(args.stage3).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    exam_dates = json.loads(Path(args.exam_dates).read_text(encoding="utf-8"))
    history_snapshot = json.loads(Path(args.history_snapshot).read_text(encoding="utf-8"))
    api_snapshot = json.loads(Path(args.api_targets).read_text(encoding="utf-8"))

    import requests
    session = CaptureSession(requests.Session())
    try:
        report = build_hybrid_report(stage3_report, watch, exam_dates, history_snapshot, api_snapshot, session)
    finally:
        session.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage3_machine_candidate_count": report.get("stage3_machine_candidate_count"),
        "record_count": report.get("record_count"),
        "status_counts": report.get("status_counts"),
        "source_identity_method_counts": report.get("source_identity_method_counts"),
        "stage2_history_snapshot_bundle_count": report.get("stage2_history_snapshot_bundle_count"),
        "moj_api_target_snapshot_count": report.get("moj_api_target_snapshot_count"),
        "current_api_ready_count": report.get("current_api_ready_count"),
        "oldver_html_ready_count": report.get("oldver_html_ready_count"),
        "fulltext_unique_url_count": report.get("fulltext_unique_url_count"),
        "fulltext_request_count_total": report.get("fulltext_request_count_total"),
        "verified_snapshot_count": report.get("verified_snapshot_count"),
        "historical_version_checked_count": report.get("historical_version_checked_count"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
