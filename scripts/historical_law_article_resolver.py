#!/usr/bin/env python3
"""Stage-3 article candidate resolver for historical-law provenance.

Purpose
-------
Most priority-law questions name the law but do not print an article number in the
stem. Stage 2 correctly refuses to guess. This worker narrows those cases by
comparing the question stem with *official current MOJ article text*.

Safety boundary
---------------
- This is candidate generation only, not historical verification.
- It never mutates stem/options/official_answer/accepted_answers/grading_mode.
- It never sets historical_version_checked=true.
- Current law text is allowed to suggest an article number, but the suggested
  article must still pass historical-text/effective-date checks for the exam date.
- Ambiguous cases route to AI review rather than being silently accepted.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import historical_law_provenance_core as hp

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_article_stage3.v1.json"
UA = "swsi-historical-law-article-resolver/1.0 (+private educational question bank)"
MOJ_ALL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}"
LIVE_ATTEMPTS = 3
LIVE_TIMEOUT = 30
LIVE_WORKERS = 6

ARTICLE_NO = r"[0-9一二三四五六七八九十百千零〇○Ｏ]+"
ARTICLE_HEADING_RE = re.compile(
    rf"(?m)^\s*第\s*({ARTICLE_NO})(?:(?:\s*之\s*|\s*-\s*)({ARTICLE_NO}))?\s*條\s*$"
)
EXPLICIT_ARTICLE_REF_RE = re.compile(
    rf"第\s*{ARTICLE_NO}(?:(?:\s*之\s*|\s*-\s*){ARTICLE_NO})?\s*條(?:\s*之\s*{ARTICLE_NO})?"
)

# Only boilerplate is removed. Domain words remain evidence.
BOILERPLATE = (
    "依據", "依照", "根據", "依", "我國", "規定", "所定", "有關", "關於",
    "下列何者", "下列敘述", "何者正確", "何者錯誤", "何者不正確", "何者不適用",
    "何者符合", "請問", "的敘述", "之敘述", "下列", "敘述", "正確", "錯誤",
)


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = html_lib.unescape(text).replace("臺", "台")
    return re.sub(r"\s+", " ", text).strip()


def semantic_text(value: object, law_name: str = "") -> str:
    text = normalize_text(value)
    if law_name:
        text = text.replace(normalize_text(law_name), "")
    text = EXPLICIT_ARTICLE_REF_RE.sub("", text)
    for phrase in BOILERPLATE:
        text = text.replace(phrase, "")
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text)


def ngrams(text: str, sizes: tuple[int, ...] = (2, 3, 4)) -> set[str]:
    out: set[str] = set()
    for n in sizes:
        if len(text) < n:
            continue
        out.update(text[i:i+n] for i in range(len(text)-n+1))
    return out


def parse_law_articles(page_html: str) -> list[dict]:
    """Extract top-level MOJ LawAll article blocks without splitting cross-references."""
    text = hp.html_to_text(str(page_html or ""))
    text = unicodedata.normalize("NFKC", text).replace("\r", "")
    matches = list(ARTICLE_HEADING_RE.finditer(text))
    rows: list[dict] = []
    for index, match in enumerate(matches):
        raw = match.group(1) + (f"-{match.group(2)}" if match.group(2) else "")
        article_no = hp.normalize_article_no(raw)
        if not article_no:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = normalize_text(text[start:end])
        # Navigation/footer text can trail the last article. The scorer only uses
        # local n-gram overlap, but cap pathological pages defensively.
        if len(body) > 12000:
            body = body[:12000]
        rows.append({"article_no": article_no, "text": body})
    # MOJ pages should not repeat top-level article headings. Fail closed if they do.
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        if row["article_no"] in seen:
            continue
        seen.add(row["article_no"])
        unique.append(row)
    return unique


def _idf_weights(article_grams: list[set[str]]) -> dict[str, float]:
    total = max(1, len(article_grams))
    df: Counter[str] = Counter()
    for grams in article_grams:
        df.update(grams)
    return {gram: math.log((total + 1) / (count + 1)) + 1.0 for gram, count in df.items()}


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?%?", unicodedata.normalize("NFKC", text)))


def rank_articles(stem: str, law_name: str, articles: list[dict], limit: int = 5) -> list[dict]:
    query = semantic_text(stem, law_name)
    query_grams = ngrams(query)
    if len(query) < 4 or len(query_grams) < 3 or not articles:
        return []

    prepared = []
    article_grams = []
    for row in articles:
        text = semantic_text(row.get("text") or "", law_name)
        grams = ngrams(text)
        prepared.append((row, text, grams))
        article_grams.append(grams)
    weights = _idf_weights(article_grams)
    query_weight = sum(weights.get(g, math.log(len(articles) + 1) + 1.0) for g in query_grams)
    query_nums = _numbers(query)
    scored = []

    for row, text, grams in prepared:
        shared = query_grams & grams
        if not shared:
            continue
        shared_weight = sum(weights.get(g, 1.0) for g in shared)
        coverage = shared_weight / max(query_weight, 1e-9)
        union = query_grams | grams
        jaccard = len(shared) / max(1, len(union))
        article_nums = _numbers(text)
        num_bonus = 0.0
        if query_nums:
            overlap = len(query_nums & article_nums) / len(query_nums)
            num_bonus = min(0.08, 0.08 * overlap)
        # Coverage matters more than article length. Jaccard is a light tie-breaker.
        score = min(1.0, 0.88 * coverage + 0.12 * jaccard + num_bonus)
        evidence = sorted(shared, key=lambda g: (-len(g), -weights.get(g, 1.0), g))[:8]
        scored.append({
            "article_no": row["article_no"],
            "score": round(score, 6),
            "shared_ngram_count": len(shared),
            "evidence": evidence,
        })
    scored.sort(key=lambda row: (-row["score"], -row["shared_ngram_count"], hp.article_key(row["article_no"])))
    return scored[:limit]


def classify_candidates(candidates: list[dict]) -> tuple[str, str]:
    """Return (route, confidence). High confidence is still only a candidate."""
    if not candidates:
        return "ai_review", "insufficient"
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    margin = top["score"] - (second["score"] if second else 0.0)
    shared = int(top.get("shared_ngram_count") or 0)
    if top["score"] >= 0.28 and margin >= 0.075 and shared >= 8:
        return "machine_candidate", "high"
    if top["score"] >= 0.16 and margin >= 0.035 and shared >= 5:
        return "ai_review", "medium"
    return "ai_review", "low"


def resolve_question(question: dict, law_name: str, articles: list[dict], source_url: str) -> dict:
    stem = str(question.get("stem") or question.get("question") or "")
    explicit = hp.extract_explicit_articles(stem)
    base = {
        "law_name": law_name,
        "question_id": question.get("question_id") or question.get("id"),
        "exam_code": question.get("exam_code"),
        "historical_version_checked": False,
        "article_source_url": source_url,
    }
    if explicit:
        return {
            **base,
            "route": "already_explicit",
            "confidence": "explicit",
            "explicit_articles": explicit,
            "candidates": [],
        }
    candidates = rank_articles(stem, law_name, articles)
    route, confidence = classify_candidates(candidates)
    return {
        **base,
        "route": route,
        "confidence": confidence,
        "suggested_article": candidates[0]["article_no"] if candidates else None,
        "candidates": candidates,
    }


def _fetch_one_law(law_name: str, pcode: str) -> tuple[str, list[dict], str, str | None]:
    import requests

    url = MOJ_ALL.format(pcode=pcode)
    last_error = None
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    try:
        for attempt in range(LIVE_ATTEMPTS):
            try:
                response = session.get(url, timeout=LIVE_TIMEOUT)
                response.raise_for_status()
                articles = parse_law_articles(response.text)
                if not articles:
                    raise RuntimeError("MOJ LawAll parsed zero articles")
                return law_name, articles, url, None
            except Exception as exc:
                last_error = exc
                if attempt + 1 < LIVE_ATTEMPTS:
                    time.sleep(0.5 * (attempt + 1))
        return law_name, [], url, f"{type(last_error).__name__}: {last_error}"
    finally:
        session.close()


def fetch_law_articles(watch: dict, cards: list[dict]) -> tuple[dict, dict, dict]:
    watch_map = hp.watch_record_map(watch)
    articles_by_law: dict[str, list[dict]] = {}
    urls: dict[str, str] = {}
    errors: dict[str, str | None] = {}
    jobs = []
    for card in cards:
        law = card["law_name"]
        source = watch_map.get(hp.clean_text(law)) or {}
        pcode = hp.pcode_from_url(source.get("official_url"))
        if not pcode:
            articles_by_law[law] = []
            urls[law] = ""
            errors[law] = "missing pcode in legal watch official_url"
            continue
        jobs.append((law, pcode))
    if jobs:
        with ThreadPoolExecutor(max_workers=min(LIVE_WORKERS, len(jobs))) as pool:
            futures = [pool.submit(_fetch_one_law, law, pcode) for law, pcode in jobs]
            for future in as_completed(futures):
                law, articles, url, error = future.result()
                articles_by_law[law] = articles
                urls[law] = url
                errors[law] = error
    return articles_by_law, urls, errors


def strip_explicit_article_refs(stem: str) -> str:
    return EXPLICIT_ARTICLE_REF_RE.sub("", str(stem or ""))


def build_report(links: dict, watch: dict) -> dict:
    cards = links.get("cards") or []
    articles_by_law, urls, errors = fetch_law_articles(watch, cards)
    records = []
    controls = []
    for card in cards:
        law = card["law_name"]
        articles = articles_by_law.get(law, [])
        url = urls.get(law, "")
        source_error = errors.get(law)
        for question in card.get("questions") or []:
            stem = str(question.get("stem") or question.get("question") or "")
            explicit = hp.extract_explicit_articles(stem)
            if explicit:
                # Positive control only: hide the printed article number and see
                # whether semantic ranking would recover it. This never changes data.
                ranked = rank_articles(strip_explicit_article_refs(stem), law, articles)
                controls.append({
                    "law_name": law,
                    "question_id": question.get("question_id") or question.get("id"),
                    "expected_articles": explicit,
                    "top_candidate": ranked[0]["article_no"] if ranked else None,
                    "top1_match": bool(ranked and ranked[0]["article_no"] in explicit),
                })
                continue
            if source_error:
                records.append({
                    "law_name": law,
                    "question_id": question.get("question_id") or question.get("id"),
                    "exam_code": question.get("exam_code"),
                    "route": "source_failure",
                    "confidence": "none",
                    "historical_version_checked": False,
                    "article_source_url": url,
                    "source_error": source_error,
                    "candidates": [],
                })
            else:
                records.append(resolve_question(question, law, articles, url))

    route_counts = Counter(row["route"] for row in records)
    confidence_counts = Counter(row["confidence"] for row in records)
    control_matches = sum(bool(row["top1_match"]) for row in controls)
    source_errors = [
        {"law_name": law, "source_url": urls.get(law), "error": error}
        for law, error in sorted(errors.items()) if error
    ]
    return {
        "schema_version": 1,
        "method": "official current MOJ article text -> IDF-weighted character n-gram candidate ranking; candidate only, never historical verification",
        "mapping_count": sum(len(card.get("questions") or []) for card in cards),
        "target_count": len(records),
        "explicit_control_count": len(controls),
        "explicit_control_top1_match_count": control_matches,
        "route_counts": dict(sorted(route_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "law_source_error_count": len(source_errors),
        "law_source_errors": source_errors,
        "historical_version_checked_count": 0,
        "controls": controls,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--links", default=str(hp.DEFAULT_LINKS))
    parser.add_argument("--legal-watch-report", default=str(hp.DEFAULT_WATCH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    watch = json.loads(Path(args.legal_watch_report).read_text(encoding="utf-8"))
    report = build_report(links, watch)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mapping_count": report["mapping_count"],
        "target_count": report["target_count"],
        "explicit_control_count": report["explicit_control_count"],
        "explicit_control_top1_match_count": report["explicit_control_top1_match_count"],
        "route_counts": report["route_counts"],
        "confidence_counts": report["confidence_counts"],
        "law_source_error_count": report["law_source_error_count"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
