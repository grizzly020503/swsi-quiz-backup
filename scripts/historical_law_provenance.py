#!/usr/bin/env python3
"""Conservative historical-law provenance triage for SWSI.

This module never edits official questions/answers. It only classifies priority-law
question links into machine-safe buckets using:
- explicit article numbers stated in the question stem;
- official MOJ law-history entries;
- the exam ROC year already present in the question record.

Important safety boundary:
- a law-name match is NOT historical verification;
- same-year amendments require an exact exam-date follow-up;
- later-year amendments require historical text retrieval;
- delayed/special effective-date clauses fail closed;
- no explicit article number => article-resolution queue.

The live CLI may fetch MOJ LawHistory pages, but deterministic CI should use the
pure parsing/triage functions in historical_law_provenance_selftest.py.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINKS = ROOT / "data/law_question_links_priority10.v1.json"
DEFAULT_WATCH = ROOT / "data/legal_watch_report.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_provenance_priority10.v1.json"
UA = "swsi-historical-law-provenance/1.0 (+private educational question bank)"
MOJ_HISTORY = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode={pcode}"

CN_DIGITS = {"零": 0, "〇": 0, "○": 0, "Ｏ": 0, "一": 1, "二": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def chinese_integer(value: str) -> int | None:
    """Parse ROC years such as 九十九、一百零四、一百十五."""
    s = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if any(ch not in CN_DIGITS and ch not in {"十", "百"} for ch in s):
        return None
    total = 0
    current = 0
    for ch in s:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
    return total + current


def normalize_article_no(value: str) -> str | None:
    s = unicodedata.normalize("NFKC", str(value or "")).strip().replace("之", "-")
    s = re.sub(r"\s+", "", s)
    if not re.fullmatch(r"\d+(?:-\d+)*", s):
        return None
    return "-".join(str(int(part)) for part in s.split("-"))


def article_key(value: str) -> tuple[int, ...]:
    return tuple(int(p) for p in value.split("-"))


def expand_article_token(token: str) -> list[str]:
    token = unicodedata.normalize("NFKC", token).strip().replace("之", "-")
    token = re.sub(r"\s+", "", token)
    if not token:
        return []
    m = re.fullmatch(r"(\d+)\s*[～~至]\s*(\d+)", token)
    if m:
        a, b = map(int, m.groups())
        if a <= b and b - a <= 200:
            return [str(i) for i in range(a, b + 1)]
        return []
    n = normalize_article_no(token)
    return [n] if n else []


def extract_explicit_articles(text: str) -> list[str]:
    """Extract only article numbers explicitly written in a question stem."""
    s = unicodedata.normalize("NFKC", str(text or "")).replace("之", "-")
    found: set[str] = set()
    for m in re.finditer(r"第\s*(\d+(?:-\d+)*)\s*條", s):
        n = normalize_article_no(m.group(1))
        if n:
            found.add(n)
    return sorted(found, key=article_key)


def _article_groups(text: str) -> set[str]:
    """Extract changed article numbers from one MOJ history entry."""
    s = unicodedata.normalize("NFKC", str(text or "")).replace("之", "-")
    out: set[str] = set()
    # Handles: 第 10、13、41、...、62～64 條 / 第 26-1、26-2 條
    for m in re.finditer(r"第\s*([0-9\-、,，～~至\s]+?)\s*條", s):
        group = m.group(1)
        for token in re.split(r"[、,，]", group):
            out.update(expand_article_token(token))
    # Handles repeated constructs such as 第 7 條第 2 項 ... 第 44 條第 3 項.
    for m in re.finditer(r"第\s*(\d+(?:-\d+)*)\s*條", s):
        n = normalize_article_no(m.group(1))
        if n:
            out.add(n)
    return out


def history_entry_year(text: str) -> int | None:
    m = re.search(r"中華民國\s*([一二三四五六七八九十百零〇○Ｏ0-9]+)\s*年", str(text or ""))
    if not m:
        return None
    roc = chinese_integer(m.group(1))
    return roc + 1911 if roc is not None else None


def has_special_effective_date(text: str) -> bool:
    s = clean_text(text)
    if "施行" not in s:
        return False
    # Plain "自公布日施行" is immediate and does not need a special effective-date review.
    reduced = s.replace("並自公布日施行", "").replace("其餘自公布日施行", "").replace("自公布日施行", "")
    return "施行" in reduced or "公布後" in s or "另定" in s


def parse_history_entries(page_text: str) -> list[dict]:
    """Parse MOJ history plain text into conservative amendment events.

    Entries are split at numbered history rows (e.g. 15. ... 14. ...). When the
    source formatting is odd, rows without a resolvable ROC year are ignored.
    """
    text = unicodedata.normalize("NFKC", str(page_text or ""))
    # Normalize line breaks but keep numbered rows identifiable.
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
        all_articles = bool(re.search(r"全文\s*\d+\s*條", chunk))
        entries.append({
            "year": year,
            "articles": sorted(_article_groups(chunk), key=article_key),
            "all_articles": all_articles,
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

    special = [e for e in relevant if e.get("special_effective_date")]
    if special:
        return {
            **base,
            "status": "effective_date_review",
            "reason": "相關沿革含延後／特殊施行條款，不能只用公布年判定版本",
            "relevant_change_years": sorted({e["year"] for e in relevant}),
        }

    later = sorted({e["year"] for e in relevant if e["year"] > exam_year})
    same = sorted({e["year"] for e in relevant if e["year"] == exam_year})
    before = sorted({e["year"] for e in relevant if e["year"] < exam_year})

    if later:
        return {
            **base,
            "status": "historical_text_required",
            "reason": "考試年度後該條仍有官方修正，需取得考試當時條文",
            "post_exam_change_years": later,
        }
    if same:
        return {
            **base,
            "status": "exam_date_required",
            "reason": "考試年度內該條有修正，需精確考試日期與施行日判定",
            "same_year_change_years": same,
        }
    if not before:
        return {**base, "status": "article_origin_review", "reason": "考試年度前找不到該條存在的官方沿革證據"}

    return {
        **base,
        "status": "current_text_equals_exam_year_candidate",
        "reason": "相關條文於考試年度後無修正，且未見特殊施行條款；可進第二階段文字/來源核驗",
        "latest_pre_exam_change_year": max(before),
        "eligible_for_historical_version_checked": True,
    }


def pcode_from_url(url: str) -> str | None:
    if not url:
        return None
    value = (parse_qs(urlparse(url).query).get("pcode") or [None])[0]
    return value.upper() if value else None


def fetch_history_text(pcode: str) -> str:
    url = MOJ_HISTORY.format(pcode=pcode)
    r = requests.get(url, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    if "沿革" not in r.text:
        raise RuntimeError(f"MOJ history page not recognized: {url}")
    # Keep HTML; the regex parser only needs visible text-like content. Remove tags conservatively.
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", r.text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = text.replace("&nbsp;", " ").replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    return text


def build_report(links: dict, watch: dict, live: bool) -> dict:
    watch_records = watch.get("records") or {}
    rows = []
    histories: dict[str, list[dict]] = {}
    history_urls = {}
    for card in links.get("cards") or []:
        law = card["law_name"]
        watch_row = watch_records.get(law) or {}
        pcode = pcode_from_url(watch_row.get("official_url"))
        history_urls[law] = MOJ_HISTORY.format(pcode=pcode) if pcode else None
        if live and pcode:
            histories[law] = parse_history_entries(fetch_history_text(pcode))
        else:
            histories[law] = []
        for q in card.get("questions") or []:
            result = triage_question(q, histories[law])
            result.update({"law_name": law, "official_history_url": history_urls[law]})
            rows.append(result)
    return {
        "schema_version": 1,
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
    ap.add_argument("--live", action="store_true", help="Fetch official MOJ LawHistory pages")
    args = ap.parse_args()

    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    report = build_report(links, watch, args.live)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"historical law provenance triage: {report['question_count']} questions -> {report['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
