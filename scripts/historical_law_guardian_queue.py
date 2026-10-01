#!/usr/bin/env python3
"""Route historical-law evidence into compact SWSI Data Guardian lanes.

The Guardian does not decide official answers and does not mutate question data.
It consumes Stage 2/3/5/6 read-only evidence plus the Stage 7 verified overlay.
Already verified mappings are removed from active work; every unresolved mapping
is routed to the cheapest safe machine/AI/source-evidence lane before humans.
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
DEFAULT_VERIFIED = ROOT / "data/historical_law_verified_priority10.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_guardian_queue.v2.json"

LANE_VERIFIED = "verified_complete"
LANE_AI_ARTICLE = "ai_article_review"
LANE_AI_HISTORICAL = "ai_historical_semantic_review"
LANE_DIRECT_SOURCE = "machine_direct_source_check"
LANE_EFFECTIVE_DATE = "effective_date_resolution"
LANE_SOURCE_RETRY = "source_retry"
LANE_MATERIALIZE = "machine_materialization_pending"
LANE_EVIDENCE_BLOCKED = "machine_evidence_blocked"
LANE_HUMAN = "human_review"


def key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def _map(report: dict, field: str = "records") -> dict[tuple[str, str], dict]:
    return {key(row): row for row in (report.get(field) or []) if all(key(row))}


def _base(row: dict) -> dict:
    return {
        "law_name": row.get("law_name"),
        "question_id": row.get("question_id"),
        "exam_code": row.get("exam_code"),
    }


def build_queue(
    stage2: dict,
    stage3: dict,
    stage5: dict,
    stage6: dict,
    verified: dict,
) -> dict:
    stage3_map = _map(stage3)
    stage5_map = _map(stage5)
    stage6_map = _map(stage6)
    verified_map = _map(verified)
    items: list[dict] = []

    for row in (stage2.get("questions") or []):
        k = key(row)
        item = _base(row)
        status2 = str(row.get("status") or "")
        priority = "normal"
        lane = LANE_SOURCE_RETRY
        reason = status2 or "missing_stage2_status"

        v = verified_map.get(k)
        if v and v.get("historical_version_checked") is True:
            lane = LANE_VERIFIED
            reason = "stage7_verified_overlay"
            priority = "complete"
            item.update({
                "historical_version_checked": True,
                "verification_level": v.get("verification_level"),
                "verified_article": v.get("article"),
                "historical_article_sha256": v.get("historical_article_sha256"),
                "selected_version": v.get("selected_version"),
            })
        else:
            item["historical_version_checked"] = False

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

                if route3 == "ai_review":
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
                elif route3 == "machine_candidate":
                    s5 = stage5_map.get(k) or {}
                    s6 = stage6_map.get(k) or {}
                    status6 = str(s6.get("status") or "")
                    item.update({
                        "stage5_promotion_status": s5.get("promotion_status"),
                        "stage5_blockers": s5.get("blockers") or [],
                        "stage6_status": status6 or None,
                        "historical_top_article": s6.get("historical_top_article"),
                        "historical_margin": s6.get("historical_margin"),
                    })
                    if status6 == "historical_semantic_confirmed":
                        lane = LANE_MATERIALIZE
                        reason = "stage6_confirmed_not_yet_in_verified_overlay"
                        priority = "high"
                    elif status6 == "historical_semantic_support":
                        lane = LANE_AI_HISTORICAL
                        reason = "historical_top1_needs_stronger_semantic_evidence"
                    elif status6 == "historical_semantic_conflict":
                        lane = LANE_AI_HISTORICAL
                        reason = "historical_semantic_conflict"
                        priority = "high"
                    elif status6 in {"source_identity_mismatch", "source_failure"}:
                        lane = LANE_SOURCE_RETRY
                        reason = status6
                        priority = "high"
                    elif status6:
                        lane = LANE_EVIDENCE_BLOCKED
                        reason = f"stage6_blocked:{status6}"
                        priority = "high"
                    elif s5.get("promotion_status") == "promotion_candidate":
                        lane = LANE_EVIDENCE_BLOCKED
                        reason = "stage6_evidence_missing"
                        priority = "high"
                    else:
                        lane = LANE_EVIDENCE_BLOCKED
                        reason = "stage5_or_stage6_evidence_missing"
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
            "stage2_status": status2 or None,
            "lane": lane,
            "priority": priority,
            "reason": reason,
            "active_work": lane != LANE_VERIFIED,
            "human_review_required": lane == LANE_HUMAN,
        })
        items.append(item)

    lane_counts = Counter(str(row["lane"]) for row in items)
    priority_counts = Counter(str(row["priority"]) for row in items)
    verified_count = lane_counts.get(LANE_VERIFIED, 0)
    human_count = lane_counts.get(LANE_HUMAN, 0)
    active = [row for row in items if row["active_work"]]

    return {
        "schema_version": 2,
        "method": (
            "Stage7 verified overlay first; unresolved mappings route through Stage2/3/5/6 "
            "machine, AI, effective-date, and source-recovery lanes before human review"
        ),
        "mapping_count": len(items),
        "unique_question_count": len({str(row.get("question_id") or "") for row in items}),
        "verified_complete_count": verified_count,
        "active_queue_count": len(active),
        "lane_counts": dict(sorted(lane_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "human_queue_count": human_count,
        "protected_core_mutation_count": 0,
        "historical_version_checked_count": verified_count,
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
    parser.add_argument("--verified", default=str(DEFAULT_VERIFIED))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage2 = json.loads(Path(args.stage2).read_text(encoding="utf-8"))
    stage3 = json.loads(Path(args.stage3).read_text(encoding="utf-8"))
    stage5 = json.loads(Path(args.stage5).read_text(encoding="utf-8"))
    stage6 = json.loads(Path(args.stage6).read_text(encoding="utf-8"))
    verified_path = Path(args.verified)
    verified = json.loads(verified_path.read_text(encoding="utf-8")) if verified_path.exists() else {}
    report = build_queue(stage2, stage3, stage5, stage6, verified)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mapping_count": report["mapping_count"],
        "unique_question_count": report["unique_question_count"],
        "verified_complete_count": report["verified_complete_count"],
        "active_queue_count": report["active_queue_count"],
        "lane_counts": report["lane_counts"],
        "human_queue_count": report["human_queue_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
