#!/usr/bin/env python3
"""Stage 6: rerank questions against the exact historical MOJ law version.

Stage 3 selects an article using current-law text. Stage 4 proves which official
historical text was in force on the exam date. Stage 5 gates promotion using
shadow calibration. Stage 6 is an independent cross-check: fetch the selected
historical version again, rank the original stem + all answer-option text against
*all articles in that historical version*, and ask whether the Stage 3 article is
still the high-confidence top semantic match.

Safety boundary:
- never reads official_answer / accepted_answers / grading_mode;
- never mutates question data;
- never sets historical_version_checked=true;
- a semantic conflict only blocks promotion; it never changes the official key.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import historical_law_article_resolver as stage3
import historical_law_oldver_stage4 as stage4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINKS = ROOT / "data/law_question_links_priority10.v1.json"
DEFAULT_STAGE5 = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_stage6_semantic.v1.json"


def record_key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def question_lookup(links: dict) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for card in links.get("cards") or []:
        law = str(card.get("law_name") or "")
        for question in card.get("questions") or []:
            qid = str(question.get("question_id") or question.get("id") or "")
            if law and qid:
                out[(law, qid)] = question
    return out


def all_articles_from_page(page_html: str) -> list[dict]:
    """Union current-page and LawOldVer parsers by article number."""
    primary = stage3.parse_law_articles(page_html)
    fallback = stage4._oldver_articles_from_html(page_html)
    merged: dict[str, dict] = {}
    for row in primary + fallback:
        no = str(row.get("article_no") or "")
        text = stage3.normalize_text(row.get("text") or "")
        if not no or not text:
            continue
        # Prefer the richer body when both parsers see the same article.
        if no not in merged or len(text) > len(str(merged[no].get("text") or "")):
            merged[no] = {"article_no": no, "text": text}
    return list(merged.values())


def semantic_decision(expected_article: str, ranked: list[dict]) -> tuple[str, dict]:
    expected_rank = next(
        (idx + 1 for idx, row in enumerate(ranked) if row.get("article_no") == expected_article),
        None,
    )
    route, confidence, reason = stage3.classify_candidates(ranked, [])
    top = ranked[0] if ranked else {}
    second = ranked[1] if len(ranked) > 1 else {}
    margin = round(float(top.get("score") or 0) - float(second.get("score") or 0), 6)

    if expected_rank == 1 and route == "machine_candidate" and confidence == "high":
        status = "historical_semantic_confirmed"
    elif expected_rank == 1:
        status = "historical_semantic_support"
    else:
        status = "historical_semantic_conflict"

    return status, {
        "expected_rank": expected_rank,
        "historical_top_article": top.get("article_no"),
        "historical_top_score": top.get("score"),
        "historical_second_article": second.get("article_no"),
        "historical_second_score": second.get("score"),
        "historical_margin": margin,
        "historical_route": route,
        "historical_confidence": confidence,
        "historical_decision_reason": reason,
        "historical_top_candidates": ranked[:5],
    }


def build_report(stage5: dict, links: dict, session: Any) -> dict:
    questions = question_lookup(links)
    option_map, shard_errors = stage3.load_question_options(links)
    candidates = [
        row for row in (stage5.get("records") or [])
        if row.get("promotion_status") == "promotion_candidate"
    ]
    page_cache: dict[str, object] = {}
    records: list[dict] = []

    for row in candidates:
        key = record_key(row)
        expected_article = str(row.get("suggested_article") or "")
        version_url = str((row.get("selected_version") or {}).get("url") or "")
        base = {
            "law_name": key[0],
            "question_id": key[1],
            "exam_code": row.get("exam_code"),
            "suggested_article": expected_article or None,
            "selected_version": row.get("selected_version"),
            "historical_article_sha256": row.get("historical_article_sha256"),
            "historical_version_checked": False,
        }
        question = questions.get(key)
        if not question:
            records.append({**base, "status": "question_link_missing"})
            continue
        if not version_url:
            records.append({**base, "status": "selected_version_missing"})
            continue

        if version_url not in page_cache:
            try:
                page_cache[version_url] = stage4._get(session, version_url)
            except Exception as exc:
                page_cache[version_url] = exc
        page = page_cache[version_url]
        if isinstance(page, Exception):
            records.append({
                **base,
                "status": "source_failure",
                "source_error": f"{type(page).__name__}: {page}",
            })
            continue
        if not stage4._page_identity_ok(page):
            records.append({**base, "status": "source_identity_mismatch"})
            continue

        articles = all_articles_from_page(page)
        if not articles:
            records.append({**base, "status": "historical_articles_unavailable"})
            continue

        qkey = stage3.question_key(question)
        option_texts = option_map.get(qkey, []) if qkey else []
        stem = str(question.get("stem") or question.get("question") or "")
        ranked = stage3.rank_articles(
            stem,
            key[0],
            articles,
            option_texts=option_texts,
            limit=max(5, len(articles)),
        )
        status, evidence = semantic_decision(expected_article, ranked)
        records.append({
            **base,
            "status": status,
            "historical_article_count": len(articles),
            "used_options": bool(option_texts),
            **evidence,
        })

    counts = Counter(row["status"] for row in records)
    return {
        "schema_version": 1,
        "method": (
            "Stage5 promotion candidate -> exact selected MOJ exam-date version -> "
            "all historical articles -> stem + all options semantic rerank; independent "
            "cross-check only, never verification write"
        ),
        "stage5_promotion_candidate_count": len(candidates),
        "record_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "historical_semantic_confirmed_count": counts.get("historical_semantic_confirmed", 0),
        "historical_semantic_support_count": counts.get("historical_semantic_support", 0),
        "historical_semantic_conflict_count": counts.get("historical_semantic_conflict", 0),
        "question_shard_error_count": len(shard_errors),
        "question_shard_errors": shard_errors,
        "historical_version_checked_count": 0,
        "protected_core_mutation_count": 0,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage5", default=str(DEFAULT_STAGE5))
    parser.add_argument("--links", default=str(DEFAULT_LINKS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage5 = json.loads(Path(args.stage5).read_text(encoding="utf-8"))
    links = json.loads(Path(args.links).read_text(encoding="utf-8"))

    import requests
    session = requests.Session()
    try:
        report = build_report(stage5, links, session)
    finally:
        session.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage5_promotion_candidate_count": report["stage5_promotion_candidate_count"],
        "record_count": report["record_count"],
        "status_counts": report["status_counts"],
        "question_shard_error_count": report["question_shard_error_count"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
