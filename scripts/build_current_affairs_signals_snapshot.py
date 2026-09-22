#!/usr/bin/env python3
"""Build the public current-affairs exam-signal snapshot for SWSI Issue #74.

The public snapshot contains SWSI-authored exam analysis and references to
historical question IDs/metadata only. It never publishes the private question
bank source path or full question text.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from analyze_current_affairs_signals import load_questions_csv, analyze_item


def confidence_score(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(value, 0)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(root / "auto" / "current_affairs.json"))
    ap.add_argument("--questions-csv", default=str(root / "data" / "questions_master_backup_20260824_2220.csv"))
    ap.add_argument("--output", default=str(root / "auto" / "current_affairs_signals.json"))
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    src_path = Path(args.input)
    q_path = Path(args.questions_csv)
    if not src_path.exists():
        raise SystemExit(f"Input not found: {src_path}")
    if not q_path.exists():
        raise SystemExit(f"Questions CSV not found: {q_path}")

    src = json.loads(src_path.read_text(encoding="utf-8"))
    items = src.get("items") or []
    if not isinstance(items, list):
        raise SystemExit("Input items must be a list")

    questions = load_questions_csv(q_path)
    analyzed = [
        analyze_item(row, questions, max_related=5)
        for row in items
        if isinstance(row, dict)
    ]

    for row in analyzed:
        score = (
            confidence_score(row.get("policy_signal", "low"))
            + confidence_score(row.get("essay_value", "low"))
            + confidence_score(row.get("mcq_fact_density", "low"))
            + (1 if row.get("related_laws") else 0)
            + (1 if len(row.get("related_exam_questions") or []) >= 1 else 0)
        )
        row["signal_score"] = min(10, score)

    analyzed.sort(
        key=lambda row: (
            -int(row.get("signal_score") or 0),
            -int(row.get("relevance_score") or 0),
            str(row.get("published_at") or ""),
        )
    )

    public_items = []
    for row in analyzed[: max(1, args.limit)]:
        public_items.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "summary": str(row.get("summary") or "")[:280],
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "published_at": row.get("published_at"),
                "region": row.get("region"),
                "category": row.get("category"),
                "relevance_score": row.get("relevance_score"),
                "exam_tags": row.get("exam_tags") or [],
                "subjects": row.get("subjects") or [],
                "policy_signal": row.get("policy_signal"),
                "essay_value": row.get("essay_value"),
                "mcq_fact_density": row.get("mcq_fact_density"),
                "signal_confidence": row.get("signal_confidence"),
                "signal_score": row.get("signal_score"),
                "exam_point_summary": row.get("exam_point_summary"),
                "essay_direction": row.get("essay_direction"),
                "mcq_focus": row.get("mcq_focus") or [],
                "related_laws": row.get("related_laws") or [],
                "related_exam_questions": row.get("related_exam_questions") or [],
            }
        )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "item_count": len(public_items),
        "questions_loaded": len(questions),
        "note": "SWSI 命題訊號快照；用於複習方向，不代表命題保證。",
        "items": public_items,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Current-affairs exam-signal snapshot: {len(public_items)} items, questions={len(questions)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
