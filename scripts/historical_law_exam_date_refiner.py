#!/usr/bin/env python3
"""Stage-2 exact-date refinement for SWSI historical-law provenance.

Read-only evidence worker: it fetches official MOEX exam dates and official MOJ
law histories, refines year-level triage, and emits an exception queue. It never
marks historical_version_checked=true and never changes official question data.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests

import historical_law_provenance_core as hp

ROOT = Path(__file__).resolve().parents[1]
MOEX_DETAIL = "https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c={exam_code}"
UA = "swsi-historical-law-exam-date/1.0 (+private educational question bank)"

# Confirmed by scripts/historical_answer_audit.py + v3 correction for 106-2.
EXAM_CODES = {
    "104-1": "104030", "104-2": "104100", "105-1": "105030", "105-2": "105090",
    "106-1": "106030", "106-2": "106110", "107-1": "107030", "107-2": "107110",
    "108-1": "108020", "108-2": "108110", "109-1": "109030", "109-2": "109110",
    "110-1": "110030", "110-2": "110111", "111-1": "111030", "111-2": "111110",
    "112-1": "112030", "112-2": "112110", "113-1": "113030", "113-2": "113100",
    "114-1": "114030", "114-2": "114100", "115-1": "115030", "115-2": "115100",
}
MOEX_DATE_RE = re.compile(
    r"考試日期\s*[:：]\s*(\d{3})/(\d{1,2})/(\d{1,2})\s*"
    r"(?:[~～至\-]\s*(?:(\d{3})/)?(\d{1,2})/(\d{1,2}))?"
)


def parse_moex_exam_dates(page_text: str) -> tuple[str, str] | None:
    text = hp.clean_text(html_lib.unescape(re.sub(r"<[^>]+>", " ", str(page_text or ""))))
    match = MOEX_DATE_RE.search(text)
    if not match:
        return None
    y1, m1, d1, y2, m2, d2 = match.groups()
    start = date(int(y1) + 1911, int(m1), int(d1))
    end = date(int(y2 or y1) + 1911, int(m2), int(d2)) if m2 and d2 else start
    return start.isoformat(), end.isoformat()


def official_exam_code(question: dict) -> str | None:
    source = str(question.get("source_exam_code") or "").strip()
    if re.fullmatch(r"\d{6}", source):
        return source
    human = str(question.get("exam_code") or "").strip()
    if re.fullmatch(r"\d{6}", human):
        return human
    return EXAM_CODES.get(human)


def fetch_exam_dates(session: requests.Session, codes: set[str]) -> dict:
    out = {}
    for code in sorted(codes):
        url = MOEX_DETAIL.format(exam_code=code)
        try:
            response = session.get(url, timeout=30, headers={"User-Agent": UA})
            response.raise_for_status()
            parsed = parse_moex_exam_dates(response.text)
            if not parsed:
                out[code] = {"status": "unresolved", "source_url": url, "error": "date_not_parsed"}
                continue
            start, end = parsed
            out[code] = {
                "status": "official_moex",
                "start_date": start,
                "end_date": end,
                "source_url": url,
            }
        except Exception as exc:
            out[code] = {"status": "unresolved", "source_url": url, "error": str(exc)}
    return out


def refine_question(question: dict, entries: list[dict], exam_record: dict | None) -> dict:
    stage1 = hp.triage_question(question, entries)
    stage1["source_exam_code"] = official_exam_code(question)
    stage1["historical_version_checked"] = False
    if not exam_record or exam_record.get("status") != "official_moex":
        return {**stage1, "stage2_status": "exam_date_unresolved"}

    start, end = exam_record["start_date"], exam_record["end_date"]
    base = {
        **stage1,
        "exam_start_date": start,
        "exam_end_date": end,
        "exam_date_source_url": exam_record.get("source_url"),
    }
    if stage1["status"] == "current_text_equals_exam_year_candidate":
        return {
            **base,
            "stage2_status": "current_text_equals_exam_date_candidate",
            "eligible_for_historical_version_checked": True,
        }
    if stage1["status"] != "exam_date_required":
        return {**base, "stage2_status": stage1["status"]}

    articles = stage1["explicit_articles"]
    same_year = [
        entry
        for entry in entries
        if entry.get("year") == stage1["exam_year"]
        and any(hp.entry_affects_article(entry, article) for article in articles)
    ]
    if any(entry.get("special_effective_date") for entry in same_year):
        return {
            **base,
            "stage2_status": "effective_date_review",
            "eligible_for_historical_version_checked": False,
        }

    dates = [entry.get("date") for entry in same_year]
    if not dates or any(not value for value in dates):
        return {
            **base,
            "stage2_status": "history_date_unresolved",
            "eligible_for_historical_version_checked": False,
        }
    if any(start <= value <= end for value in dates):
        return {
            **base,
            "stage2_status": "exam_day_resolution_required",
            "same_year_change_dates": sorted(dates),
            "eligible_for_historical_version_checked": False,
        }
    after = sorted(value for value in dates if value > end)
    if after:
        return {
            **base,
            "stage2_status": "historical_text_required",
            "post_exam_change_dates": after,
            "eligible_for_historical_version_checked": False,
        }
    return {
        **base,
        "stage2_status": "current_text_equals_exam_date_candidate",
        "latest_pre_exam_change_date": max(dates),
        "eligible_for_historical_version_checked": True,
    }


def queue_bucket(status: str) -> str | None:
    if status in {"article_resolution_required", "article_origin_review"}:
        return "article_resolution"
    if status == "historical_text_required":
        return "historical_text"
    if status in {"effective_date_review", "exam_day_resolution_required"}:
        return "effective_date"
    if status in {"exam_date_unresolved", "history_date_unresolved", "official_history_unavailable"}:
        return "source_failure"
    return None


def build_live_report(links: dict, watch: dict, session: requests.Session) -> dict:
    watch_map = hp.watch_record_map(watch)
    mappings = [
        (card["law_name"], question)
        for card in links.get("cards") or []
        for question in card.get("questions") or []
    ]
    questions = [question for _law, question in mappings]
    codes = {code for question in questions if (code := official_exam_code(question))}
    exam_dates = fetch_exam_dates(session, codes)

    histories = {}
    history_urls = {}
    rows = []
    for card in links.get("cards") or []:
        law = card["law_name"]
        watch_row = watch_map.get(law) or {}
        pcode = hp.pcode_from_url(watch_row.get("official_url"))
        history_urls[law] = hp.MOJ_HISTORY.format(pcode=pcode) if pcode else None
        if pcode:
            try:
                histories[law] = hp.parse_history_entries(hp.fetch_history_text(pcode, session))
            except Exception:
                histories[law] = []
        else:
            histories[law] = []

        for question in card.get("questions") or []:
            code = official_exam_code(question)
            row = refine_question(question, histories[law], exam_dates.get(code) if code else None)
            row.update({"law_name": law, "official_history_url": history_urls[law]})
            rows.append(row)

    status_counts = Counter(row["stage2_status"] for row in rows)
    queues = defaultdict(list)
    for row in rows:
        bucket = queue_bucket(row["stage2_status"])
        if bucket:
            queues[bucket].append(
                {
                    "law_name": row["law_name"],
                    "question_id": row["question_id"],
                    "stage2_status": row["stage2_status"],
                }
            )

    unique_question_count = len({str(row.get("question_id") or "") for row in rows})
    return {
        "schema_version": 2,
        "question_count": len(rows),
        "mapping_count": len(rows),
        "unique_question_count": unique_question_count,
        "cross_law_overlap_count": len(rows) - unique_question_count,
        "historical_version_checked_count": 0,
        "candidate_count": sum(
            row["stage2_status"] == "current_text_equals_exam_date_candidate" for row in rows
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "exception_queue": {key: value for key, value in sorted(queues.items())},
        "exam_dates": exam_dates,
        "questions": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--links", default=str(hp.DEFAULT_LINKS))
    parser.add_argument("--legal-watch-report", default=str(hp.DEFAULT_WATCH))
    parser.add_argument("--output", default=str(ROOT / "auto/qa/historical_law_exam_date_stage2.v1.json"))
    args = parser.parse_args()

    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    report = build_live_report(links, watch, session)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "mapping_count",
                    "unique_question_count",
                    "cross_law_overlap_count",
                    "candidate_count",
                    "historical_version_checked_count",
                    "status_counts",
                    "exception_queue",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
