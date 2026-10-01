#!/usr/bin/env python3
"""Stage 5 read-only promotion contract for historical-law provenance.

Stage 5 does not mutate question data and does not mark any question verified.
It combines Stage 3 article-candidate calibration with Stage 4 official
historical-text evidence and emits an auditable promotion-candidate report.

A record may become ``promotion_candidate`` only when:
- Stage 3 classified it as a high-confidence machine candidate;
- the real explicit-control shadow-routing calibration has zero false machine
  candidates;
- Stage 4 found the exact target article in the official MOJ version in force
  throughout the official exam window and produced a SHA-256 fingerprint.

Even then ``historical_version_checked`` remains false. A later materialization
step must separately decide whether to write verification metadata.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE3 = ROOT / "auto/qa/historical_law_article_stage3.v1.json"
DEFAULT_STAGE4 = ROOT / "auto/qa/historical_law_oldver_stage4.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"

ALLOWED_MACHINE_REASONS = {
    "official_text_semantics_and_metadata_agree",
    "very_strong_semantic_separation",
}


def record_key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def calibration_summary(stage3: dict) -> dict:
    control_count = int(stage3.get("explicit_control_count") or 0)
    top1 = int(stage3.get("explicit_control_top1_match_count") or 0)
    top3 = int(stage3.get("explicit_control_top3_match_count") or 0)
    shadow_machine = int(stage3.get("explicit_control_shadow_machine_candidate_count") or 0)
    false_machine = int(stage3.get("explicit_control_false_machine_candidate_count") or 0)
    safe = (
        control_count >= 10
        and top1 >= 9
        and top3 >= 9
        and false_machine == 0
    )
    return {
        "explicit_control_count": control_count,
        "top1_match_count": top1,
        "top3_match_count": top3,
        "shadow_machine_candidate_count": shadow_machine,
        "false_machine_candidate_count": false_machine,
        "promotion_calibration_safe": safe,
    }


def build_report(stage3: dict, stage4: dict) -> dict:
    calibration = calibration_summary(stage3)
    stage3_machine = {
        record_key(row): row
        for row in (stage3.get("records") or [])
        if row.get("route") == "machine_candidate"
    }
    stage4_rows = {record_key(row): row for row in (stage4.get("records") or [])}

    records: list[dict] = []
    for key in sorted(stage3_machine):
        s3 = stage3_machine[key]
        s4 = stage4_rows.get(key) or {}
        blockers: list[str] = []

        if not calibration["promotion_calibration_safe"]:
            blockers.append("stage3_shadow_calibration_not_safe")
        if s3.get("confidence") != "high":
            blockers.append("stage3_not_high_confidence")
        if s3.get("decision_reason") not in ALLOWED_MACHINE_REASONS:
            blockers.append("stage3_reason_not_allowlisted")
        if not s3.get("suggested_article"):
            blockers.append("stage3_article_missing")
        if s4.get("status") != "historical_text_evidence_ready":
            blockers.append("stage4_historical_text_not_ready")
        if s4.get("suggested_article") != s3.get("suggested_article"):
            blockers.append("stage3_stage4_article_mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", str(s4.get("historical_article_sha256") or "")):
            blockers.append("stage4_fingerprint_missing")
        if not (s4.get("selected_version") or {}).get("url"):
            blockers.append("stage4_version_url_missing")
        if not s4.get("official_history_url"):
            blockers.append("stage4_history_url_missing")
        if not s4.get("exam_date_source_url"):
            blockers.append("exam_date_source_missing")

        status = "promotion_candidate" if not blockers else "blocked"
        records.append({
            "law_name": key[0],
            "question_id": key[1],
            "exam_code": s3.get("exam_code"),
            "suggested_article": s3.get("suggested_article"),
            "stage3_confidence": s3.get("confidence"),
            "stage3_decision_reason": s3.get("decision_reason"),
            "stage3_metadata_articles": s3.get("metadata_articles") or [],
            "stage4_status": s4.get("status"),
            "historical_article_sha256": s4.get("historical_article_sha256"),
            "historical_article_char_count": s4.get("historical_article_char_count"),
            "selected_version": s4.get("selected_version"),
            "official_history_url": s4.get("official_history_url"),
            "exam_date_source_url": s4.get("exam_date_source_url"),
            "promotion_status": status,
            "blockers": blockers,
            "historical_version_checked": False,
            "protected_core_mutation": False,
        })

    counts = Counter(row["promotion_status"] for row in records)
    return {
        "schema_version": 1,
        "method": (
            "Stage3 high-confidence article candidate + zero-false-machine explicit-control "
            "shadow calibration + Stage4 official MOJ exam-window article fingerprint; "
            "read-only promotion candidate only"
        ),
        "calibration": calibration,
        "stage3_machine_candidate_count": len(stage3_machine),
        "stage4_record_count": int(stage4.get("record_count") or 0),
        "record_count": len(records),
        "promotion_status_counts": dict(sorted(counts.items())),
        "promotion_candidate_count": counts.get("promotion_candidate", 0),
        "blocked_count": counts.get("blocked", 0),
        "historical_version_checked_count": 0,
        "protected_core_mutation_count": 0,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage3", default=str(DEFAULT_STAGE3))
    parser.add_argument("--stage4", default=str(DEFAULT_STAGE4))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage3 = json.loads(Path(args.stage3).read_text(encoding="utf-8"))
    stage4 = json.loads(Path(args.stage4).read_text(encoding="utf-8"))
    report = build_report(stage3, stage4)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "calibration": report["calibration"],
        "stage3_machine_candidate_count": report["stage3_machine_candidate_count"],
        "record_count": report["record_count"],
        "promotion_status_counts": report["promotion_status_counts"],
        "historical_version_checked_count": report["historical_version_checked_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
