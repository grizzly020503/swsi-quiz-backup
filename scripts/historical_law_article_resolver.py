#!/usr/bin/env python3
"""Stage-3 article candidate resolver for historical-law provenance.

Most priority-law questions name the law but do not print an article number in the
stem. Stage 2 correctly refuses to guess. This worker narrows those cases with
three read-only evidence streams:

1. official current MOJ LawAll article text;
2. the official question stem + all four answer-option texts (never the answer);
3. existing law metadata, used only as a corroborating/conflict signal.

Safety boundary
---------------
- Candidate generation only; never historical verification.
- Never mutates stem/options/official_answer/accepted_answers/grading_mode.
- Never reads the official answer when resolving an article.
- Never sets historical_version_checked=true.
- A high-confidence current-law article candidate must still pass historical
  article-text/effective-date checks for the exact exam date.
- Metadata/semantic disagreement is forced to AI review.
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

import historical_law_provenance_core as hp

ROOT = Path(__file__).resolve().parents[1]
SHARD_DIR = ROOT / "cdn/question-shards"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_article_stage3.v1.json"
UA = "swsi-historical-law-article-resolver/1.1 (+private educational question bank)"
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

BOILERPLATE = (
    "依據", "依照", "根據", "依", "我國", "規定", "所定", "有關", "關於",
    "下列何者", "下列敘述", "何者正確", "何者錯誤", "何者不正確", "何者不適用",
    "何者符合", "請問", "的敘述", "之敘述", "下列", "敘述", "正確", "錯誤",
)
LEGAL_SUFFIXES = ("施行法", "特別條例", "條例", "自治條例", "法")


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = html_lib.unescape(text).replace("臺", "台")
    return re.sub(r"\s+", " ", text).strip()


def law_core(law_name: str) -> str:
    value = normalize_text(law_name)
    for suffix in LEGAL_SUFFIXES:
        if value.endswith(suffix) and len(value) - len(suffix) >= 4:
            return value[:-len(suffix)]
    return value


def semantic_text(value: object, law_name: str = "") -> str:
    text = normalize_text(value)
    if law_name:
        full = normalize_text(law_name)
        core = law_core(law_name)
        text = text.replace(full, "")
        if core != full and len(core) >= 4:
            text = text.replace(core, "")
    text = EXPLICIT_ARTICLE_REF_RE.sub("", text)
    for phrase in BOILERPLATE:
        text = text.replace(phrase, "")
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text)


def ngrams(text: str, sizes: tuple[int, ...] = (2, 3, 4)) -> set[str]:
    out: set[str] = set()
    for n in sizes:
        if len(text) >= n:
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
        if len(body) > 12000:
            body = body[:12000]
        rows.append({"article_no": article_no, "text": body})
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


def rank_articles(
    stem: str,
    law_name: str,
    articles: list[dict],
    option_texts: list[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    # Options carry much of the legal substance in MCQs. They are deliberately
    # included without consulting which option is correct.
    parts = [semantic_text(stem, law_name)]
    parts.extend(semantic_text(value, law_name) for value in (option_texts or []) if value)
    query = "".join(part for part in parts if part)
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
    default_weight = math.log(len(articles) + 1) + 1.0
    query_weight = sum(weights.get(g, default_weight) for g in query_grams)
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


def extract_metadata_articles(question: dict) -> list[str]:
    return hp.extract_explicit_articles(str(question.get("law_metadata") or ""))


def classify_candidates(candidates: list[dict], metadata_articles: list[str]) -> tuple[str, str, str]:
    """Return (route, confidence, reason). Machine route requires strong corroboration."""
    if not candidates:
        return "ai_review", "insufficient", "no_semantic_candidate"
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    margin = top["score"] - (second["score"] if second else 0.0)
    shared = int(top.get("shared_ngram_count") or 0)

    if metadata_articles:
        if top["article_no"] not in metadata_articles:
            return "ai_review", "conflict", "semantic_metadata_disagree"
        if len(metadata_articles) == 1 and top["score"] >= 0.15 and shared >= 5:
            return "machine_candidate", "high", "official_text_semantics_and_metadata_agree"
        return "ai_review", "medium", "metadata_multi_article_or_weak_semantics"

    # No metadata corroboration: require a much stronger semantic separation.
    if top["score"] >= 0.50 and margin >= 0.15 and shared >= 12:
        return "machine_candidate", "high", "very_strong_semantic_separation"
    if top["score"] >= 0.16 and margin >= 0.035 and shared >= 5:
        return "ai_review", "medium", "semantic_candidate_needs_second_signal"
    return "ai_review", "low", "weak_or_ambiguous_semantics"


def question_key(question: dict) -> tuple[str, str, int] | None:
    code = str(question.get("exam_code") or "").strip()
    subject = str(question.get("subject") or "").strip()
    raw = question.get("question_number") or question.get("qno")
    try:
        qno = int(str(raw))
    except (TypeError, ValueError):
        return None
    return (code, subject, qno)


def shard_options(row: dict) -> list[str]:
    if isinstance(row.get("options"), dict):
        values = [row["options"].get(key) for key in ("A", "B", "C", "D")]
    else:
        values = [row.get(f"opt_{key}") for key in ("a", "b", "c", "d")]
    return [str(value) for value in values if str(value or "").strip()]


def load_question_options(links: dict) -> tuple[dict[tuple[str, str, int], list[str]], list[dict]]:
    needed_codes = sorted({
        str(q.get("exam_code") or "").strip()
        for card in (links.get("cards") or [])
        for q in (card.get("questions") or [])
        if str(q.get("exam_code") or "").strip()
    })
    options: dict[tuple[str, str, int], list[str]] = {}
    errors: list[dict] = []
    for code in needed_codes:
        path = SHARD_DIR / f"{code}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append({"exam_code": code, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for row in payload.get("questions") or []:
            key = question_key({
                "exam_code": code,
                "subject": row.get("subject"),
                "question_number": row.get("qno") or row.get("question_number"),
            })
            if key:
                options[key] = shard_options(row)
    return options, errors


def resolve_question(
    question: dict,
    law_name: str,
    articles: list[dict],
    source_url: str,
    option_texts: list[str] | None = None,
) -> dict:
    stem = str(question.get("stem") or question.get("question") or "")
    explicit = hp.extract_explicit_articles(stem)
    base = {
        "law_name": law_name,
        "question_id": question.get("question_id") or question.get("id"),
        "exam_code": question.get("exam_code"),
        "historical_version_checked": False,
        "article_source_url": source_url,
        "context_fields": ["stem"] + (["options"] if option_texts else []),
    }
    if explicit:
        return {
            **base,
            "route": "already_explicit",
            "confidence": "explicit",
            "explicit_articles": explicit,
            "candidates": [],
        }
    metadata_articles = extract_metadata_articles(question)
    candidates = rank_articles(stem, law_name, articles, option_texts=option_texts)
    route, confidence, reason = classify_candidates(candidates, metadata_articles)
    return {
        **base,
        "route": route,
        "confidence": confidence,
        "decision_reason": reason,
        "metadata_articles": metadata_articles,
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
    option_map, shard_errors = load_question_options(links)
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
            key = question_key(question)
            option_texts = option_map.get(key, []) if key else []
            if explicit:
                ranked = rank_articles(
                    strip_explicit_article_refs(stem), law, articles, option_texts=option_texts
                )
                expected_rank = next(
                    (i + 1 for i, row in enumerate(ranked) if row["article_no"] in explicit), None
                )
                controls.append({
                    "law_name": law,
                    "question_id": question.get("question_id") or question.get("id"),
                    "expected_articles": explicit,
                    "top_candidate": ranked[0]["article_no"] if ranked else None,
                    "expected_rank": expected_rank,
                    "top1_match": expected_rank == 1,
                    "top3_match": bool(expected_rank and expected_rank <= 3),
                    "used_options": bool(option_texts),
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
                records.append(resolve_question(
                    question, law, articles, url, option_texts=option_texts
                ))

    route_counts = Counter(row["route"] for row in records)
    confidence_counts = Counter(row["confidence"] for row in records)
    decision_reason_counts = Counter(row.get("decision_reason") or row["route"] for row in records)
    control_top1 = sum(bool(row["top1_match"]) for row in controls)
    control_top3 = sum(bool(row["top3_match"]) for row in controls)
    source_errors = [
        {"law_name": law, "source_url": urls.get(law), "error": error}
        for law, error in sorted(errors.items()) if error
    ]
    return {
        "schema_version": 2,
        "method": "official current MOJ article text + official stem/options + metadata conflict gate; candidate only, never historical verification",
        "mapping_count": sum(len(card.get("questions") or []) for card in cards),
        "target_count": len(records),
        "explicit_control_count": len(controls),
        "explicit_control_top1_match_count": control_top1,
        "explicit_control_top3_match_count": control_top3,
        "route_counts": dict(sorted(route_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "decision_reason_counts": dict(sorted(decision_reason_counts.items())),
        "law_source_error_count": len(source_errors),
        "law_source_errors": source_errors,
        "question_shard_error_count": len(shard_errors),
        "question_shard_errors": shard_errors,
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
        "explicit_control_top3_match_count": report["explicit_control_top3_match_count"],
        "route_counts": report["route_counts"],
        "confidence_counts": report["confidence_counts"],
        "decision_reason_counts": report["decision_reason_counts"],
        "law_source_error_count": report["law_source_error_count"],
        "question_shard_error_count": report["question_shard_error_count"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
