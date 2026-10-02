#!/usr/bin/env python3
"""Plan durable Guardian review reconciliation without writing the ledger.

The current Guardian queue is authoritative only for routing. This planner
compares it with existing open durable review rows and produces explicit
upsert/resolve/supersede actions. It never deletes history and never mutates
Official Core.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from historical_law_guardian_ops_review import (
    SKIP_LANES,
    TASK_ID,
    build_candidates,
    stable_item_id,
)


def source_ref(row: dict[str, Any]) -> str:
    law = str(row.get("law_name") or "").strip()
    question = str(row.get("question_id") or "").strip()
    if not law or not question:
        raise ValueError("Guardian row requires law_name and question_id")
    return f"{law}|{question}"


def build_reconciliation(queue: Any, open_reviews: Any) -> dict[str, Any]:
    if not isinstance(queue, dict) or queue.get("schema_version") != 2:
        raise ValueError("Guardian queue must be schema_version=2")
    current_items = queue.get("items")
    if not isinstance(current_items, list):
        raise ValueError("Guardian queue items[] is required")
    if not isinstance(open_reviews, list):
        raise ValueError("open_reviews must be a list")

    current_by_source: dict[str, dict[str, Any]] = {}
    for raw in current_items:
        if not isinstance(raw, dict):
            raise ValueError("Guardian item must be an object")
        ref = source_ref(raw)
        if ref in current_by_source:
            raise ValueError(f"duplicate Guardian source identity: {ref}")
        current_by_source[ref] = raw

    candidate_payload = build_candidates(queue)
    current_candidates = candidate_payload["items"]
    candidate_by_id = {str(row["item_id"]): row for row in current_candidates}

    actions: list[dict[str, Any]] = []
    for row in current_candidates:
        actions.append(
            {
                "action": "review_upsert",
                "task_id": TASK_ID,
                "item_id": row["item_id"],
                "reason": row["reason"],
                "source_ref": row["source_ref"],
                "metadata": row.get("metadata") or {},
            }
        )

    untouched_open: list[str] = []
    seen_open_ids: set[str] = set()
    for raw in open_reviews:
        if not isinstance(raw, dict):
            raise ValueError("open review row must be an object")
        item_id = str(raw.get("item_id") or "").strip()
        task_id = str(raw.get("task_id") or "").strip()
        state = str(raw.get("state") or "open").strip()
        ref = str(raw.get("source_ref") or "").strip()
        if not item_id or item_id in seen_open_ids:
            raise ValueError(f"open review item id missing or duplicated: {item_id!r}")
        seen_open_ids.add(item_id)
        if task_id and task_id != TASK_ID:
            continue
        if state != "open":
            raise ValueError(f"open_reviews contains non-open row: {item_id}")
        if not item_id.startswith("historical-law:"):
            raise ValueError(f"Guardian review item outside namespace: {item_id}")
        if not ref:
            raise ValueError(f"Guardian open review lacks source_ref: {item_id}")

        current = current_by_source.get(ref)
        if current is None:
            # Disappearance is not enough evidence to auto-resolve. Preserve debt.
            untouched_open.append(item_id)
            continue

        lane = str(current.get("lane") or "").strip()
        if lane in SKIP_LANES:
            actions.append(
                {
                    "action": "review_resolve",
                    "task_id": TASK_ID,
                    "item_id": item_id,
                    "final_state": "resolved",
                    "resolution": (
                        f"Guardian routing advanced {ref} to {lane}; "
                        "durable review debt closed without changing Official Core."
                    ),
                }
            )
            continue

        expected_id = stable_item_id(current)
        if item_id != expected_id:
            actions.append(
                {
                    "action": "review_resolve",
                    "task_id": TASK_ID,
                    "item_id": item_id,
                    "final_state": "superseded",
                    "resolution": (
                        f"Guardian routing changed lane for {ref} to {lane}; "
                        f"superseded by {expected_id}."
                    ),
                }
            )
        elif item_id not in candidate_by_id:
            raise ValueError(f"current unresolved Guardian item missing candidate: {item_id}")

    action_ids: set[tuple[str, str]] = set()
    for action in actions:
        key = (str(action["action"]), str(action["item_id"]))
        if key in action_ids:
            # Same item must never receive the same action twice in one plan.
            raise ValueError(f"duplicate reconciliation action: {key}")
        action_ids.add(key)

    counts: dict[str, int] = {}
    for action in actions:
        name = str(action["action"])
        counts[name] = counts.get(name, 0) + 1

    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "write_authorized": False,
        "current_source_count": len(current_by_source),
        "candidate_count": len(current_candidates),
        "open_input_count": len(open_reviews),
        "untouched_open_count": len(untouched_open),
        "untouched_open_item_ids": sorted(untouched_open),
        "action_counts": dict(sorted(counts.items())),
        "actions": actions,
    }


def self_test() -> dict[str, Any]:
    queue = {
        "schema_version": 2,
        "items": [
            {
                "law_name": "A法",
                "question_id": "q1",
                "lane": "human_review",
                "reason": "semantic_conflict",
                "priority": "high",
                "human_review_required": True,
            },
            {
                "law_name": "B法",
                "question_id": "q2",
                "lane": "machine_promotion",
                "reason": "confirmed",
                "priority": "normal",
            },
        ],
    }
    open_reviews = [
        {
            "item_id": "historical-law:source_retry:A法:q1",
            "task_id": TASK_ID,
            "source_ref": "A法|q1",
            "state": "open",
        },
        {
            "item_id": "historical-law:human_review:B法:q2",
            "task_id": TASK_ID,
            "source_ref": "B法|q2",
            "state": "open",
        },
        {
            "item_id": "historical-law:source_retry:C法:q3",
            "task_id": TASK_ID,
            "source_ref": "C法|q3",
            "state": "open",
        },
    ]
    out = build_reconciliation(queue, open_reviews)
    assert out["candidate_count"] == 1
    assert out["untouched_open_count"] == 1
    actions = out["actions"]
    assert any(
        row["action"] == "review_upsert"
        and row["item_id"] == "historical-law:human_review:A法:q1"
        for row in actions
    )
    assert any(
        row["action"] == "review_resolve"
        and row["item_id"] == "historical-law:source_retry:A法:q1"
        and row["final_state"] == "superseded"
        for row in actions
    )
    assert any(
        row["action"] == "review_resolve"
        and row["item_id"] == "historical-law:human_review:B法:q2"
        and row["final_state"] == "resolved"
        for row in actions
    )
    return {
        "ok": True,
        "lane_change_supersedes": True,
        "machine_promotion_resolves": True,
        "disappearance_preserves_debt": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan Guardian durable review reconciliation")
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--open-reviews", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.queue or not args.open_reviews:
        raise SystemExit("--queue and --open-reviews are required unless --self-test is used")

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    open_reviews = json.loads(args.open_reviews.read_text(encoding="utf-8"))
    result = build_reconciliation(queue, open_reviews)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
