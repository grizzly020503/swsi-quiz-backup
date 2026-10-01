#!/usr/bin/env python3
"""Shared fail-closed historical-law provenance core for SWSI.

This module never mutates official question/answer/grading fields. It only
classifies whether a law-linked question can move toward historical verification
or must remain in an evidence/review queue.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINKS = ROOT / "data/law_question_links_priority10.v1.json"
DEFAULT_WATCH = ROOT / "data/legal_watch_report.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_provenance_priority10.v1.json"
UA = "swsi-historical-law-provenance/2.0 (+private educational question bank)"
MOJ_HISTORY = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode={pcode}"

CN_DIGITS = {
    "零": 0, "〇": 0, "○": 0, "Ｏ": 0,
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
CN_NUMBER = r"[0-9一二三四五六七八九十百千零〇○Ｏ]+"


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def chinese_integer(value: str) -> int | None:
    s = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if any(ch not in CN_DIGITS and ch not in CN_UNITS for ch in s):
        return None
    total = 0
    current = 0
    for ch in s:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        else:
            total += (current or 1) * CN_UNITS[ch]
            current = 0
    return total + current


def normalize_article_no(value: str) -> str | None:
    s = unicodedata.normalize("NFKC", str(value or "")).strip().replace("之", "-")
    s = re.sub(r"\s+", "", s)
    if not s:
        return None
    parts = s.split("-")
    out = []
    for part in parts:
        number = int(part) if part.isdigit() else chinese_integer(part)
        if number is None:
            return None
        out.append(str(number))
    return "-".join(out)


def article_key(value: str) -> tuple[int, ...]:
    return tuple(int(p) for p in value.split("-"))


def expand_article_token(token: str) -> list[str]:
    token = unicodedata.normalize("NFKC", token).strip().replace("之", "-")
    token = re.sub(r"\s+", "", token)
    if not token:
        return []
    range_match = re.fullmatch(rf"({CN_NUMBER})[～~至]({CN_NUMBER})", token)
    if range_match:
        a = chinese_integer(range_match.group(1))
        b = chinese_integer(range_match.group(2))
        if a is not None and b is not None and a <= b and b - a <= 300:
            return [str(i) for i in range(a, b + 1)]
        return []
    normalized = normalize_article_no(token)
    return [normalized] if normalized else []


def extract_explicit_articles(text: str) -> list[str]:
    """Extract only article numbers explicitly written in a question stem."""
    s = unicodedata.normalize("NFKC", str(text or ""))
    pattern = re.compile(
        rf"第\s*({CN_NUMBER})(?:(?:\s*-\s*|\s*之\s*)({CN_NUMBER}))?\s*條(?:\s*之\s*({CN_NUMBER}))?"
    )
    found: set[str] = set()
    for match in pattern.finditer(s):
        main = match.group(1)
        sub = match.group(2) or match.group(3)
        raw = main + (f"-{sub}" if sub else "")
        normalized = normalize_article_no(raw)
        if normalized:
            found.add(normalized)
    return sorted(found, key=article_key)


def _article_groups(text: str) -> set[str]:
    s = unicodedata.normalize("NFKC", str(text or "")).replace("之", "-")
    out: set[str] = set()
    # MOJ history normally uses Arabic article numbers here. Keep the grouped
    # parser narrow so unrelated quantities are never promoted to article IDs.
    for match in re.finditer(r"第\s*([0-9\-、,，～~至\s]+?)\s*條", s):
        for token in re.split(r"[、,，]", match.group(1)):
            out.update(expand_article_token(token))
    for match in re.finditer(r"第\s*(\d+(?:-\d+)*)\s*條", s):
        normalized = normalize_article_no(match.group(1))
        if normalized:
            out.add(normalized)
    return out


def parse_roc_date(text: str) -> str | None:
    m = re.search(
        rf"中華民國\s*({CN_NUMBER})\s*年\s*({CN_NUMBER})\s*月\s*({CN_NUMBER})\s*日",
        str(text or ""),
    )
    if not m:
        return None
    roc, month, day = (chinese_integer(x) for x in m.groups())
    if None in (roc, month, day):
        return None
    try:
        return date(int(roc) + 1911, int(month), int(day)).isoformat()
    except ValueError:
        return None


def history_entry_year(text: str) -> int | None:
    iso = parse_roc_date(text)
    if iso:
        return int(iso[:4])
    m = re.search(rf"中華民國\s*({CN_NUMBER})\s*年", str(text or ""))
    roc = chinese_integer(m.group(1)) if m else None
    return roc + 1911 if roc is not None else None


def has_special_effective_date(text: str) -> bool:
    s = clean_text(text)
    if "施行" not in s:
        return False
    # Mixed immediate + delayed clauses are still risky because this layer does
    # not assign each effective-date clause to a specific article.
    delayed = "公布後" in s or "另定" in s or bool(
        re.search(rf"自(?:中華民國)?\s*{CN_NUMBER}\s*年", s)
    )
    if delayed:
        return True
    reduced = s.replace("並自公布日施行", "").replace("其餘自公布日施行", "").replace("自公布日施行", "")
    return "施行" in reduced


def parse_history_entries(page_text: str) -> list[dict]:
    text = unicodedata.normalize("NFKC", str(page_text or ""))
    text = re.sub(r"\r\n?", "\n", text)
    chunks = re.split(r"(?m)(?=^\s*\d+\.\s*)", text)
    entries = []
    for chunk in chunks:
        chunk = clean_text(chunk)
        if not re.match(r"^\d+\.\s*", chunk):
            continue
        year = history_entry_year(chunk)
        if year is None:
            continue
        entries.append({
            "date": parse_roc_date(chunk),
            "year": year,
            "articles": sorted(_article_groups(chunk), key=article_key),
            "all_articles": bool(re.search(r"全文\s*\d+\s*條", chunk)),
            "special_effective_date": has_special_effective_date(chunk),
            "summary": chunk,
        })
    return entries


def entry_affects_article(entry: dict, article: str) -> bool:
    return bool(entry.get("all_articles")) or article in set(entry.get("articles") or [])


def triage_question(question: dict, history_entries: Iterable[dict]) -> dict:
    articles = extract_explicit_articles(question.get("stem") or question.get("question") or "")
    exam_roc = int(str(question.get("year")))
    exam_year = exam_roc + 1911
    base = {
        "question_id": question.get("question_id") or question.get("id"),
        "exam_code": question.get("exam_code"),
        "exam_year": exam_year,
        "explicit_articles": articles,
        "historical_version_checked": False,
        "eligible_for_historical_version_checked": False,
    }
    if not articles:
        return {**base, "status": "article_resolution_required", "reason": "題幹未明示條號，不以關鍵字猜測條文"}
    entries = list(history_entries)
    if not entries:
        return {**base, "status": "official_history_unavailable", "reason": "未取得可解析的 MOJ 沿革"}
    relevant = [e for e in entries if any(entry_affects_article(e, a) for a in articles)]
    if not relevant:
        return {**base, "status": "article_origin_review", "reason": "MOJ 沿革中找不到該條明確建立／異動紀錄"}
    if any(e.get("special_effective_date") for e in relevant):
        return {**base, "status": "effective_date_review", "reason": "相關沿革含延後／特殊施行條款", "relevant_change_years": sorted({e["year"] for e in relevant})}
    later = sorted({e["year"] for e in relevant if e["year"] > exam_year})
    same = sorted({e["year"] for e in relevant if e["year"] == exam_year})
    before = sorted({e["year"] for e in relevant if e["year"] < exam_year})
    if later:
        return {**base, "status": "historical_text_required", "reason": "考試年度後該條仍有官方修正", "post_exam_change_years": later}
    if same:
        return {**base, "status": "exam_date_required", "reason": "考試年度內該條有修正，需精確考試日期", "same_year_change_years": same}
    if not before:
        return {**base, "status": "article_origin_review", "reason": "考試年度前找不到該條存在的官方沿革證據"}
    return {
        **base,
        "status": "current_text_equals_exam_year_candidate",
        "reason": "考試年度後無該條修正；可進第二階段精確日期／文字核驗",
        "latest_pre_exam_change_year": max(before),
        "eligible_for_historical_version_checked": True,
    }


def pcode_from_url(url: str) -> str | None:
    if not url:
        return None
    value = (parse_qs(urlparse(url).query).get("pcode") or [None])[0]
    return value.upper() if value else None


def watch_record_map(watch: dict) -> dict[str, dict]:
    raw = watch.get("records") or []
    if isinstance(raw, dict):
        return {clean_text(name): row for name, row in raw.items() if clean_text(name) and isinstance(row, dict)}
    out: dict[str, dict] = {}
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = clean_text(row.get("canonical_name") or row.get("law_name") or row.get("name"))
            if name:
                out[name] = row
    return out


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    return html_lib.unescape(text)


def fetch_history_text(pcode: str, session: requests.Session | None = None) -> str:
    session = session or requests.Session()
    url = MOJ_HISTORY.format(pcode=pcode)
    r = session.get(url, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    text = html_to_text(r.text)
    if "沿革" not in text:
        raise RuntimeError(f"MOJ history page not recognized: {url}")
    return text


def build_report(links: dict, watch: dict, live: bool, session: requests.Session | None = None) -> dict:
    watch_records = watch_record_map(watch)
    rows = []
    histories: dict[str, list[dict]] = {}
    for card in links.get("cards") or []:
        law = card["law_name"]
        watch_row = watch_records.get(law) or {}
        pcode = pcode_from_url(watch_row.get("official_url"))
        history_url = MOJ_HISTORY.format(pcode=pcode) if pcode else None
        histories[law] = parse_history_entries(fetch_history_text(pcode, session)) if live and pcode else []
        for q in card.get("questions") or []:
            result = triage_question(q, histories[law])
            result.update({"law_name": law, "official_history_url": history_url})
            rows.append(result)
    return {
        "schema_version": 2,
        "method": "explicit article + official MOJ history; no answer mutation; no keyword-only article inference",
        "live_history_fetch": live,
        "question_count": len(rows),
        "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
        "questions": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", default=str(DEFAULT_LINKS))
    ap.add_argument("--legal-watch-report", default=str(DEFAULT_WATCH))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    report = build_report(links, watch, args.live)
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"historical law provenance triage: {report['question_count']} questions -> {report['status_counts']}")
    return 0
