#!/usr/bin/env python3
"""Read-only aggregate triage of historical SWSI AI-analysis review records.

Not a queue reactivator, model evaluator or source-verification engine.
Never changes Official Core, AI enrichment, status or scheduler.
Only aggregate counts are reported; raw errors and question IDs stay local.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_YEARS = tuple(str(y) for y in range(104, 116))
SUBJECTS = frozenset((
    "社會工作", "社會工作直接服務", "社會政策與社會立法",
    "人類行為與社會環境", "社會工作研究方法",
))
ROUNDS = frozenset(("第一次", "第二次"))
FIELDS = ("id", "year", "round", "subject", "qno", "analysis_status",
          "analysis_error", "grading_mode", "accepted_answers", "answer")
STATUS = frozenset(("ready", "review", "pending", "analyzing"))
GRADING = frozenset(("standard", "all_credit", "any_answer"))
CATEGORY_KEYS = (
    "legacy_http_405_single_answer", "missing_reason_single_answer",
    "other_manual_single_answer", "multi_answer_requires_separate_review",
    "special_grading_requires_separate_review",
)
OLD_HTTP_405_PREFIX = "AI qwen/qwen3.6-27b HTTP 405"


def validate_scope(rows: Any) -> None:
    if not isinstance(rows, list) or len(rows) != 4800:
        raise ValueError("historical query requires exactly 4800 public MCQ rows")
    identities: set[str] = set()
    groups: dict[tuple[str, str, str], set[int]] = {}
    for row in rows:
        if not isinstance(row, dict) or any(field not in row for field in FIELDS):
            raise ValueError("review audit input row is malformed or incomplete")
        ident = row["id"]
        if not isinstance(ident, str) or not ident or ident in identities:
            raise ValueError("missing/duplicate question ID in historical review audit")
        identities.add(ident)
        group = (str(row["year"]), str(row["round"]), str(row["subject"]))
        if group[0] not in HISTORICAL_YEARS or group[1] not in ROUNDS or group[2] not in SUBJECTS:
            raise ValueError("unexpected historic year/round/subject in review audit")
        try:
            qno = int(str(row["qno"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("historical question number is invalid") from exc
        numbers = groups.setdefault(group, set())
        if qno in numbers or qno not in range(1, 41):
            raise ValueError("historical exam has duplicate/invalid question number")
        numbers.add(qno)
        if row["analysis_status"] not in STATUS or row["grading_mode"] not in GRADING:
            raise ValueError("unknown analysis status or grading mode: refuse review classification")
        accepted = row["accepted_answers"]
        if accepted is not None and (
            not isinstance(accepted, list)
            or any(x not in ("A", "B", "C", "D") for x in accepted)
            or len(accepted) != len(set(accepted))
        ):
            raise ValueError("invalid accepted_answers contract")
        if row["answer"] not in ("A", "B", "C", "D"):
            raise ValueError("invalid official answer contract")
        if row["grading_mode"] == "standard" and accepted and row["answer"] not in accepted:
            raise ValueError("standard grading conflicts with accepted answer set")
        if row["analysis_error"] is not None and not isinstance(row["analysis_error"], str):
            raise ValueError("invalid analysis error type")
    expected = {(y, r, s) for y in HISTORICAL_YEARS for r in ROUNDS for s in SUBJECTS}
    if set(groups) != expected or any(nums != set(range(1, 41)) for nums in groups.values()):
        raise ValueError("historical review audit missing a paper or question number")


def review_category(row: dict[str, Any]) -> str:
    if row["analysis_status"] != "review":
        raise ValueError("only review rows may be categorized")
    if row["grading_mode"] != "standard":
        return "special_grading_requires_separate_review"
    if len(row["accepted_answers"] or []) > 1:
        return "multi_answer_requires_separate_review"
    error = (row["analysis_error"] or "").strip()
    if error.startswith(OLD_HTTP_405_PREFIX):
        return "legacy_http_405_single_answer"
    if not error:
        return "missing_reason_single_answer"
    return "other_manual_single_answer"


def audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    validate_scope(rows)
    statuses = Counter(r["analysis_status"] for r in rows)
    categories = Counter(review_category(r) for r in rows if r["analysis_status"] == "review")
    if sum(categories.values()) != statuses["review"]:
        raise ValueError("unclassified review rows")
    return {
        "schema_version": 1,
        "scope": "ROC104-115_4800_public_mcq_only",
        "total_historical_mcq": len(rows),
        "exam_sessions": 24,
        "subject_papers": 120,
        "analysis_status": {s: statuses[s] for s in ("ready", "review", "pending", "analyzing")},
        "review_categories": {key: categories[key] for key in CATEGORY_KEYS},
        "legacy_http_405_is_historical_annotation": True,
        "ready_means_human_verified": False,
        "official_pdf_review_signals_counted": False,
        "automatic_change": False,
        "bulk_requeue_allowed": False,
        "release_approval": False,
    }


def fetch_public_historical_rows() -> list[dict[str, Any]]:
    """Explicit GET-only public anon API; no service-role, writes or retries."""
    import requests
    from build_question_shards import frontend_config

    base, anon_key = frontend_config()
    headers = {
        "apikey": anon_key, "Authorization": "Bearer " + anon_key,
        "Accept": "application/json", "User-Agent": "SWSI-AI-Review-Triage-ReadOnly/1.0",
    }
    rows: list[dict[str, Any]] = []
    for offset in range(0, 4800, 1000):
        response = requests.get(
            base + "/rest/v1/questions", headers=headers,
            params={
                "select": ",".join(FIELDS),
                "year": "in.(" + ",".join(HISTORICAL_YEARS) + ")",
                "order": "year.asc,round.asc,subject.asc,qno.asc,id.asc",
                "offset": str(offset), "limit": "1000",
            }, timeout=45,
        )
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            raise ValueError("Supabase response must be a JSON array")
        rows.extend(batch)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", action="store_true", help="public anon GET-only read")
    source.add_argument("--input", type=Path, help="offline minimum-field JSON fixture")
    parser.add_argument("--out", type=Path, help="write counts only, outside repository")
    args = parser.parse_args()
    rows = fetch_public_historical_rows() if args.live else json.loads(args.input.read_text(encoding="utf-8"))
    report = audit(rows)
    if args.out:
        destination = args.out.resolve()
        if destination == ROOT or ROOT in destination.parents:
            raise ValueError("refusing to write review report inside repository")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
