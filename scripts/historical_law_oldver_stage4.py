#!/usr/bin/env python3
"""Stage 4: build read-only historical MOJ article-text evidence.

Consumes Stage 3 ``machine_candidate`` rows only.  MOJ ``LawHistory`` pages do
not expose links to every historical full-text page, so Stage 4 derives the
official ``LawOldVer`` URL from each promulgation date listed by MOJ, resolves
known effective-date rules, selects the version spanning the official exam
window, and fingerprints the suggested article text from that official version.

Safety boundary
---------------
- never reads or mutates official answer/grading fields;
- never sets ``historical_version_checked=true``;
- unresolved effective dates, exam-window version conflicts, source failures,
  or a missing suggested article remain fail-closed review states;
- Stage 4 produces evidence only.  Promotion is a later explicit gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import historical_law_provenance_core as hp
import historical_law_article_resolver as stage3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE3 = ROOT / "auto/qa/historical_law_article_stage3.v1.json"
DEFAULT_WATCH = ROOT / "data/legal_watch_report.json"
DEFAULT_EXAM_DATES = ROOT / "data/moex_social_worker_exam_dates.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_oldver_stage4.v1.json"

UA = "swsi-historical-law-oldver-stage4/2.0 (+private educational question bank)"
MOJ_HISTORY = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode={pcode}"
MOJ_OLD = "https://law.moj.gov.tw/LawClass/LawOldVer.aspx"
LIVE_ATTEMPTS = 3
LIVE_TIMEOUT = 30

ROC_NUMBER = hp.CN_NUMBER


def _canonical_oldver_url(pcode: str, lnndate: str, lser: str = "001") -> str:
    """Build the official MOJ historical-full-text URL.

    Live probing on MOJ confirmed that a promulgation date listed on LawHistory
    is accepted by LawOldVer with lser=001 and returns the historical full text.
    """
    return MOJ_OLD + "?" + urlencode({
        "pcode": pcode.upper(),
        "lnndate": lnndate,
        "lser": lser,
    })


def _iso_from_roc_parts(roc_raw: str, month_raw: str, day_raw: str) -> str | None:
    roc = hp.chinese_integer(roc_raw)
    month = hp.chinese_integer(month_raw)
    day = hp.chinese_integer(day_raw)
    if None in (roc, month, day):
        return None
    try:
        return date(int(roc) + 1911, int(month), int(day)).isoformat()
    except ValueError:
        return None


def _explicit_effective_dates(summary: str) -> list[str]:
    """Extract dates explicitly stated as the date the law/amendment takes effect."""
    text = hp.clean_text(summary)
    pattern = re.compile(
        rf"(?:發布定)?自(?:中華民國\s*)?({ROC_NUMBER})\s*年\s*"
        rf"({ROC_NUMBER})\s*月\s*({ROC_NUMBER})\s*日(?:起)?施行"
    )
    out: list[str] = []
    for match in pattern.finditer(text):
        value = _iso_from_roc_parts(*match.groups())
        if value and value not in out:
            out.append(value)
    return out


def effective_date_from_entry(entry: dict) -> str | None:
    """Resolve a deterministic effective date from one MOJ history entry.

    Unknown or mixed special rules intentionally return None.
    """
    promulgated = str(entry.get("date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", promulgated):
        return None
    summary = hp.clean_text(entry.get("summary") or "")

    explicit = _explicit_effective_dates(summary)
    if len(explicit) == 1:
        return explicit[0]
    if len(explicit) > 1:
        return None

    if re.search(r"自公布後次年(?:之)?一月一日施行", summary):
        year = int(promulgated[:4]) + 1
        return f"{year:04d}-01-01"

    # A simple promulgation-day rule is safe only when the same history row does
    # not also contain another delayed/special clause.
    if "自公布日施行" in summary and not hp.has_special_effective_date(summary):
        return promulgated

    if not entry.get("special_effective_date"):
        return promulgated

    return None


def _announcement_effective_date(entry: dict) -> str | None:
    """Return an effective date from a later MOJ '發布定自…施行' announcement."""
    summary = hp.clean_text(entry.get("summary") or "")
    if "發布定自" not in summary:
        return None
    explicit = _explicit_effective_dates(summary)
    return explicit[0] if len(explicit) == 1 else None


def resolve_effective_dates(entries: list[dict]) -> list[dict]:
    """Attach deterministic effective dates without manufacturing certainty.

    Some amendments say their effective date will be separately prescribed and
    a later MOJ history row records that Executive Yuan announcement.  Pair the
    unresolved promulgation row with the nearest later announcement when the
    announcement occurs within one year.  Otherwise keep it unresolved.
    """
    ordered = sorted(
        (dict(row) for row in entries if row.get("date")),
        key=lambda row: str(row.get("date")),
    )
    announcements: list[tuple[str, str]] = []
    for row in ordered:
        effective = _announcement_effective_date(row)
        if effective:
            announcements.append((str(row["date"]), effective))

    for row in ordered:
        resolved = effective_date_from_entry(row)
        source = "entry_rule" if resolved else None
        if resolved is None and row.get("special_effective_date"):
            promulgated = date.fromisoformat(str(row["date"]))
            candidates: list[tuple[str, str]] = []
            for announced_at, effective in announcements:
                announce_day = date.fromisoformat(announced_at)
                if announce_day < promulgated:
                    continue
                if (announce_day - promulgated).days > 366:
                    continue
                candidates.append((announced_at, effective))
            if candidates:
                nearest = min(candidates, key=lambda item: item[0])
                resolved = nearest[1]
                source = "later_moj_effective_announcement"
        row["effective_date"] = resolved
        row["effective_date_source"] = source or "unresolved"
    return ordered


def versions_from_history_entries(
    entries: list[dict],
    pcode: str,
    official_url: str,
    official_modified_date: str | None,
) -> list[dict]:
    """Build candidate full-law versions from official MOJ history rows."""
    modified = str(official_modified_date or "").strip()
    resolved_entries = resolve_effective_dates(entries)
    versions: list[dict] = []
    seen: set[str] = set()

    for entry in resolved_entries:
        promulgated = str(entry.get("date") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", promulgated):
            continue
        if promulgated in seen:
            continue
        seen.add(promulgated)
        lnndate = promulgated.replace("-", "")
        is_current = bool(modified and promulgated == modified)
        versions.append({
            "kind": "current" if is_current else "oldver",
            "version_date": promulgated,
            "effective_date": entry.get("effective_date"),
            "effective_date_source": entry.get("effective_date_source"),
            "lnndate": lnndate,
            "lser": None if is_current else "001",
            "url": official_url if is_current else _canonical_oldver_url(pcode, lnndate),
            "articles_changed": entry.get("articles") or [],
            "all_articles": bool(entry.get("all_articles")),
            "special_effective_date": bool(entry.get("special_effective_date")),
            "history_summary": entry.get("summary"),
        })

    return sorted(versions, key=lambda row: row["version_date"])


def select_version(versions: list[dict], on_date: str) -> dict | None:
    eligible = [
        row for row in versions
        if row.get("effective_date") and str(row["effective_date"]) <= on_date
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda row: (str(row["effective_date"]), str(row["version_date"])),
    )


def unresolved_effective_date_risk(
    versions: list[dict], article: str, exam_end: str
) -> list[dict]:
    """Return unresolved promulgated versions that could affect this article."""
    risky = []
    for row in versions:
        if row.get("effective_date"):
            continue
        if str(row.get("version_date") or "") > exam_end:
            continue
        if row.get("all_articles") or article in set(row.get("articles_changed") or []):
            risky.append(row)
    return risky


def select_exam_window_version(
    versions: list[dict], start_date: str, end_date: str, article: str | None = None
) -> tuple[str, dict | None, dict | None]:
    if article and unresolved_effective_date_risk(versions, article, end_date):
        return "effective_date_review", None, None
    start = select_version(versions, start_date)
    end = select_version(versions, end_date)
    if not start or not end:
        return "history_version_unavailable", start, end
    if (start["url"], start["effective_date"]) != (end["url"], end["effective_date"]):
        return "exam_window_version_conflict", start, end
    return "ok", start, end


def article_fingerprint(text: str) -> str:
    normalized = stage3.normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def exam_date_map(payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
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


def _history_bundle(session: Any, pcode: str) -> tuple[str, list[dict]]:
    url = MOJ_HISTORY.format(pcode=pcode)
    raw = _get(session, url)
    history_text = hp.html_to_text(raw)
    if "沿革" not in history_text:
        raise RuntimeError(f"MOJ history page not recognized: {url}")
    entries = hp.parse_history_entries(history_text)
    if not entries:
        raise RuntimeError(f"MOJ history parsed zero entries: {url}")
    return url, entries


def _article_from_page(page_html: str, article_no: str) -> dict | None:
    articles = stage3.parse_law_articles(page_html)
    return next((row for row in articles if row.get("article_no") == article_no), None)


def _page_matches_law(page_html: str, law_name: str) -> bool:
    text = hp.clean_text(hp.html_to_text(page_html)).replace("臺", "台")
    needle = hp.clean_text(law_name).replace("臺", "台")
    return bool(needle and needle in text)


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

        history_url, history_entries = history_bundle
        versions = versions_from_history_entries(
            history_entries,
            pcode,
            official_url,
            watch_row.get("official_modified_date"),
        )
        version_status, start_version, end_version = select_exam_window_version(
            versions, start_date, end_date, article=article
        )
        if version_status != "ok":
            payload = {
                **base,
                "status": version_status,
                "exam_start_date": start_date,
                "exam_end_date": end_date,
                "official_history_url": history_url,
                "start_version": start_version,
                "end_version": end_version,
            }
            if version_status == "effective_date_review":
                payload["unresolved_effective_versions"] = unresolved_effective_date_risk(
                    versions, article, end_date
                )
            records.append(payload)
            continue

        assert start_version is not None
        version_url = str(start_version["url"])
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

        if not _page_matches_law(page, law_name):
            records.append({
                **base,
                "status": "source_identity_mismatch",
                "official_history_url": history_url,
                "selected_version": start_version,
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
        "schema_version": 2,
        "method": (
            "Stage3 machine candidate -> official pinned exam window -> MOJ LawHistory "
            "promulgation/effective-date resolution -> derived official LawOldVer/current "
            "full text -> exact suggested-article fingerprint; read-only evidence only"
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
