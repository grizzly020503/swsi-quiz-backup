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

from analyze_current_affairs_signals import (
    analyze_item,
    build_exam_point_summary,
    confidence_for,
    essay_direction_for,
    historical_exam_stats,
    load_questions_csv,
    match_questions,
    mcq_focus_for,
    text_of,
)
from current_affairs_law_links import infer_current_affairs_links


PUBLIC_RELATED_MATCH_MIN_SCORE = 2.0


def confidence_score(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(value, 0)


def _student_visible_related(matches: list[dict]) -> list[dict]:
    """Keep only concept-or-stronger historical evidence for public output.

    Vignette-only/background matches remain available inside the analyzer for
    audit, but they must not inflate student-facing historical counts or lists.
    """
    visible = []
    for match in matches:
        try:
            score = float(match.get("match_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if score >= PUBLIC_RELATED_MATCH_MIN_SCORE:
            visible.append(match)
    return visible


def load_questions_shards(path: Path) -> list[dict]:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Question shard manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for shard in manifest.get("shards") or []:
        name = shard.get("file")
        if not name:
            continue
        shard_path = path / str(name)
        if not shard_path.exists():
            raise SystemExit(f"Question shard missing: {shard_path}")
        payload = json.loads(shard_path.read_text(encoding="utf-8"))
        for row in payload.get("questions") or []:
            if isinstance(row, dict) and row.get("id"):
                rows.append(row)
    expected = int(manifest.get("total_questions") or 0)
    if expected and len(rows) != expected:
        raise SystemExit(f"Question shard count mismatch: manifest={expected}, loaded={len(rows)}")
    return rows


def analyze_item_with_law_links(row: dict, questions: list[dict], max_related: int = 5) -> dict:
    """Apply the base analyzer, then the stricter law/policy linkage layer.

    When a high-confidence inferred law is added, recompute historical matching
    and student-facing summaries with that law. ``match_questions`` still
    requires event-supported topic evidence, so a shared law alone cannot pull
    unrelated historical questions into the event.

    Low-score vignette/background matches are kept by the base analyzer for
    internal audit, but are filtered out of the public snapshot here.
    """
    out = analyze_item(row, questions, max_related=max_related)
    linkage = infer_current_affairs_links(out)
    old_laws = [str(x) for x in (out.get("related_laws") or []) if str(x)]
    laws = [str(x) for x in (linkage.get("related_laws") or []) if str(x)]

    if laws != old_laws:
        all_related = match_questions(
            out,
            laws,
            questions,
            max_hits=max(1, len(questions)) if questions else 1,
        )
        policy = str(out.get("policy_signal") or "low")
        essay = str(out.get("essay_value") or "low")
        mcq = str(out.get("mcq_fact_density") or "low")
        text = text_of(out)
        out.update(
            {
                "related_laws": laws,
                "related_exam_questions": all_related[: max(1, max_related)],
                "historical_exam_stats": historical_exam_stats(all_related, questions, laws),
                "exam_point_summary": build_exam_point_summary(out, laws, policy, essay, mcq),
                "essay_direction": essay_direction_for(out, laws),
                "mcq_focus": mcq_focus_for(out, text, laws),
                "signal_confidence": confidence_for(policy, essay, mcq, laws, len(all_related)),
            }
        )

    out.update(linkage)

    # Recompute the final historical surface after linkage. Internal matcher
    # results below concept-level remain useful for audits, but student-facing
    # related questions and counts must use the same evidence threshold.
    final_laws = [str(x) for x in (out.get("related_laws") or []) if str(x)]
    all_related = match_questions(
        out,
        final_laws,
        questions,
        max_hits=max(1, len(questions)) if questions else 1,
    )
    public_related = _student_visible_related(all_related)
    policy = str(out.get("policy_signal") or "low")
    essay = str(out.get("essay_value") or "low")
    mcq = str(out.get("mcq_fact_density") or "low")
    out.update(
        {
            "related_exam_questions": public_related[: max(1, max_related)],
            "historical_exam_stats": historical_exam_stats(public_related, questions, final_laws),
            "signal_confidence": confidence_for(
                policy,
                essay,
                mcq,
                final_laws,
                len(public_related),
            ),
        }
    )
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(root / "auto" / "current_affairs.json"))
    ap.add_argument("--questions-shards-dir", default=str(root / "cdn" / "question-shards"))
    ap.add_argument("--questions-csv", default="")
    ap.add_argument("--output", default=str(root / "auto" / "current_affairs_signals.json"))
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    src_path = Path(args.input)
    q_path = Path(args.questions_shards_dir)
    csv_path = Path(args.questions_csv) if args.questions_csv else None
    if not src_path.exists():
        raise SystemExit(f"Input not found: {src_path}")
    if not q_path.exists() and (csv_path is None or not csv_path.exists()):
        raise SystemExit(f"Question source not found: {q_path}")

    src = json.loads(src_path.read_text(encoding="utf-8"))
    items = src.get("items") or []
    if not isinstance(items, list):
        raise SystemExit("Input items must be a list")

    questions = load_questions_shards(q_path) if q_path.exists() else load_questions_csv(csv_path)
    analyzed = [
        analyze_item_with_law_links(row, questions, max_related=5)
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
                "knowledge_root": row.get("knowledge_root"),
                "knowledge_model": row.get("knowledge_model"),
                "management_domains": row.get("management_domains") or [],
                "exam_subject_axes": row.get("exam_subject_axes") or [],
                "primary_exam_subject_axes": row.get("primary_exam_subject_axes") or [],
                "supporting_exam_subject_axes": row.get("supporting_exam_subject_axes") or [],
                "subject_topics": row.get("subject_topics") or {},
                "knowledge_topics": row.get("knowledge_topics") or [],
                "knowledge_paths": row.get("knowledge_paths") or [],
                "policy_signal": row.get("policy_signal"),
                "essay_value": row.get("essay_value"),
                "mcq_fact_density": row.get("mcq_fact_density"),
                "signal_confidence": row.get("signal_confidence"),
                "signal_score": row.get("signal_score"),
                "exam_point_summary": row.get("exam_point_summary"),
                "essay_direction": row.get("essay_direction"),
                "mcq_focus": row.get("mcq_focus") or [],
                "related_laws": row.get("related_laws") or [],
                "related_policy_instruments": row.get("related_policy_instruments") or [],
                "law_link_status": row.get("law_link_status"),
                "law_link_note": row.get("law_link_note"),
                "law_link_basis": row.get("law_link_basis") or [],
                "law_link_rules_schema": row.get("law_link_rules_schema"),
                "related_exam_questions": row.get("related_exam_questions") or [],
                "historical_exam_stats": row.get("historical_exam_stats") or {},
            }
        )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "item_count": len(public_items),
        "questions_loaded": len(questions),
        "question_source": "cdn/question-shards" if q_path.exists() else "csv",
        "law_link_rules_schema": 1,
        "note": (
            "SWSI 命題訊號快照；用於複習方向，不代表命題保證。"
            "法規連結可由高精度規則推論；相關法規不等於本事件發生修法。"
        ),
        "items": public_items,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Current-affairs exam-signal snapshot: {len(public_items)} items, questions={len(questions)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
