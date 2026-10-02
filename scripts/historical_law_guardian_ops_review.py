#!/usr/bin/env python3
"""Convert historical-law Guardian routing output into durable review-item candidates.

This script is read-only with respect to the ledger. It emits candidate upserts
that a trusted backend may later persist through #269 review RPCs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TASK_ID = "historical-law-guardian-queue"
SKIP_LANES = {"machine_promotion"}


def stable_item_id(row: dict[str, Any]) -> str:
    lane = str(row.get("lane") or "").strip()
    law = str(row.get("law_name") or "").strip()
    question = str(row.get("question_id") or "").strip()
    if not lane or not law or not question:
        raise ValueError("guardian item requires lane, law_name, question_id")
    return f"historical-law:{lane}:{law}:{question}"


def build_candidates(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise ValueError("guardian queue must be schema_version=2")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("guardian queue items[] is required")

    out: list[dict[str, Any]] = []
    skipped = 0
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError("guardian item must be object")
        lane = str(raw.get("lane") or "").strip()
        if lane in SKIP_LANES:
            skipped += 1
            continue
        item_id = stable_item_id(raw)
        if item_id in seen:
            raise ValueError(f"duplicate durable review identity: {item_id}")
        seen.add(item_id)
        law = str(raw.get("law_name") or "").strip()
        question = str(raw.get("question_id") or "").strip()
        reason = str(raw.get("reason") or f"guardian_{lane}").strip()
        metadata = {
            "lane": lane,
            "priority": raw.get("priority"),
            "exam_code": raw.get("exam_code"),
            "human_review_required": bool(raw.get("human_review_required")),
            "stage3_route": raw.get("stage3_route"),
            "stage5_promotion_status": raw.get("stage5_promotion_status"),
            "stage6_status": raw.get("stage6_status"),
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}
        out.append({
            "item_id": item_id,
            "task_id": TASK_ID,
            "reason": reason,
            "source_ref": f"{law}|{question}",
            "metadata": metadata,
        })

    lane_counts: dict[str, int] = {}
    for row in out:
        lane = str(row["metadata"]["lane"])
        lane_counts[lane] = lane_counts.get(lane, 0) + 1

    return {
        "schema_version": 1,
        "source_schema_version": 2,
        "task_id": TASK_ID,
        "operation": "review_item_upsert_candidates",
        "write_authorized": False,
        "candidate_count": len(out),
        "skipped_machine_promotion": skipped,
        "lane_counts": dict(sorted(lane_counts.items())),
        "items": out,
    }


def self_test() -> dict[str, Any]:
    sample = {
        "schema_version": 2,
        "items": [
            {"law_name": "A法", "question_id": "q1", "lane": "human_review",
             "reason": "conflict", "priority": "high", "human_review_required": True},
            {"law_name": "B法", "question_id": "q2", "lane": "source_retry",
             "reason": "source_failure", "priority": "high"},
            {"law_name": "C法", "question_id": "q3", "lane": "machine_promotion",
             "reason": "confirmed"},
        ],
    }
    out = build_candidates(sample)
    assert out["candidate_count"] == 2
    assert out["skipped_machine_promotion"] == 1
    assert out["items"][0]["item_id"] == "historical-law:human_review:A法:q1"
    try:
        build_candidates({"schema_version": 2, "items": [sample["items"][0], sample["items"][0]]})
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate durable review identity must fail closed")
    return {"ok": True, "candidate_count": 2, "machine_promotion_skipped": True, "duplicate_fail_closed": True}


def main() -> int:
    p = argparse.ArgumentParser(description="Build #269 durable review candidates from Guardian routing")
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.input:
        raise SystemExit("--input is required unless --self-test is used")
    result = build_candidates(json.loads(args.input.read_text(encoding="utf-8")))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
