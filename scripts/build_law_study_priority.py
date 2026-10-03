#!/usr/bin/env python3
"""Build evidence-backed law study-priority data.

Counts come only from the existing priority-law linkage registry, whose contract is
exact law metadata name or explicit alias. They are *linked-question counts*, not
predictions, not keyword frequency, and not historical-law verification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "law_question_links_priority10.v1.json"


def _year(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def build_snapshot(source_path: Path) -> dict:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    cards = source.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("priority-law linkage registry must contain non-empty cards")

    all_years: list[int] = []
    for card in cards:
        for question in card.get("questions") or []:
            y = _year(question.get("year"))
            if y:
                all_years.append(y)
    if not all_years:
        raise ValueError("priority-law linkage registry has no usable question years")

    latest_year = max(all_years)
    recent_start = latest_year - 4
    laws: list[dict] = []
    all_linked_ids: set[str] = set()
    total_pairs = 0

    for card in cards:
        law_name = str(card.get("law_name") or "").strip()
        if not law_name:
            raise ValueError("priority-law card missing law_name")

        by_id: dict[str, dict] = {}
        for raw in card.get("questions") or []:
            qid = str(raw.get("question_id") or "").strip()
            if not qid:
                raise ValueError(f"{law_name}: linked question missing question_id")
            if qid in by_id:
                continue
            by_id[qid] = raw

        questions = sorted(
            by_id.values(),
            key=lambda q: (_year(q.get("year")), str(q.get("exam_code") or ""), str(q.get("question_id") or "")),
            reverse=True,
        )
        recent = [q for q in questions if _year(q.get("year")) >= recent_start]
        all_linked_ids.update(by_id)
        total_pairs += len(questions)

        laws.append(
            {
                "law_name": law_name,
                "all_linked_question_count": len(questions),
                "recent_five_year_question_count": len(recent),
                "question_ids": [str(q.get("question_id")) for q in questions],
                "recent_question_ids": [str(q.get("question_id")) for q in recent],
                "recent_exam_codes": sorted({str(q.get("exam_code") or "") for q in recent if q.get("exam_code")}, reverse=True),
            }
        )

    laws.sort(key=lambda x: (-x["recent_five_year_question_count"], -x["all_linked_question_count"], x["law_name"]))

    return {
        "schema_version": 1,
        "source": "data/law_question_links_priority10.v1.json",
        "source_method": str(source.get("method") or "").strip(),
        "scope": {
            "first_exam_year": min(all_years),
            "latest_exam_year": latest_year,
            "recent_start_year": recent_start,
            "recent_end_year": latest_year,
            "recent_label": f"近五年（{recent_start}–{latest_year}）",
            "priority_law_count": len(laws),
            "linked_law_question_pairs": total_pairs,
            "unique_linked_questions": len(all_linked_ids),
        },
        "student_boundary": "題數只計題庫中明確法規 metadata／既有明示 alias 的唯一題目；不是關鍵字命中、不是命題機率，也不代表每題歷史法規版本已核實。",
        "laws": laws,
    }


def build_runtime_payload(snapshot: dict) -> dict:
    """Return only fields needed by the browser UI; no runtime fetch is required."""
    scope = snapshot.get("scope") or {}
    runtime_laws: dict[str, dict] = {}
    for law in snapshot.get("laws") or []:
        name = str(law.get("law_name") or "").strip()
        if not name or name in runtime_laws:
            raise ValueError("runtime payload requires unique non-empty law names")
        runtime_laws[name] = {
            "all": int(law.get("all_linked_question_count") or 0),
            "recent": int(law.get("recent_five_year_question_count") or 0),
            "question_ids": list(law.get("question_ids") or []),
            "recent_exam_codes": list(law.get("recent_exam_codes") or []),
        }
    return {
        "schema_version": 1,
        "scope": {
            "first_exam_year": int(scope.get("first_exam_year") or 0),
            "latest_exam_year": int(scope.get("latest_exam_year") or 0),
            "recent_start_year": int(scope.get("recent_start_year") or 0),
            "recent_end_year": int(scope.get("recent_end_year") or 0),
            "recent_label": str(scope.get("recent_label") or ""),
        },
        "student_boundary": str(snapshot.get("student_boundary") or ""),
        "laws": runtime_laws,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--runtime-output", type=Path)
    ap.add_argument("--print", action="store_true", dest="print_json")
    args = ap.parse_args()

    snapshot = build_snapshot(args.source)
    rendered = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.runtime_output:
        args.runtime_output.parent.mkdir(parents=True, exist_ok=True)
        args.runtime_output.write_text(
            json.dumps(build_runtime_payload(snapshot), ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    if args.print_json or (not args.output and not args.runtime_output):
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())