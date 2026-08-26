#!/usr/bin/env python3
"""Unified intake QA for SWSI multiple-choice and essay exam data.

This script does NOT deploy or modify student-facing files.

Design goals:
- Official Core and SWSI enrichment are evaluated separately.
- Normal official questions should auto-pass without manual review.
- Missing analysis is a generation backlog, NOT a human-review backlog.
- Special grading fails closed; never infer grading_mode from answer text or IDs.
- Legal/policy risk can be satisfied by an explicitly trusted fresh legal-watch
  snapshot for the CURRENT intake session only; historical exams still require
  historical-version QA.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "data" / "question_qa_policy_v1.json"

STATUS_RANK = {"passed": 0, "needs_review": 1, "blocked": 2}
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
READY_ANALYSIS_STATES = {"ready", "done", "reviewed", "verified", "complete"}
CHECKED_LEGAL_STATES = {"current", "checked", "verified", "historical_checked"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canon_round(value: Any, policy: dict) -> str:
    raw = str(value or "").strip()
    return str(policy.get("round_aliases", {}).get(raw, raw))


def qno_int(value: Any) -> int | None:
    raw = str(value or "").strip()
    return int(raw) if raw.isdigit() else None


def add_issue(
    issues: list[dict],
    *,
    layer: str,
    rule: str,
    status: str,
    risk: str,
    message: str,
) -> None:
    issues.append(
        {
            "layer": layer,
            "rule": rule,
            "status": status,
            "risk": risk,
            "message": message,
        }
    )


def worst_status(issues: list[dict], layer: str | None = None) -> str:
    relevant = [x for x in issues if layer is None or x.get("layer") == layer]
    if not relevant:
        return "passed"
    return max(
        (str(x.get("status", "passed")) for x in relevant),
        key=lambda x: STATUS_RANK.get(x, -1),
    )


def worst_risk(issues: list[dict], layer: str | None = None) -> str:
    relevant = [x for x in issues if layer is None or x.get("layer") == layer]
    if not relevant:
        return "low"
    return max(
        (str(x.get("risk", "low")) for x in relevant),
        key=lambda x: RISK_RANK.get(x, -1),
    )


def text_matches(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.I):
                hits.append(pattern)
        except re.error:
            if pattern in text:
                hits.append(pattern)
    return hits


def normalize_mcq_payload(payload: Any) -> list[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        return payload["questions"]
    if isinstance(payload, list):
        return payload
    raise ValueError("MCQ JSON must be a shard object with questions[] or a list")


def normalize_essay_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("essays"), list):
        return payload["essays"]
    raise ValueError("Essay JSON must be a list or an object with essays[]")


def filter_session(rows: list[dict], year: str, round_name: str, policy: dict) -> list[dict]:
    return [
        row
        for row in rows
        if str(row.get("year") or "").strip() == year
        and canon_round(row.get("round"), policy) == round_name
    ]


def load_legal_watch(path: Path | None) -> dict | None:
    if path is None:
        return None
    raw = read_json(path)
    records = raw.get("records") if isinstance(raw, dict) else None
    if not isinstance(records, list):
        raise ValueError("legal watch JSON must contain records[]")
    by_name: dict[str, dict] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("canonical_name") or "").strip()
        if name:
            by_name[name] = rec
    return {
        "checked_at": str(raw.get("checked_at") or ""),
        "lookup_error_count": int(raw.get("lookup_error_count") or 0),
        "missing_count": int(raw.get("missing_count") or 0),
        "records": by_name,
    }


def canonical_law_matches(text: str, legal_watch: dict | None) -> list[str]:
    if not legal_watch:
        return []
    return sorted(name for name in legal_watch.get("records", {}) if name and name in text)


def legal_watch_clears_current_review(
    names: list[str],
    legal_watch: dict | None,
    trust_current_legal_watch: bool,
) -> bool:
    """Return true only for explicit current-intake opt-in.

    This MUST NOT be used as historical-law-version proof.  The caller has to
    explicitly pass --trust-current-legal-watch for a newly published/current
    exam session.
    """
    if not trust_current_legal_watch or not legal_watch or not names:
        return False
    if legal_watch.get("lookup_error_count", 0) != 0:
        return False
    records = legal_watch.get("records", {})
    for name in names:
        rec = records.get(name) or {}
        if rec.get("found") is not True:
            return False
        if rec.get("changed") is True:
            return False
    return True


def official_core_record(row: dict, kind: str, issues: list[dict]) -> dict:
    return {
        "id": str(row.get("id") or ""),
        "kind": kind,
        "subject": str(row.get("subject") or ""),
        "year": str(row.get("year") or ""),
        "round": str(row.get("round") or ""),
        "qno": str(row.get("qno") or ""),
        "official_status": worst_status(issues, "official_core"),
        "official_risk": worst_risk(issues, "official_core"),
        "enrichment_status": worst_status(issues, "enrichment"),
        "enrichment_risk": worst_risk(issues, "enrichment"),
        "issues": issues,
    }


def validate_mcq(
    rows: list[dict],
    year: str,
    round_name: str,
    policy: dict,
    legal_watch: dict | None = None,
    trust_current_legal_watch: bool = False,
) -> tuple[list[dict], list[dict]]:
    cfg = policy["mcq"]
    subjects = set(policy["subjects"])
    valid_modes = set(cfg["valid_grading_modes"])
    letters = set(cfg["valid_answer_letters"])
    special_marker = str(cfg["special_answer_marker"])
    session_issues: list[dict] = []
    results: list[dict] = []

    expected_total = int(cfg["expected_total"])
    if len(rows) != expected_total:
        add_issue(
            session_issues,
            layer="official_core",
            rule="MCQ_SESSION_COUNT",
            status="blocked",
            risk="critical",
            message=f"expected {expected_total} MCQs, got {len(rows)}",
        )

    ids = [str(r.get("id") or "") for r in rows]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        add_issue(
            session_issues,
            layer="official_core",
            rule="MCQ_ID_UNIQUE",
            status="blocked",
            risk="critical",
            message="missing or duplicated MCQ IDs",
        )

    counts = Counter(str(r.get("subject") or "") for r in rows)
    expected_per_subject = int(cfg["expected_per_subject"])
    if set(counts) != subjects or any(counts.get(s, 0) != expected_per_subject for s in subjects):
        add_issue(
            session_issues,
            layer="official_core",
            rule="MCQ_SUBJECT_DISTRIBUTION",
            status="blocked",
            risk="critical",
            message=f"subject distribution invalid: {dict(counts)}",
        )

    by_subject: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        n = qno_int(row.get("qno"))
        if n is not None:
            by_subject[str(row.get("subject") or "")].add(n)
    expected_qnos = set(range(int(cfg["qno_min"]), int(cfg["qno_max"]) + 1))
    for subject in subjects:
        if by_subject.get(subject, set()) != expected_qnos:
            add_issue(
                session_issues,
                layer="official_core",
                rule="MCQ_QNO_COVERAGE",
                status="blocked",
                risk="critical",
                message=f"{subject}: qno set is not {min(expected_qnos)}..{max(expected_qnos)}",
            )

    legal_patterns = list(policy.get("risk_signals", {}).get("legal_or_policy_high", []))

    for row in rows:
        issues: list[dict] = []
        item_id = str(row.get("id") or "")
        subject = str(row.get("subject") or "").strip()
        row_year = str(row.get("year") or "").strip()
        row_round = canon_round(row.get("round"), policy)
        n = qno_int(row.get("qno"))
        question = str(row.get("question") or row.get("q") or "").strip()

        if not item_id:
            add_issue(issues, layer="official_core", rule="MCQ_ID_REQUIRED", status="blocked", risk="critical", message="id missing")
        if subject not in subjects:
            add_issue(issues, layer="official_core", rule="MCQ_SUBJECT_VALID", status="blocked", risk="critical", message=f"invalid subject: {subject!r}")
        if row_year != year or row_round != round_name:
            add_issue(issues, layer="official_core", rule="MCQ_SESSION_MATCH", status="blocked", risk="critical", message=f"row belongs to {row_year}-{row_round}")
        if n is None or not (int(cfg["qno_min"]) <= n <= int(cfg["qno_max"])):
            add_issue(issues, layer="official_core", rule="MCQ_QNO_VALID", status="blocked", risk="critical", message=f"invalid qno: {row.get('qno')!r}")
        if not question:
            add_issue(issues, layer="official_core", rule="MCQ_QUESTION_REQUIRED", status="blocked", risk="critical", message="question text missing")

        for letter, field in (("A", "opt_a"), ("B", "opt_b"), ("C", "opt_c"), ("D", "opt_d")):
            value = row.get(field)
            if value is None:
                value = row.get(letter)
            if not str(value or "").strip():
                add_issue(issues, layer="official_core", rule="MCQ_OPTION_REQUIRED", status="blocked", risk="critical", message=f"option {letter} missing")

        if not str(row.get("source_exam_code") or "").strip():
            add_issue(issues, layer="official_core", rule="MCQ_SOURCE_REQUIRED", status="needs_review", risk="high", message="source_exam_code missing")

        mode = str(row.get("grading_mode") or "").strip()
        answer = str(row.get("answer") or "").strip().upper()
        accepted = row.get("accepted_answers")

        if not mode:
            add_issue(issues, layer="official_core", rule="MCQ_GRADING_MODE_EXPLICIT", status="blocked", risk="critical", message="grading_mode missing; fail closed")
        elif mode not in valid_modes:
            add_issue(issues, layer="official_core", rule="MCQ_GRADING_MODE_VALID", status="blocked", risk="critical", message=f"invalid grading_mode: {mode!r}")

        if special_marker in str(row.get("answer") or "") and mode not in {"all_credit", "any_answer"}:
            add_issue(issues, layer="official_core", rule="MCQ_SPECIAL_GRADING_EXPLICIT", status="blocked", risk="critical", message="special answer marker present without explicit special grading_mode")

        if mode == "standard":
            if answer not in letters:
                add_issue(issues, layer="official_core", rule="MCQ_STANDARD_ANSWER_VALID", status="blocked", risk="critical", message=f"standard answer invalid: {answer!r}")
            if accepted is not None:
                if not isinstance(accepted, list) or not accepted:
                    add_issue(issues, layer="official_core", rule="MCQ_ACCEPTED_ANSWERS_SHAPE", status="blocked", risk="critical", message="accepted_answers must be a non-empty list when present")
                else:
                    xs = [str(x).strip().upper() for x in accepted]
                    if len(xs) != len(set(xs)) or any(x not in letters for x in xs):
                        add_issue(issues, layer="official_core", rule="MCQ_ACCEPTED_ANSWERS_VALID", status="blocked", risk="critical", message=f"accepted_answers invalid: {xs}")
                    if answer in letters and answer not in xs:
                        add_issue(issues, layer="official_core", rule="MCQ_PRIMARY_IN_ACCEPTED", status="blocked", risk="critical", message="primary answer not included in accepted_answers")
        elif mode in {"all_credit", "any_answer"}:
            if str(row.get("answer") or "").strip() != special_marker:
                add_issue(issues, layer="official_core", rule="MCQ_SPECIAL_MARKER_MATCH", status="blocked", risk="critical", message=f"{mode} must use answer={special_marker}")
            if accepted is not None:
                add_issue(issues, layer="official_core", rule="MCQ_SPECIAL_ACCEPTED_EMPTY", status="blocked", risk="critical", message="special grading must not carry accepted_answers")

        enrichment_text = "\n".join(
            str(row.get(k) or "")
            for k in ("question", "q", "law", "extension", "exp_why", "exp_raw")
        )
        legal_hits = text_matches(enrichment_text, legal_patterns)
        canonical_laws = canonical_law_matches(enrichment_text, legal_watch)
        legal_status = str(row.get("legal_status") or "").strip().lower()
        watch_fresh = legal_watch_clears_current_review(
            canonical_laws, legal_watch, trust_current_legal_watch
        )
        if legal_hits and legal_status not in CHECKED_LEGAL_STATES and not watch_fresh:
            add_issue(
                issues,
                layer="enrichment",
                rule="ENRICHMENT_LEGAL_REVIEW",
                status="needs_review",
                risk="high",
                message="legal/policy content detected without checked status or trusted fresh current legal watch",
            )

        analysis_status = str(row.get("analysis_status") or "").strip().lower()
        record = official_core_record(row, "mcq", issues)
        record["generation_state"] = "ready" if analysis_status in READY_ANALYSIS_STATES else "pending_generation"
        record["signals"] = {
            "legal_or_policy": legal_hits,
            "canonical_laws": canonical_laws,
            "legal_watch_fresh": watch_fresh,
        }
        results.append(record)

    return results, session_issues


def validate_essays(
    rows: list[dict],
    year: str,
    round_name: str,
    policy: dict,
    legal_watch: dict | None = None,
    trust_current_legal_watch: bool = False,
) -> tuple[list[dict], list[dict]]:
    cfg = policy["essay"]
    subjects = set(policy["subjects"])
    session_issues: list[dict] = []
    results: list[dict] = []

    expected_total = int(cfg["expected_total"])
    if len(rows) != expected_total:
        add_issue(session_issues, layer="official_core", rule="ESSAY_SESSION_COUNT", status="blocked", risk="critical", message=f"expected {expected_total} essays, got {len(rows)}")

    ids = [str(r.get("id") or "") for r in rows]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        add_issue(session_issues, layer="official_core", rule="ESSAY_ID_UNIQUE", status="blocked", risk="critical", message="missing or duplicated essay IDs")

    counts = Counter(str(r.get("subject") or "") for r in rows)
    expected_per_subject = int(cfg["expected_per_subject"])
    if set(counts) != subjects or any(counts.get(s, 0) != expected_per_subject for s in subjects):
        add_issue(session_issues, layer="official_core", rule="ESSAY_SUBJECT_DISTRIBUTION", status="blocked", risk="critical", message=f"subject distribution invalid: {dict(counts)}")

    by_subject: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        n = qno_int(row.get("qno"))
        if n is not None:
            by_subject[str(row.get("subject") or "")].add(n)
    expected_qnos = set(range(int(cfg["qno_min"]), int(cfg["qno_max"]) + 1))
    for subject in subjects:
        if by_subject.get(subject, set()) != expected_qnos:
            add_issue(session_issues, layer="official_core", rule="ESSAY_QNO_COVERAGE", status="blocked", risk="critical", message=f"{subject}: qno set is not {min(expected_qnos)}..{max(expected_qnos)}")

    legal_patterns = list(policy.get("risk_signals", {}).get("legal_or_policy_high", []))
    multi_patterns = list(policy.get("risk_signals", {}).get("multi_requirement_medium", []))

    for row in rows:
        issues: list[dict] = []
        item_id = str(row.get("id") or "")
        subject = str(row.get("subject") or "").strip()
        row_year = str(row.get("year") or "").strip()
        row_round = canon_round(row.get("round"), policy)
        n = qno_int(row.get("qno"))
        question = str(row.get("q") or row.get("question") or "").strip()

        if not item_id:
            add_issue(issues, layer="official_core", rule="ESSAY_ID_REQUIRED", status="blocked", risk="critical", message="id missing")
        if subject not in subjects:
            add_issue(issues, layer="official_core", rule="ESSAY_SUBJECT_VALID", status="blocked", risk="critical", message=f"invalid subject: {subject!r}")
        if row_year != year or row_round != round_name:
            add_issue(issues, layer="official_core", rule="ESSAY_SESSION_MATCH", status="blocked", risk="critical", message=f"row belongs to {row_year}-{row_round}")
        if n is None or not (int(cfg["qno_min"]) <= n <= int(cfg["qno_max"])):
            add_issue(issues, layer="official_core", rule="ESSAY_QNO_VALID", status="blocked", risk="critical", message=f"invalid qno: {row.get('qno')!r}")
        if not question:
            add_issue(issues, layer="official_core", rule="ESSAY_QUESTION_REQUIRED", status="blocked", risk="critical", message="official essay stem missing")
        if not str(row.get("source_exam_code") or "").strip():
            add_issue(issues, layer="official_core", rule="ESSAY_SOURCE_CODE_REQUIRED", status="needs_review", risk="high", message="source_exam_code missing")
        if not str(row.get("source_url") or "").strip():
            add_issue(issues, layer="official_core", rule="ESSAY_SOURCE_URL_REQUIRED", status="needs_review", risk="high", message="official source_url missing")

        legal_hits = text_matches(question, legal_patterns)
        multi_hits = text_matches(question, multi_patterns)
        canonical_laws = canonical_law_matches(question, legal_watch)
        watch_fresh = legal_watch_clears_current_review(
            canonical_laws, legal_watch, trust_current_legal_watch
        )

        if legal_hits and not watch_fresh:
            add_issue(
                issues,
                layer="enrichment",
                rule="ESSAY_HISTORICAL_LAW_REVIEW",
                status="needs_review",
                risk="high",
                message="law/policy signal detected; guide needs law-version QA unless current legal watch is explicitly trusted",
            )

        analysis_status = str(row.get("analysis_status") or "").strip().lower()
        record = official_core_record(row, "essay", issues)
        record["generation_state"] = "ready" if analysis_status in READY_ANALYSIS_STATES else "pending_generation"
        record["signals"] = {
            "legal_or_policy": legal_hits,
            "canonical_laws": canonical_laws,
            "legal_watch_fresh": watch_fresh,
            "multi_requirement": multi_hits,
            "complexity_risk": "high" if legal_hits else ("medium" if multi_hits else "low"),
        }
        results.append(record)

    return results, session_issues


def summarize(items: list[dict], session_issues: list[dict]) -> dict:
    official_counts = Counter(x["official_status"] for x in items)
    enrichment_counts = Counter(x["enrichment_status"] for x in items)
    generation_counts = Counter(x["generation_state"] for x in items)

    manual_queue = []
    for x in items:
        if x["official_status"] in {"needs_review", "blocked"} or x["enrichment_status"] in {"needs_review", "blocked"}:
            manual_queue.append(
                {
                    "id": x["id"],
                    "kind": x["kind"],
                    "official_status": x["official_status"],
                    "enrichment_status": x["enrichment_status"],
                    "max_risk": max(
                        (x["official_risk"], x["enrichment_risk"]),
                        key=lambda r: RISK_RANK.get(r, -1),
                    ),
                }
            )

    session_status = worst_status(session_issues, "official_core")
    official_release_ready = (
        session_status == "passed"
        and official_counts.get("blocked", 0) == 0
        and official_counts.get("needs_review", 0) == 0
    )

    return {
        "items": len(items),
        "session_status": session_status,
        "official_core": {
            "passed": official_counts.get("passed", 0),
            "needs_review": official_counts.get("needs_review", 0),
            "blocked": official_counts.get("blocked", 0),
            "release_ready": official_release_ready,
        },
        "enrichment": {
            "passed": enrichment_counts.get("passed", 0),
            "needs_review": enrichment_counts.get("needs_review", 0),
            "blocked": enrichment_counts.get("blocked", 0),
            "pending_generation": generation_counts.get("pending_generation", 0),
        },
        "manual_review_queue_count": len(manual_queue),
        "manual_review_queue": manual_queue,
        "session_issues": session_issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SWSI unified MCQ + essay intake QA")
    ap.add_argument("--mcq", type=Path, help="MCQ shard JSON or JSON list")
    ap.add_argument("--essays", type=Path, help="Essay JSON list")
    ap.add_argument("--year", required=True, help="ROC exam year, e.g. 115")
    ap.add_argument("--round", required=True, help="1/2 or 第一次/第二次")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--legal-watch", type=Path, help="Current law watch report JSON")
    ap.add_argument(
        "--trust-current-legal-watch",
        action="store_true",
        help="For the current/new intake only: let unchanged named laws satisfy intake legal review. Never use for historical exam backfill.",
    )
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fail-on", choices=["blocked", "review", "never"], default="blocked")
    args = ap.parse_args()

    if not args.mcq and not args.essays:
        ap.error("at least one of --mcq or --essays is required")
    if args.trust_current_legal_watch and not args.legal_watch:
        ap.error("--trust-current-legal-watch requires --legal-watch")

    policy = read_json(args.policy)
    legal_watch = load_legal_watch(args.legal_watch)
    year = str(args.year).strip()
    round_name = canon_round(args.round, policy)
    if round_name not in {"第一次", "第二次"}:
        raise SystemExit(f"invalid round: {args.round!r}")

    all_items: list[dict] = []
    all_session_issues: list[dict] = []
    sections: dict[str, Any] = {}

    if args.mcq:
        mcq_rows = filter_session(normalize_mcq_payload(read_json(args.mcq)), year, round_name, policy)
        mcq_items, mcq_session_issues = validate_mcq(
            mcq_rows,
            year,
            round_name,
            policy,
            legal_watch=legal_watch,
            trust_current_legal_watch=args.trust_current_legal_watch,
        )
        all_items.extend(mcq_items)
        all_session_issues.extend(mcq_session_issues)
        sections["mcq"] = summarize(mcq_items, mcq_session_issues)

    if args.essays:
        essay_rows = filter_session(normalize_essay_payload(read_json(args.essays)), year, round_name, policy)
        essay_items, essay_session_issues = validate_essays(
            essay_rows,
            year,
            round_name,
            policy,
            legal_watch=legal_watch,
            trust_current_legal_watch=args.trust_current_legal_watch,
        )
        all_items.extend(essay_items)
        all_session_issues.extend(essay_session_issues)
        sections["essay"] = summarize(essay_items, essay_session_issues)

    overall = summarize(all_items, all_session_issues)
    report = {
        "schema_version": 1,
        "year": year,
        "round": round_name,
        "policy": str(args.policy),
        "legal_watch": {
            "path": str(args.legal_watch) if args.legal_watch else None,
            "trusted_for_current_intake": bool(args.trust_current_legal_watch),
            "checked_at": (legal_watch or {}).get("checked_at"),
        },
        "overall": overall,
        "sections": sections,
        "items": all_items,
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    blocked = overall["official_core"]["blocked"] > 0 or overall["session_status"] == "blocked"
    review = overall["manual_review_queue_count"] > 0
    if args.fail_on == "blocked" and blocked:
        return 2
    if args.fail_on == "review" and (blocked or review):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
