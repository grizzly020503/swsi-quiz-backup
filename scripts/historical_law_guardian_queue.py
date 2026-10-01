#!/usr/bin/env python3
"""Build a compact historical-law work queue for SWSI Data Guardian.

This is a routing layer only. It combines the read-only Stage 2/3/5/6 reports
and keeps routine work out of the human queue:

- Stage 6 confirmed candidates stay in a machine-promotion lane.
- Stage 6 semantic support goes to AI semantic review.
- Stage 6 source failures/identity misses go to source retry.
- Stage 6 semantic conflicts are the exceptional human-review lane.
- Stage 3 unresolved article candidates go to AI article review.
- explicit-article current-text candidates stay in a direct source-check lane.
- special/delayed effective-date cases stay in a legal-evidence lane.

No row is marked historically verified here and no official answer/grading field
is copied into the queue.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE2 = ROOT / "auto/qa/historical_law_exam_date_stage2.v1.json"
DEFAULT_STAGE3 = ROOT / "auto/qa/historical_law_article_stage3.v1.json"
DEFAULT_STAGE5 = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"
DEFAULT_STAGE6 = ROOT / "auto/qa/historical_law_stage6_semantic.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_guardian_queue.v1.json"

LANE_MACHINE_PROMOTION = "machine_promotion"
LANE_AI_ARTICLE = "ai_article_review"
LANE_AI_SEMANTIC = "ai_semantic_review"
LANE_DIRECT_SOURCE = "machine_direct_source_check"
LANE_EFFECTIVE_DATE = "effective_date_resolution"
LANE_SOURCE_RETRY = "source_retry"
LANE_EVIDENCE_BLOCKED = "machine_evidence_blocked"
LANE_HUMAN = "human_review"


def key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def _base(row: dict) -> dict:
    return {
        "law_name": row.get("law_name"),
        "question_id": row.get("question_id"),
        "exam_code": row.get("exam_code"),
        "historical_version_checked": False,
    }


def build_queue(stage2: dict, stage3: dict, stage5: dict, stage6: dict) -> dict:
    stage3_map = {key(row): row for row in (stage3.get("records") or [])}
    stage5_map = {key(row): row for row in (stage5.get("records") or [])}
    stage6_map = {key(row): row for row in (stage6.get("records") or [])}
    items: list[dict] = []

    for row in (stage2.get("questions") or []):
        item = _base(row)
        k = key(row)
        status2 = str(row.get("status") or "")
        priority = "normal"
        reason = status2 or "unknown_stage2_status"
        lane = LANE_SOURCE_RETRY

        if status2 == "article_resolution_required":
            s3 = stage3_map.get(k) or {}
            route3 = str(s3.get("route") or "")
            confidence3 = str(s3.get("confidence") or "")
            reason3 = str(s3.get("decision_reason") or route3)
            item.update({
                "stage3_route": route3 or None,
                "stage3_confidence": confidence3 or None,
                "stage3_reason": reason3 or None,
                "suggested_article": s3.get("suggested_article"),
            })
            if route3 == "machine_candidate":
                s5 = stage5_map.get(k) or {}
                promotion = str(s5.get("promotion_status") or "")
                item.update({
                    "stage5_promotion_status": promotion or None,
                    "stage5_blockers": s5.get("blockers") or [],
                    "historical_article_sha256": s5.get("historical_article_sha256"),
                })
                if promotion == "promotion_candidate":
                    s6 = stage6_map.get(k) or {}
                    status6 = str(s6.get("status") or "")
                    item.update({
                        "stage6_status": status6 or None,
                        "stage6_source_identity_method": s6.get("source_identity_method"),
                        "stage6_source_error": s6.get("source_error"),
                        "stage6_expected_rank": s6.get("expected_rank"),
                    })
                    if status6 == "historical_semantic_confirmed":
                        lane = LANE_MACHINE_PROMOTION
                        reason = "stage6_historical_semantic_confirmed"
                    elif status6 == "historical_semantic_support":
                        lane = LANE_AI_SEMANTIC
                        reason = "stage6_historical_semantic_support"
                    elif status6 in {
                        "source_failure",
                        "source_identity_mismatch",
                        "historical_articles_unavailable",
                    }:
                        lane = LANE_SOURCE_RETRY
                        reason = f"stage6_{status6}"
                        priority = "high"
                    elif status6 == "historical_semantic_conflict":
                        lane = LANE_HUMAN
                        reason = "stage6_historical_semantic_conflict"
                        priority = "high"
                    elif status6 in {
                        "question_link_missing",
                        "selected_version_missing",
                    }:
                        lane = LANE_EVIDENCE_BLOCKED
                        reason = f"stage6_{status6}"
                        priority = "high"
                    else:
                        lane = LANE_EVIDENCE_BLOCKED
                        reason = "stage6_missing_or_unknown_status"
                        priority = "high"
                else:
                    lane = LANE_EVIDENCE_BLOCKED
                    reason = "stage5_not_promotion_ready"
                    priority = "high"
            elif route3 == "ai_review":
                lane = LANE_AI_ARTICLE
                reason = reason3 or "stage3_ai_review"
                if confidence3 == "conflict" or reason3 == "semantic_metadata_disagree":
                    priority = "high"
                elif confidence3 == "low":
                    priority = "low"
            elif route3 == "source_failure":
                lane = LANE_SOURCE_RETRY
                reason = "stage3_source_failure"
                priority = "high"
            else:
                lane = LANE_EVIDENCE_BLOCKED
                reason = "stage3_missing_or_unknown_route"
                priority = "high"

        elif status2 in {
            "current_text_equals_exam_date_candidate",
            "current_text_equals_exam_year_candidate",
        }:
            lane = LANE_DIRECT_SOURCE
            reason = status2
        elif status2 == "effective_date_review":
            lane = LANE_EFFECTIVE_DATE
            reason = "special_or_delayed_effective_date"
            priority = "high"
        elif status2 in {"official_history_unavailable", "source_failure"}:
            lane = LANE_SOURCE_RETRY
            reason = status2
            priority = "high"
        else:
            lane = LANE_SOURCE_RETRY
            reason = f"unrecognized_stage2_status:{status2 or 'missing'}"
            priority = "high"

        item.update({
            "lane": lane,
            "priority": priority,
            "reason": reason,
            "human_review_required": lane == LANE_HUMAN,
        })
        items.append(item)

    lane_counts = Counter(str(row["lane"]) for row in items)
    priority_counts = Counter(str(row["priority"]) for row in items)
    human_items = [row for row in items if row["lane"] == LANE_HUMAN]
    return {
        "schema_version": 2,
        "method": "Stage2 provenance -> Stage3 article routing -> Stage5 evidence promotion -> Stage6 historical semantic/source routing; only confirmed cases remain machine-promotion candidates",
        "mapping_count": len(items),
        "unique_question_count": len({str(row.get('question_id') or '') for row in items}),
        "lane_counts": dict(sorted(lane_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "human_queue_count": len(human_items),
        "historical_version_checked_count": 0,
        "protected_core_mutation_count": 0,
        "lanes": {
            lane: [row for row in items if row["lane"] == lane]
            for lane in sorted(lane_counts)
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage2", default=str(DEFAULT_STAGE2))
    parser.add_argument("--stage3", default=str(DEFAULT_STAGE3))
    parser.add_argument("--stage5", default=str(DEFAULT_STAGE5))
    parser.add_argument("--stage6", default=str(DEFAULT_STAGE6))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage2 = json.loads(Path(args.stage2).read_text(encoding="utf-8"))
    stage3 = json.loads(Path(args.stage3).read_text(encoding="utf-8"))
    stage5 = json.loads(Path(args.stage5).read_text(encoding="utf-8"))
    stage6 = json.loads(Path(args.stage6).read_text(encoding="utf-8"))
    report = build_queue(stage2, stage3, stage5, stage6)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mapping_count": report["mapping_count"],
        "unique_question_count": report["unique_question_count"],
        "lane_counts": report["lane_counts"],
        "priority_counts": report["priority_counts"],
        "human_queue_count": report["human_queue_count"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
