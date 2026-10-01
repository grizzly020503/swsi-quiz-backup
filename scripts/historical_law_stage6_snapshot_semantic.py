#!/usr/bin/env python3
"""Stage 6 semantic cross-check using Stage 4's exact verified source snapshot.

Stage 4 owns source provenance/transport. Stage 6 independently revalidates the
hash-bound all-article snapshot and reranks the original question stem + all
options. Current versions may originate from the official MOJ Open API; old
versions may originate from identity-verified MOJ LawOldVer HTML. Stage 6 makes
no network request.

Safety boundary:
- never reads official_answer / accepted_answers / grading_mode;
- never mutates question data;
- never sets historical_version_checked=true;
- selected URL/kind, source identity and every article fingerprint must agree;
- snapshot IDs are re-derived from their bound source evidence;
- any missing/tampered/mismatched snapshot fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import historical_law_article_resolver as stage3
import historical_law_oldver_stage4 as stage4
import historical_law_stage6_semantic as stage6

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINKS = ROOT / "data/law_question_links_priority10.v1.json"
DEFAULT_STAGE4 = ROOT / "auto/qa/historical_law_oldver_stage4.v1.json"
DEFAULT_STAGE5 = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_stage6_semantic.v1.json"
MOJ_API_ENDPOINTS = {
    "https://law.moj.gov.tw/api/ch/law/json",
    "https://law.moj.gov.tw/api/ch/order/json",
}


def record_key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def question_lookup(links: dict) -> dict[tuple[str, str], dict]:
    return stage6.question_lookup(links)


def _official_moj_law_url(url: str) -> bool:
    return stage6._official_moj_law_url(url)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_sha256(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(raw)


def verified_snapshot_articles(stage4_row: dict, stage5_row: dict) -> tuple[list[dict] | None, str | None]:
    if stage4_row.get("status") != "historical_text_evidence_ready":
        return None, f"Stage4 status is {stage4_row.get('status') or 'missing'}"

    selected4 = stage4_row.get("selected_version") or {}
    selected5 = stage5_row.get("selected_version") or {}
    url4 = str(selected4.get("url") or "")
    url5 = str(selected5.get("url") or "")
    if not url4 or url4 != url5 or not _official_moj_law_url(url4):
        return None, "Stage4/5 selected official source URL mismatch"
    kind4 = str(selected4.get("kind") or "")
    kind5 = str(selected5.get("kind") or "")
    if not kind4 or kind4 != kind5:
        return None, "Stage4/5 selected version kind mismatch"

    expected = str(stage5_row.get("historical_article_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        return None, "Stage5 target article fingerprint missing"
    if str(stage4_row.get("historical_article_sha256") or "") != expected:
        return None, "Stage4/5 target article fingerprint mismatch"

    snapshot = stage4_row.get("historical_version_snapshot") or {}
    if str(snapshot.get("source_url") or "") != url4:
        return None, "Stage4 snapshot source URL mismatch"
    method = str(snapshot.get("source_identity_method") or "")
    if method not in {"stage4_moj_title", "moj_open_api_current"}:
        return None, "Stage4 snapshot source identity method unsupported"
    if str(stage4_row.get("source_identity_method") or "") != method:
        return None, "Stage4 row/snapshot source identity method mismatch"

    snapshot_id = str(snapshot.get("snapshot_id") or "")
    evidence_sha = str(snapshot.get("evidence_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
        return None, "Stage4 snapshot id missing"
    if not re.fullmatch(r"[0-9a-f]{64}", evidence_sha):
        return None, "Stage4 snapshot evidence fingerprint missing"

    if method == "stage4_moj_title":
        if kind4 != "oldver":
            return None, "MOJ old-version HTML snapshot used for non-oldver selected version"
        page_sha = str(snapshot.get("page_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", page_sha):
            return None, "Stage4 HTML page fingerprint missing"
        expected_snapshot_id = _sha256_text(f"{url4}\n{page_sha}")
        if snapshot_id != expected_snapshot_id:
            return None, "Stage4 HTML snapshot id mismatch"
    else:
        if kind4 != "current":
            return None, "MOJ Open API snapshot used for non-current selected version"
        if str(snapshot.get("api_endpoint") or "") not in MOJ_API_ENDPOINTS:
            return None, "MOJ Open API endpoint identity mismatch"
        api_url = str(snapshot.get("api_law_url") or "")
        if not _official_moj_law_url(api_url):
            return None, "MOJ Open API law URL is not official"
        pcode_selected = stage4.hp.pcode_from_url(url4)
        pcode_api = stage4.hp.pcode_from_url(api_url)
        if not pcode_selected or pcode_selected != pcode_api:
            return None, "MOJ Open API law URL PCode mismatch"
        source_identity_sha = str(snapshot.get("api_source_identity_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", source_identity_sha):
            return None, "MOJ Open API source identity fingerprint missing"
        expected_snapshot_id = _payload_sha256({
            "source_identity_sha256": source_identity_sha,
            "selected_version_url": url4,
            "articles_sha256": evidence_sha,
        })
        if snapshot_id != expected_snapshot_id:
            return None, "MOJ Open API snapshot id mismatch"

    raw_articles = snapshot.get("articles") or []
    if _payload_sha256(raw_articles) != evidence_sha:
        return None, "Stage4 snapshot aggregate evidence fingerprint mismatch"

    articles: list[dict] = []
    for row in raw_articles:
        article_no = str(row.get("article_no") or "")
        text = stage3.normalize_text(row.get("text") or "")
        stored_sha = str(row.get("sha256") or "")
        if not article_no or not text or stage4.article_fingerprint(text) != stored_sha:
            return None, f"Stage4 snapshot article fingerprint mismatch: {article_no or 'missing'}"
        articles.append({"article_no": article_no, "text": text})

    if len(articles) != int(snapshot.get("article_count") or -1) or not articles:
        return None, "Stage4 snapshot article count mismatch"

    expected_article = str(stage5_row.get("suggested_article") or "")
    target = next((row for row in articles if row.get("article_no") == expected_article), None)
    if not target or stage4.article_fingerprint(str(target.get("text") or "")) != expected:
        return None, "Stage4 snapshot target article fingerprint mismatch"
    return articles, None


def build_report(stage5: dict, stage4_report: dict, links: dict) -> dict:
    questions = question_lookup(links)
    option_map, shard_errors = stage3.load_question_options(links)
    stage4_map = {record_key(row): row for row in (stage4_report.get("records") or [])}
    candidates = [
        row for row in (stage5.get("records") or [])
        if row.get("promotion_status") == "promotion_candidate"
    ]
    records: list[dict] = []

    for row in candidates:
        key = record_key(row)
        expected_article = str(row.get("suggested_article") or "")
        expected_fingerprint = str(row.get("historical_article_sha256") or "")
        base = {
            "law_name": key[0],
            "question_id": key[1],
            "exam_code": row.get("exam_code"),
            "suggested_article": expected_article or None,
            "selected_version": row.get("selected_version"),
            "historical_article_sha256": expected_fingerprint or None,
            "historical_version_checked": False,
        }
        question = questions.get(key)
        if not question:
            records.append({**base, "status": "question_link_missing"})
            continue

        stage4_row = stage4_map.get(key) or {}
        articles, identity_error = verified_snapshot_articles(stage4_row, row)
        if articles is None:
            records.append({
                **base,
                "status": "source_identity_mismatch",
                "source_error": identity_error,
            })
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
        status, evidence = stage6.semantic_decision(expected_article, ranked)
        snapshot = stage4_row.get("historical_version_snapshot") or {}
        records.append({
            **base,
            "status": status,
            "source_identity_method": snapshot.get("source_identity_method"),
            "historical_snapshot_id": snapshot.get("snapshot_id"),
            "historical_evidence_sha256": snapshot.get("evidence_sha256"),
            "historical_article_count": len(articles),
            "used_options": bool(option_texts),
            **evidence,
        })

    counts = Counter(row["status"] for row in records)
    identity_counts = Counter(
        str(row.get("source_identity_method"))
        for row in records if row.get("source_identity_method")
    )
    return {
        "schema_version": 4,
        "method": (
            "Stage5 promotion candidate -> exact hash-bound Stage4 all-article snapshot -> "
            "selected-source URL/kind identity + re-derived snapshot ID + aggregate/per-article fingerprints -> "
            "stem + all options semantic rerank; supports official MOJ Open API current snapshots and "
            "identity-verified MOJ old-version HTML snapshots; no second network transport, "
            "semantic cross-check only, never verification write"
        ),
        "stage5_promotion_candidate_count": len(candidates),
        "record_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "source_identity_method_counts": dict(sorted(identity_counts.items())),
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
    parser.add_argument("--stage4", default=str(DEFAULT_STAGE4))
    parser.add_argument("--links", default=str(DEFAULT_LINKS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage5 = json.loads(Path(args.stage5).read_text(encoding="utf-8"))
    stage4_report = json.loads(Path(args.stage4).read_text(encoding="utf-8"))
    links = json.loads(Path(args.links).read_text(encoding="utf-8"))
    report = build_report(stage5, stage4_report, links)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage5_promotion_candidate_count": report["stage5_promotion_candidate_count"],
        "record_count": report["record_count"],
        "status_counts": report["status_counts"],
        "source_identity_method_counts": report["source_identity_method_counts"],
        "question_shard_error_count": report["question_shard_error_count"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
