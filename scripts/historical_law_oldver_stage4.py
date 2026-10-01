#!/usr/bin/env python3
"""Stage 4: build read-only historical MOJ article-text evidence.

Consumes Stage 3 machine candidates only. It discovers official MOJ historical
version links from LawHistory, selects the version that spans the official exam
window, and fingerprints the suggested article text from that version.

Safety boundary:
- never reads or mutates official answer/grading fields;
- never sets historical_version_checked=true;
- any ambiguous exam-window version, special effective-date history,
  source failure, or missing article remains review/fail-closed.
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import historical_law_provenance_core as hp
import historical_law_article_resolver as stage3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE3 = ROOT / "auto/qa/historical_law_article_stage3.v1.json"
DEFAULT_WATCH = ROOT / "data/legal_watch_report.json"
DEFAULT_EXAM_DATES = ROOT / "data/moex_social_worker_exam_dates.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_oldver_stage4.v1.json"

UA = "swsi-historical-law-oldver-stage4/1.0 (+private educational question bank)"
MOJ_HISTORY = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode={pcode}"
MOJ_OLD = "https://law.moj.gov.tw/LawClass/LawOldVer.aspx"
LIVE_ATTEMPTS = 3
LIVE_TIMEOUT = 30


def _query_dict(url: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in parse_qsl(urlparse(url).query, keep_blank_values=True):
        out[key.lower()] = value
    return out


def _canonical_oldver_url(pcode: str, lnndate: str, lser: str | None) -> str:
    query = {"pcode": pcode.upper(), "lnndate": lnndate}
    if lser:
        query["lser"] = lser
    return MOJ_OLD + "?" + urlencode(query)


def parse_oldver_links(history_html: str, pcode: str) -> list[dict]:
    raw = html_lib.unescape(str(history_html or ""))
    hrefs = re.findall(
        r"href\s*=\s*[\"']([^\"']*LawOldVer(?:_Vaild)?\.aspx\?[^\"']+)[\"']",
        raw,
        flags=re.I,
    )
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for href in hrefs:
        absolute = urljoin("https://law.moj.gov.tw/LawClass/", href)
        q = _query_dict(absolute)
        link_pcode = (q.get("pcode") or "").upper()
        lnndate = re.sub(r"\D", "", q.get("lnndate") or "")
        lser = (q.get("lser") or "").strip() or None
        if link_pcode != pcode.upper() or not re.fullmatch(r"\d{8}", lnndate):
            continue
        try:
            iso = date(int(lnndate[:4]), int(lnndate[4:6]), int(lnndate[6:8])).isoformat()
        except ValueError:
            continue
        url = _canonical_oldver_url(link_pcode, lnndate, lser)
        key = (iso, lser or "", url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "kind": "oldver",
            "version_date": iso,
            "lnndate": lnndate,
            "lser": lser,
            "url": url,
        })
    rows.sort(key=lambda row: (row["version_date"], row.get("lser") or ""))
    return rows


def add_current_version(
    versions: list[dict], official_url: str, official_modified_date: str | None
) -> list[dict]:
    out = [dict(row) for row in versions]
    value = str(official_modified_date or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        out.append({
            "kind": "current",
            "version_date": value,
            "lnndate": value.replace("-", ""),
            "lser": None,
            "url": official_url,
        })
    dedup: dict[tuple[str, str], dict] = {}
    for row in out:
        dedup[(row["version_date"], row["url"])] = row
    return sorted(dedup.values(), key=lambda row: (row["version_date"], row["kind"]))


def select_version(versions: list[dict], on_date: str) -> dict | None:
    eligible = [row for row in versions if row.get("version_date") and row["version_date"] <= on_date]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row["version_date"], row["kind"] == "current"))


def select_exam_window_version(
    versions: list[dict], start_date: str, end_date: str
) -> tuple[str, dict | None, dict | None]:
    start = select_version(versions, start_date)
    end = select_version(versions, end_date)
    if not start or not end:
        return "history_version_unavailable", start, end
    if (start["url"], start["version_date"]) != (end["url"], end["version_date"]):
        return "exam_window_version_conflict", start, end
    return "ok", start, end


def article_fingerprint(text: str) -> str:
    normalized = stage3.normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _entry_date(entry: dict) -> str | None:
    value = entry.get("date")
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return None


def has_effective_date_risk(history_entries: list[dict], article: str, exam_end: str) -> bool:
    for entry in history_entries:
        if not hp.entry_affects_article(entry, article):
            continue
        entry_date = _entry_date(entry)
        if entry_date and entry_date > exam_end:
            continue
        if entry.get("special_effective_date"):
            return True
    return False


def exam_date_map(payload: dict) -> dict[str, dict]:
    out = {}
    for row in payload.get("records") or []:
        code = str(row.get("exam_code") or "").strip()
        if code:
            out[code] = row
    return out


def _get(session: Any, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(LIVE_ATTEMPTS):
        try:
            response = session.get(url, timeout=LIVE_TIMEOUT, headers={"User-Agent": UA})
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt + 1 < LIVE_ATTEMPTS:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _history_bundle(session: Any, pcode: str) -> tuple[str, list[dict], list[dict]]:
    url = MOJ_HISTORY.format(pcode=pcode)
    raw = _get(session, url)
    history_text = hp.html_to_text(raw)
    if "沿革" not in history_text:
        raise RuntimeError(f"MOJ history page not recognized: {url}")
    links = parse_oldver_links(raw, pcode)
    entries = hp.parse_history_entries(history_text)
    return url, links, entries


def _article_from_page(page_html: str, article_no: str) -> dict | None:
    articles = stage3.parse_law_articles(page_html)
    return next((row for row in articles if row.get("article_no") == article_no), None)


def build_report(stage3_report: dict, watch: dict, exam_dates: dict, session: Any) -> dict:
    watch_map = hp.watch_record_map(watch)
    dates = exam_date_map(exam_dates)
    candidates = [
        row for row in (stage3_report.get("records") or [])
        if row.get("route") == "machine_candidate"
    ]

    history_cache: dict[str, object] = {}
    page_cache: dict[str, object] = {}
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
        pcode = hp.pcode_from_url(official_url)
        if not pcode:
            records.append({**base, "status": "law_source_missing"})
            continue

        if pcode not in history_cache:
            try:
                history_cache[pcode] = _history_bundle(session, pcode)
            except Exception as exc:
                history_cache[pcode] = exc
        history_bundle = history_cache[pcode]
        if isinstance(history_bundle, Exception):
            records.append({
                **base,
                "status": "source_failure",
                "source_error": f"{type(history_bundle).__name__}: {history_bundle}",
            })
            continue

        history_url, old_versions, history_entries = history_bundle
        versions = add_current_version(
            old_versions,
            official_url,
            watch_row.get("official_modified_date"),
        )
        version_status, start_version, end_version = select_exam_window_version(
            versions, start_date, end_date
        )
        if version_status != "ok":
            records.append({
                **base,
                "status": version_status,
                "exam_start_date": start_date,
                "exam_end_date": end_date,
                "official_history_url": history_url,
                "start_version": start_version,
                "end_version": end_version,
            })
            continue

        assert start_version is not None
        if has_effective_date_risk(history_entries, article, end_date):
            records.append({
                **base,
                "status": "effective_date_review",
                "exam_start_date": start_date,
                "exam_end_date": end_date,
                "official_history_url": history_url,
                "selected_version": start_version,
            })
            continue

        version_url = start_version["url"]
        if version_url not in page_cache:
            try:
                page_cache[version_url] = _get(session, version_url)
            except Exception as exc:
                page_cache[version_url] = exc
        page = page_cache[version_url]
        if isinstance(page, Exception):
            records.append({
                **base,
                "status": "source_failure",
                "official_history_url": history_url,
                "selected_version": start_version,
                "source_error": f"{type(page).__name__}: {page}",
            })
            continue

        article_row = _article_from_page(page, article)
        if not article_row or not stage3.normalize_text(article_row.get("text") or ""):
            records.append({
                **base,
                "status": "article_missing_in_selected_version",
                "official_history_url": history_url,
                "selected_version": start_version,
            })
            continue

        article_text = stage3.normalize_text(article_row["text"])
        records.append({
            **base,
            "status": "historical_text_evidence_ready",
            "eligible_for_historical_version_checked": True,
            "exam_start_date": start_date,
            "exam_end_date": end_date,
            "exam_date_source_url": exam.get("source_url"),
            "official_history_url": history_url,
            "selected_version": start_version,
            "historical_article_sha256": article_fingerprint(article_text),
            "historical_article_char_count": len(article_text),
            "historical_article_excerpt": article_text[:180],
        })

    counts = Counter(row["status"] for row in records)
    return {
        "schema_version": 1,
        "method": (
            "Stage3 machine candidate -> official pinned exam window -> MOJ LawHistory "
            "LawOldVer/current version selection -> exact suggested-article text fingerprint; "
            "read-only evidence only"
        ),
        "stage3_machine_candidate_count": len(candidates),
        "record_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "historical_text_evidence_ready_count": counts.get("historical_text_evidence_ready", 0),
        "eligible_for_historical_version_checked_count": sum(
            bool(row.get("eligible_for_historical_version_checked")) for row in records
        ),
        "historical_version_checked_count": 0,
        "protected_core_mutation_count": 0,
        "records": records,
    }


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
    session = requests.Session()
    try:
        report = build_report(stage3_report, watch, exam_dates, session)
    finally:
        session.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage3_machine_candidate_count": report["stage3_machine_candidate_count"],
        "record_count": report["record_count"],
        "status_counts": report["status_counts"],
        "historical_text_evidence_ready_count": report["historical_text_evidence_ready_count"],
        "eligible_for_historical_version_checked_count": report["eligible_for_historical_version_checked_count"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
