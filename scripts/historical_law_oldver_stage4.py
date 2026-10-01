#!/usr/bin/env python3
"""Stage 4 read-only historical-law article evidence for SWSI.

Stage 3 resolves a high-confidence article candidate. Stage 4 then asks a much
narrower question: which official version of *that article* was legally in force
throughout the official exam window?  It derives MOJ LawOldVer URLs from
LawHistory promulgation dates, resolves deterministic article-scoped effective
dates, fetches official full text, and fingerprints the candidate article.

This is evidence only. It never reads official answers, never mutates protected
question fields, and never sets historical_version_checked=true.
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
UA = "swsi-historical-law-oldver-stage4/3.0 (+private educational question bank)"
MOJ_HISTORY = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode={pcode}"
MOJ_OLD = "https://law.moj.gov.tw/LawClass/LawOldVer.aspx"
LIVE_ATTEMPTS = 3
LIVE_TIMEOUT = 30
ROC_NUMBER = hp.CN_NUMBER


def _compact(value: object) -> str:
    return re.sub(r"\s+", "", hp.clean_text(value))


def _canonical_oldver_url(pcode: str, lnndate: str, lser: str = "001") -> str:
    return MOJ_OLD + "?" + urlencode({
        "pcode": pcode.upper(), "lnndate": lnndate, "lser": lser,
    })


def _iso_from_roc_parts(roc_raw: str, month_raw: str, day_raw: str) -> str | None:
    values = [hp.chinese_integer(v) for v in (roc_raw, month_raw, day_raw)]
    if any(v is None for v in values):
        return None
    try:
        return date(int(values[0]) + 1911, int(values[1]), int(values[2])).isoformat()
    except ValueError:
        return None


def _effective_clauses(summary: str) -> list[dict]:
    """Extract explicit ``自 ROC-date 施行`` clauses and their nearby article scope."""
    text = _compact(summary)
    pattern = re.compile(
        rf"自(?:中華民國)?({ROC_NUMBER})年({ROC_NUMBER})月({ROC_NUMBER})日(?:起)?施行"
    )
    matches = list(pattern.finditer(text))
    clauses: list[dict] = []
    previous_end = 0
    for match in matches:
        start = previous_end
        prefix = text[start:match.start()]
        cut = max(prefix.rfind(";"), prefix.rfind("；"), prefix.rfind("。"))
        if cut >= 0:
            prefix = prefix[cut + 1:]
        effective = _iso_from_roc_parts(*match.groups())
        scope = sorted(hp._article_groups(prefix), key=hp.article_key)
        clauses.append({
            "effective_date": effective,
            "scope_articles": scope,
            "prefix": prefix[-240:],
            "global_by_statute_clause": bool(re.search(r"依第[^條]+條規定[:：]?", prefix)),
        })
        previous_end = match.end()
    return [row for row in clauses if row.get("effective_date")]


def article_effective_date(entry: dict, article: str) -> str | None:
    """Resolve the effective date for one target article in one MOJ history row."""
    promulgated = str(entry.get("date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", promulgated):
        return None
    text = _compact(entry.get("summary") or "")
    clauses = _effective_clauses(text)

    for clause in clauses:
        if article in set(clause["scope_articles"]):
            return str(clause["effective_date"])

    for clause in clauses:
        if entry.get("all_articles") and clause.get("global_by_statute_clause"):
            return str(clause["effective_date"])

    unscoped = [c for c in clauses if not c["scope_articles"]]
    if len(clauses) == 1 and len(unscoped) == 1:
        return str(unscoped[0]["effective_date"])

    if entry.get("all_articles") and unscoped:
        return str(unscoped[-1]["effective_date"])

    if "自公布日起施行" in text or "自公布日施行" in text:
        return promulgated

    if re.search(r"自公布後次年(?:之)?一月一日施行", text):
        return f"{int(promulgated[:4]) + 1:04d}-01-01"

    if not entry.get("special_effective_date"):
        return promulgated
    return None


def versions_for_article(
    entries: list[dict], pcode: str, official_url: str,
    official_modified_date: str | None, article: str,
) -> list[dict]:
    """Return the version chain for one article.

    The last history row that affects the target article is represented by the
    current MOJ LawAll page. Earlier target-article rows use LawOldVer. This is
    article-scoped: later amendments to unrelated articles do not force the
    target article back onto an old-version URL.
    """
    del official_modified_date  # retained for API compatibility with Stage 4 callers
    relevant: list[dict] = []
    seen: set[str] = set()
    for entry in sorted(entries, key=lambda row: str(row.get("date") or "")):
        promulgated = str(entry.get("date") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", promulgated):
            continue
        if promulgated in seen or not hp.entry_affects_article(entry, article):
            continue
        seen.add(promulgated)
        relevant.append(entry)

    versions: list[dict] = []
    for index, entry in enumerate(relevant):
        promulgated = str(entry.get("date") or "")
        is_current_article_version = index == len(relevant) - 1
        lnndate = promulgated.replace("-", "")
        versions.append({
            "kind": "current" if is_current_article_version else "oldver",
            "version_date": promulgated,
            "effective_date": article_effective_date(entry, article),
            "effective_date_scope": "target_article",
            "lnndate": lnndate,
            "lser": None if is_current_article_version else "001",
            "url": official_url if is_current_article_version else _canonical_oldver_url(pcode, lnndate),
            "articles_changed": entry.get("articles") or [],
            "all_articles": bool(entry.get("all_articles")),
            "special_effective_date": bool(entry.get("special_effective_date")),
            "history_summary": entry.get("summary"),
        })
    return versions


def select_version(versions: list[dict], on_date: str) -> dict | None:
    eligible = [
        row for row in versions
        if row.get("effective_date")
        and str(row["effective_date"]) <= on_date
        and str(row["version_date"]) <= on_date
    ]
    return max(eligible, key=lambda row: str(row["version_date"])) if eligible else None


def unresolved_effective_date_risk(versions: list[dict], exam_end: str) -> list[dict]:
    return [
        row for row in versions
        if not row.get("effective_date") and str(row.get("version_date") or "") <= exam_end
    ]


def select_exam_window_version(
    versions: list[dict], start_date: str, end_date: str,
) -> tuple[str, dict | None, dict | None]:
    if unresolved_effective_date_risk(versions, end_date):
        return "effective_date_review", None, None
    start = select_version(versions, start_date)
    end = select_version(versions, end_date)
    if not start or not end:
        return "history_version_unavailable", start, end
    if (start["url"], start["version_date"]) != (end["url"], end["version_date"]):
        return "exam_window_version_conflict", start, end
    return "ok", start, end


def article_fingerprint(text: str) -> str:
    return hashlib.sha256(stage3.normalize_text(text).encode("utf-8")).hexdigest()


def exam_date_map(payload: dict) -> dict[str, dict]:
    return {
        str(row.get("exam_code")): row
        for row in (payload.get("records") or []) if row.get("exam_code")
    }


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
    text = hp.html_to_text(raw)
    if "沿革" not in text:
        raise RuntimeError(f"MOJ history page not recognized: {url}")
    entries = hp.parse_history_entries(text)
    if not entries:
        raise RuntimeError(f"MOJ history parsed zero entries: {url}")
    return url, entries


def _article_from_page(page_html: str, article_no: str) -> dict | None:
    return next(
        (row for row in stage3.parse_law_articles(page_html)
         if row.get("article_no") == article_no), None,
    )


def _page_identity_ok(page_html: str) -> bool:
    """Verify the fetched page is an official MOJ law document, independent of article parsing."""
    raw = str(page_html or "")
    title = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    title_text = hp.clean_text(title.group(1)) if title else ""
    return "全國法規資料庫" in title_text


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
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", end_date
        ):
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
        bundle = history_cache[pcode]
        if isinstance(bundle, Exception):
            records.append({
                **base, "status": "source_failure",
                "source_error": f"{type(bundle).__name__}: {bundle}",
            })
            continue

        history_url, entries = bundle
        versions = versions_for_article(
            entries, pcode, official_url, watch_row.get("official_modified_date"), article
        )
        status, start_version, end_version = select_exam_window_version(
            versions, start_date, end_date
        )
        if status != "ok":
            result = {
                **base, "status": status,
                "exam_start_date": start_date,
                "exam_end_date": end_date,
                "official_history_url": history_url,
                "start_version": start_version,
                "end_version": end_version,
            }
            if status == "effective_date_review":
                result["unresolved_effective_versions"] = unresolved_effective_date_risk(
                    versions, end_date
                )
            records.append(result)
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
                **base, "status": "source_failure",
                "official_history_url": history_url,
                "selected_version": start_version,
                "source_error": f"{type(page).__name__}: {page}",
            })
            continue
        if not _page_identity_ok(page):
            records.append({
                **base, "status": "source_identity_mismatch",
                "official_history_url": history_url,
                "selected_version": start_version,
            })
            continue

        article_row = _article_from_page(page, article)
        article_text = stage3.normalize_text((article_row or {}).get("text") or "")
        if not article_text:
            records.append({
                **base, "status": "article_missing_in_selected_version",
                "official_history_url": history_url,
                "selected_version": start_version,
            })
            continue

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
        "schema_version": 3,
        "method": (
            "Stage3 machine candidate -> target-article MOJ LawHistory changes -> "
            "article-scoped effective date -> official pinned exam window -> derived "
            "MOJ LawOldVer/current full text -> exact article fingerprint; evidence only"
        ),
        "stage3_machine_candidate_count": len(candidates),
        "record_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "historical_text_evidence_ready_count": counts.get(
            "historical_text_evidence_ready", 0
        ),
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