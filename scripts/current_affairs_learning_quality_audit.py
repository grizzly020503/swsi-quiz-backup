#!/usr/bin/env python3
"""Deterministic audit for student-facing current-affairs trend cards.

The audit deliberately separates:
- hard_errors: structural/evidence contracts that can be checked deterministically;
- review_flags: semantic/editorial risks that require human review and MUST NOT
  auto-attach laws, delete historical relations, or promote/demote content.

It never mutates the source snapshot or Official Core.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_POLICY = "data/current_affairs_learning_quality_policy.v1.json"
DEFAULT_SNAPSHOT = "auto/current_affairs_trends.json"


class AuditError(ValueError):
    pass


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def _valid_web_url(value: Any) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AuditError(f"missing file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuditError(f"expected object: {path}")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise AuditError("policy schema_version must be 1")
    hard = policy.get("hard_requirements")
    review = policy.get("review_only_rules")
    tiers = policy.get("presentation_tiers")
    if not isinstance(hard, dict) or not isinstance(review, dict) or not isinstance(tiers, dict):
        raise AuditError("policy hard_requirements/review_only_rules/presentation_tiers are required")
    min_primary = int(hard.get("primary_subject_min", 0))
    max_primary = int(hard.get("primary_subject_max", 0))
    if min_primary < 1 or max_primary < min_primary or max_primary > 5:
        raise AuditError("invalid primary subject bounds")
    threshold = int(review.get("broad_relation_without_strong_threshold", 0))
    if threshold < 1:
        raise AuditError("broad relation review threshold must be >= 1")
    for key in ("strong_historical_support", "medium_historical_relation", "concept_observation"):
        if key not in tiers:
            raise AuditError(f"presentation tier missing: {key}")


def presentation_tier(trend: dict[str, Any]) -> str:
    breakdown = trend.get("historical_match_breakdown") or {}
    strong = int(breakdown.get("strong") or 0)
    medium = int(breakdown.get("medium") or 0)
    if strong > 0:
        return "strong_historical_support"
    if medium > 0:
        return "medium_historical_relation"
    return "concept_observation"


def _law_context_in_related_questions(trend: dict[str, Any], tokens: list[str]) -> list[str]:
    hits: list[str] = []
    for row in trend.get("related_exam_questions") or []:
        if not isinstance(row, dict):
            continue
        haystack = " | ".join(
            str(row.get(field) or "")
            for field in ("major", "topic", "match_reason")
        )
        if any(token in haystack for token in tokens):
            qid = str(row.get("id") or "unknown")
            hits.append(qid)
    return sorted(set(hits))


def audit_trend(trend: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    hard_policy = policy["hard_requirements"]
    review_policy = policy["review_only_rules"]
    event_id = str(trend.get("canonical_event_id") or "").strip()
    title = str(trend.get("title") or "").strip()
    hard_errors: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []

    def hard(code: str, detail: str) -> None:
        hard_errors.append({"code": code, "detail": detail})

    def review(code: str, detail: str, evidence: Any = None) -> None:
        row: dict[str, Any] = {"code": code, "detail": detail}
        if evidence is not None:
            row["evidence"] = evidence
        review_flags.append(row)

    if not event_id:
        hard("missing_event_id", "canonical_event_id is required")
    if not title:
        hard("missing_title", "student-facing event title is required")

    primary = _strings(trend.get("primary_exam_subject_axes"))
    supporting = _strings(trend.get("supporting_exam_subject_axes"))
    axes = _strings(trend.get("exam_subject_axes"))
    if len(primary) < int(hard_policy["primary_subject_min"]) or len(primary) > int(hard_policy["primary_subject_max"]):
        hard("primary_subject_count", f"primary subject count={len(primary)} outside policy bounds")
    if len(set(primary)) != len(primary):
        hard("duplicate_primary_subject", "primary_exam_subject_axes contains duplicates")
    if len(set(supporting)) != len(supporting):
        hard("duplicate_supporting_subject", "supporting_exam_subject_axes contains duplicates")
    overlap = sorted(set(primary) & set(supporting))
    if overlap and hard_policy.get("primary_supporting_must_be_disjoint") is True:
        hard("primary_supporting_overlap", f"overlap={overlap}")
    if hard_policy.get("subject_axes_must_cover_primary_and_supporting") is True:
        missing_axes = sorted((set(primary) | set(supporting)) - set(axes))
        if missing_axes:
            hard("subject_axes_missing_roles", f"exam_subject_axes missing={missing_axes}")

    topics = trend.get("subject_topics") if isinstance(trend.get("subject_topics"), dict) else {}
    if hard_policy.get("primary_subject_requires_topic") is True:
        for subject in primary:
            if not _strings(topics.get(subject)):
                hard("primary_subject_missing_topic", f"primary subject has no study topic: {subject}")

    source_count = int(trend.get("source_count") or 0)
    official_count = int(trend.get("official_source_count") or 0)
    evidence = trend.get("evidence") if isinstance(trend.get("evidence"), list) else []
    if source_count < 1:
        hard("invalid_source_count", "source_count must be >= 1")
    if hard_policy.get("official_source_count_must_not_exceed_source_count") is True and official_count > source_count:
        hard("official_source_count_exceeds_total", f"official={official_count}, total={source_count}")
    if hard_policy.get("evidence_required") is True and not evidence:
        hard("missing_evidence", "at least one source evidence record is required")

    unique_urls: set[str] = set()
    for idx, row in enumerate(evidence):
        if not isinstance(row, dict):
            hard("invalid_evidence_record", f"evidence[{idx}] must be an object")
            continue
        source_name = str(row.get("source_name") or "").strip()
        source_url = str(row.get("source_url") or "").strip()
        if hard_policy.get("evidence_requires_source_name_and_url") is True:
            if not source_name:
                hard("evidence_missing_source_name", f"evidence[{idx}] has no source_name")
            if not _valid_web_url(source_url):
                hard("evidence_invalid_source_url", f"evidence[{idx}] has invalid source_url")
        if source_url:
            unique_urls.add(source_url)

    if review_policy.get("declared_source_count_mismatch") is True and evidence and source_count != len(unique_urls):
        review(
            "declared_source_count_mismatch",
            "declared source_count differs from unique evidence URLs; review aggregation semantics rather than auto-fixing",
            {"declared": source_count, "unique_evidence_urls": len(unique_urls)},
        )
    if review_policy.get("single_source") is True and source_count == 1:
        review("single_source", "event currently has only one declared source")
    if (
        review_policy.get("single_source_sustained_or_rising") is True
        and source_count == 1
        and str(trend.get("trend_state") or "") in {"sustained", "rising"}
    ):
        review(
            "single_source_trend_state",
            f"trend_state={trend.get('trend_state')} with one source; persistence may be real, but cross-source support is absent",
        )

    related = trend.get("related_exam_questions") if isinstance(trend.get("related_exam_questions"), list) else []
    for idx, row in enumerate(related):
        if not isinstance(row, dict):
            hard("invalid_related_question_record", f"related_exam_questions[{idx}] must be an object")
            continue
        if hard_policy.get("related_exam_question_requires_id_and_reason") is True:
            if not str(row.get("id") or "").strip():
                hard("related_question_missing_id", f"related_exam_questions[{idx}] missing id")
            if not str(row.get("match_reason") or "").strip():
                hard("related_question_missing_reason", f"related_exam_questions[{idx}] missing match_reason")

    hist_count = int(trend.get("historical_question_count") or 0)
    if review_policy.get("declared_historical_count_mismatch") is True and hist_count != len(related):
        review(
            "declared_historical_count_mismatch",
            "historical_question_count differs from emitted related_exam_questions; inspect whether the list is intentionally truncated",
            {"declared": hist_count, "emitted": len(related)},
        )

    breakdown = trend.get("historical_match_breakdown") if isinstance(trend.get("historical_match_breakdown"), dict) else {}
    strong = int(breakdown.get("strong") or 0)
    medium = int(breakdown.get("medium") or 0)
    concept = int(breakdown.get("concept") or 0)
    if review_policy.get("historical_relation_without_strong_match") is True and hist_count > 0 and strong == 0:
        review(
            "historical_relation_without_strong_match",
            "historical relations exist but none are strong; student copy should not imply precise historical support",
            {"strong": strong, "medium": medium, "concept": concept},
        )
    broad_threshold = int(review_policy.get("broad_relation_without_strong_threshold") or 0)
    if hist_count >= broad_threshold and strong == 0:
        review(
            "broad_relation_volume_without_strong_match",
            "many historical relations are medium/concept only; review precision before presenting volume as trend strength",
            {"historical_question_count": hist_count, "threshold": broad_threshold},
        )

    related_laws = _strings(trend.get("related_laws"))
    law_tokens = _strings(policy.get("law_context_tokens"))
    law_hits = _law_context_in_related_questions(trend, law_tokens)
    if review_policy.get("law_context_without_related_laws") is True and not related_laws and law_hits:
        review(
            "law_context_without_related_laws",
            "related historical questions contain explicit law/regulation context while event related_laws is empty; review whether a law link is substantively justified",
            {"related_question_ids": law_hits},
        )

    why = _strings(trend.get("why"))
    if hard_policy.get("student_card_requires_why") is True and not why:
        hard("student_card_missing_why", "student-facing card needs at least one evidence/relevance reason")
    essay_direction = str(trend.get("essay_direction") or "").strip()
    mcq_focus = _strings(trend.get("mcq_focus"))
    if hard_policy.get("student_card_requires_practice_direction") is True and not essay_direction and not mcq_focus:
        hard("student_card_missing_practice", "student-facing card needs essay_direction or mcq_focus")

    tier = presentation_tier(trend)
    return {
        "canonical_event_id": event_id or None,
        "title": title or None,
        "trend_state": trend.get("trend_state"),
        "trend_score": trend.get("trend_score"),
        "source_count": source_count,
        "historical_question_count": hist_count,
        "historical_match_breakdown": {"strong": strong, "medium": medium, "concept": concept},
        "presentation_tier": tier,
        "hard_errors": sorted(hard_errors, key=lambda x: (x["code"], x["detail"])),
        "review_flags": sorted(review_flags, key=lambda x: (x["code"], x["detail"])),
    }


def audit_snapshot(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if snapshot.get("schema_version") != policy.get("source_snapshot_schema_version"):
        raise AuditError("unsupported current-affairs snapshot schema_version")
    trends = snapshot.get("trends")
    if not isinstance(trends, list):
        raise AuditError("snapshot trends[] is required")
    rows = [audit_trend(row, policy) for row in trends if isinstance(row, dict)]
    rows.sort(key=lambda x: (str(x.get("canonical_event_id") or ""), str(x.get("title") or "")))
    hard_counts = Counter(item["code"] for row in rows for item in row["hard_errors"])
    review_counts = Counter(item["code"] for row in rows for item in row["review_flags"])
    tier_counts = Counter(row["presentation_tier"] for row in rows)
    return {
        "audit_schema_version": 1,
        "source_schema_version": snapshot.get("schema_version"),
        "source_generated_at": snapshot.get("generated_at"),
        "source_method": snapshot.get("method"),
        "event_count": len(rows),
        "hard_error_count": sum(hard_counts.values()),
        "hard_error_event_count": sum(1 for row in rows if row["hard_errors"]),
        "review_flag_count": sum(review_counts.values()),
        "review_event_count": sum(1 for row in rows if row["review_flags"]),
        "presentation_tier_counts": dict(sorted(tier_counts.items())),
        "hard_error_counts": dict(sorted(hard_counts.items())),
        "review_flag_counts": dict(sorted(review_counts.items())),
        "events": rows,
        "mutation_allowed": False,
        "semantic_review_flags_are_advisory": True,
    }


def _fixture_event(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "canonical_event_id": "fixture-1",
        "title": "合成測試事件",
        "trend_state": "one-off",
        "trend_score": 2.0,
        "exam_subject_axes": ["社會政策與社會立法", "社會工作"],
        "primary_exam_subject_axes": ["社會政策與社會立法"],
        "supporting_exam_subject_axes": ["社會工作"],
        "subject_topics": {
            "社會政策與社會立法": ["合成政策主題"],
            "社會工作": ["合成支持主題"]
        },
        "source_count": 1,
        "official_source_count": 1,
        "evidence": [{"source_name": "合成官方來源", "source_url": "https://example.invalid/item"}],
        "historical_question_count": 1,
        "historical_match_breakdown": {"strong": 1, "medium": 0, "concept": 0},
        "related_exam_questions": [{
            "id": "SP999-1-01",
            "major": "合成主題",
            "topic": "一般政策",
            "match_reason": "同主題直接關聯",
            "match_score": 5.0
        }],
        "related_laws": [],
        "why": ["合成證據理由"],
        "essay_direction": "以合成事件練習政策分析。",
        "mcq_focus": ["合成事實"]
    }
    row.update(overrides)
    return row


def self_test(policy: dict[str, Any]) -> dict[str, Any]:
    clean = audit_trend(_fixture_event(), policy)
    assert not clean["hard_errors"]
    assert clean["presentation_tier"] == "strong_historical_support"
    assert any(x["code"] == "single_source" for x in clean["review_flags"])

    broken = _fixture_event(
        primary_exam_subject_axes=["社會政策與社會立法", "社會工作", "社會工作直接服務"],
        supporting_exam_subject_axes=["社會工作"],
        subject_topics={"社會工作": ["合成"]},
        official_source_count=2,
        evidence=[],
        related_exam_questions=[{"id": "SP999-1-01", "match_reason": ""}],
        why=[],
        essay_direction="",
        mcq_focus=[]
    )
    bad = audit_trend(broken, policy)
    bad_codes = {x["code"] for x in bad["hard_errors"]}
    assert {
        "primary_subject_count",
        "primary_supporting_overlap",
        "primary_subject_missing_topic",
        "official_source_count_exceeds_total",
        "missing_evidence",
        "related_question_missing_reason",
        "student_card_missing_why",
        "student_card_missing_practice",
    }.issubset(bad_codes)

    broad = _fixture_event(
        trend_state="sustained",
        historical_question_count=8,
        historical_match_breakdown={"strong": 0, "medium": 7, "concept": 1},
        related_exam_questions=[
            {"id": f"SP999-1-{i:02d}", "major": "兒少福利法規", "topic": "兒少權法 > 合成", "match_reason": "同義考點：合成", "match_score": 3.0}
            for i in range(1, 9)
        ],
        related_laws=[]
    )
    review_row = audit_trend(broad, policy)
    review_codes = {x["code"] for x in review_row["review_flags"]}
    assert {
        "single_source_trend_state",
        "historical_relation_without_strong_match",
        "broad_relation_volume_without_strong_match",
        "law_context_without_related_laws",
    }.issubset(review_codes)
    assert review_row["presentation_tier"] == "medium_historical_relation"
    assert not review_row["hard_errors"]

    return {"status": "pass", "cases": 3, "hard_vs_review_separated": True}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(root / DEFAULT_SNAPSHOT))
    ap.add_argument("--policy", default=str(root / DEFAULT_POLICY))
    ap.add_argument("--output")
    ap.add_argument("--fail-on-hard", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    policy = load_json(Path(args.policy))
    validate_policy(policy)
    if args.self_test:
        print(json.dumps(self_test(policy), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    snapshot = load_json(Path(args.snapshot))
    result = audit_snapshot(snapshot, policy)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    if args.fail_on_hard and result["hard_error_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
