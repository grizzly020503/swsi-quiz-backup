#!/usr/bin/env python3
"""Stage 7 materializes verified historical-law metadata into a separate overlay.

This is the first stage allowed to emit ``historical_version_checked=true``, and
only inside the dedicated derived registry.  It never mutates question shards,
official answers, accepted answers, grading modes, stems, or options.

Materialization is monotonic: an existing verified record remains present during
source outages.  If fresh evidence for an existing key changes the historical
article SHA-256 or article number, the script fails closed with an evidence
conflict rather than silently overwriting provenance.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE5 = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"
DEFAULT_STAGE6 = ROOT / "auto/qa/historical_law_stage6_semantic.v1.json"
DEFAULT_EXISTING = ROOT / "data/historical_law_verified_priority10.v1.json"
DEFAULT_OUTPUT = DEFAULT_EXISTING

VERIFICATION_LEVEL = "machine_verified_historical_v1"
VERIFICATION_BASIS = (
    "Stage3 zero-false-machine shadow calibration + Stage4 official MOJ exam-date "
    "article fingerprint + Stage6 historical-version semantic top1 high confidence"
)


def key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def _valid_sha(value: object) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def candidate_records(stage5: dict, stage6: dict) -> list[dict]:
    s5 = {
        key(row): row for row in (stage5.get("records") or [])
        if row.get("promotion_status") == "promotion_candidate"
    }
    records: list[dict] = []
    for row in stage6.get("records") or []:
        if row.get("status") != "historical_semantic_confirmed":
            continue
        k = key(row)
        p = s5.get(k)
        if not p:
            continue
        article = str(row.get("suggested_article") or "")
        fingerprint = str(row.get("historical_article_sha256") or "")
        version = row.get("selected_version") or {}
        if not article or not _valid_sha(fingerprint) or not version.get("url"):
            continue
        records.append({
            "law_name": k[0],
            "question_id": k[1],
            "exam_code": row.get("exam_code"),
            "article": article,
            "historical_version_checked": True,
            "verification_level": VERIFICATION_LEVEL,
            "verification_basis": VERIFICATION_BASIS,
            "selected_version": version,
            "historical_article_sha256": fingerprint,
            "historical_semantic": {
                "top_article": row.get("historical_top_article"),
                "top_score": row.get("historical_top_score"),
                "second_article": row.get("historical_second_article"),
                "second_score": row.get("historical_second_score"),
                "margin": row.get("historical_margin"),
                "decision_reason": row.get("historical_decision_reason"),
            },
            "official_history_url": p.get("official_history_url"),
            "exam_date_source_url": p.get("exam_date_source_url"),
        })
    return sorted(records, key=lambda row: key(row))


def build_registry(stage5: dict, stage6: dict, existing: dict | None = None) -> tuple[dict, list[dict]]:
    existing = existing or {}
    old = {key(row): dict(row) for row in (existing.get("records") or [])}
    fresh = {key(row): row for row in candidate_records(stage5, stage6)}
    conflicts: list[dict] = []

    for k, new in fresh.items():
        previous = old.get(k)
        if previous:
            changed = []
            if str(previous.get("article") or "") != str(new.get("article") or ""):
                changed.append("article")
            if str(previous.get("historical_article_sha256") or "") != str(new.get("historical_article_sha256") or ""):
                changed.append("historical_article_sha256")
            if changed:
                conflicts.append({
                    "law_name": k[0],
                    "question_id": k[1],
                    "changed_fields": changed,
                    "previous_article": previous.get("article"),
                    "fresh_article": new.get("article"),
                    "previous_sha256": previous.get("historical_article_sha256"),
                    "fresh_sha256": new.get("historical_article_sha256"),
                })
                continue
        old[k] = new

    rows = [old[k] for k in sorted(old)]
    registry = {
        "schema_version": 1,
        "scope": "priority10 historical-law verified metadata overlay",
        "method": (
            "Machine-verified historical-law metadata only; protected official "
            "question/answer/grading core is not modified. Registry is monotonic; "
            "evidence drift fails closed."
        ),
        "verified_record_count": len(rows),
        "historical_version_checked_count": sum(
            row.get("historical_version_checked") is True for row in rows
        ),
        "records": rows,
    }
    return registry, conflicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage5", default=str(DEFAULT_STAGE5))
    parser.add_argument("--stage6", default=str(DEFAULT_STAGE6))
    parser.add_argument("--existing", default=str(DEFAULT_EXISTING))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage5 = json.loads(Path(args.stage5).read_text(encoding="utf-8"))
    stage6 = json.loads(Path(args.stage6).read_text(encoding="utf-8"))
    existing_path = Path(args.existing)
    existing = (
        json.loads(existing_path.read_text(encoding="utf-8"))
        if existing_path.exists() else {}
    )
    registry, conflicts = build_registry(stage5, stage6, existing)
    if conflicts:
        print(json.dumps({"materialization_conflicts": conflicts}, ensure_ascii=False, indent=2))
        return 2

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verified_record_count": registry["verified_record_count"],
        "historical_version_checked_count": registry["historical_version_checked_count"],
        "fresh_confirmed_count": len(candidate_records(stage5, stage6)),
        "materialization_conflict_count": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
