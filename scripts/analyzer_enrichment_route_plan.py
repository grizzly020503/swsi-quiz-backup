#!/usr/bin/env python3
"""Dry-run route planner between production analyzer candidates and enrichment QA.

This is deliberately NOT imported by the deployed Edge Function. It proves the
routing contract without writing data.

Input boundary:
- official question row is immutable evidence;
- analyzer candidate may contain exactly the v12 FIELDS payload and must not
  contain question/options/answer/grading/source fields;
- deterministic enrichment decision chooses ready / sanitized-ready / review;
- current legal-watch projection is opt-in and never historical-law proof;
- a legal-risk candidate may auto-publish only when separate exam-time
  historical evidence has already been verified.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from enrichment_decision import (
    DEFAULT_POLICY,
    DEFAULT_QUESTION_POLICY,
    build_report,
    normalize_questions,
    read_json,
)
from enrichment_decision_current import (
    apply_trusted_current_legal_watch,
    load_legal_watch,
)

ANALYZER_CANDIDATE_FIELDS = [
    "id",
    "major",
    "topic",
    "keywords",
    "exp_why",
    "exp_others",
    "exp_trap",
    "mnemonic",
    "extension",
    "law",
    "mistake",
]
ENRICHMENT_FIELDS = [field for field in ANALYZER_CANDIDATE_FIELDS if field != "id"]
OFFICIAL_CORE_FIELDS = {
    "question",
    "opt_a",
    "opt_b",
    "opt_c",
    "opt_d",
    "answer",
    "accepted_answers",
    "grading_mode",
    "subject",
    "year",
    "round",
    "qno",
    "source_exam_code",
    "source_url",
}
ALLOWED_FIELD_ACTIONS = {"law": {"drop"}}
LEGAL_EVIDENCE_RULE = "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED"


def clean(value: Any) -> str:
    return str(value or "").strip()


def validate_candidate(question: dict[str, Any], candidate: Any) -> dict[str, Any]:
    if not isinstance(question, dict):
        raise TypeError("official question must be an object")
    qid = clean(question.get("id"))
    if not qid:
        raise ValueError("official question id is required")
    if not isinstance(candidate, dict) or isinstance(candidate, list):
        raise TypeError("analyzer candidate must be an object")

    keys = set(candidate)
    expected = set(ANALYZER_CANDIDATE_FIELDS)
    if keys != expected:
        unexpected = sorted(keys - expected)
        missing = sorted(expected - keys)
        core_attempt = sorted(keys.intersection(OFFICIAL_CORE_FIELDS))
        raise ValueError(
            "analyzer candidate field contract mismatch: "
            f"missing={missing} unexpected={unexpected} official_core_attempt={core_attempt}"
        )
    if clean(candidate.get("id")) != qid:
        raise ValueError("analyzer candidate id does not match official question")
    return copy.deepcopy(candidate)


def merged_evaluation_row(
    question: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Return an evaluation copy without mutating Official Core input."""
    merged = copy.deepcopy(question)
    for field in ENRICHMENT_FIELDS:
        merged[field] = candidate.get(field)
    # Decision engine evaluates a post-generation candidate. This synthetic
    # ready marker is local-only and is never written by this planner.
    merged["analysis_status"] = "ready"
    merged.setdefault("legal_status", question.get("legal_status"))
    return merged


def _apply_sanitizations(
    candidate: dict[str, Any], field_actions: dict[str, Any]
) -> dict[str, Any]:
    out = copy.deepcopy(candidate)
    for field, action in field_actions.items():
        allowed = ALLOWED_FIELD_ACTIONS.get(field) or set()
        if action not in allowed:
            raise ValueError(f"unsupported deterministic field action: {field}={action}")
        if action == "drop":
            out[field] = None
    return out


def ready_patch(candidate: dict[str, Any]) -> dict[str, Any]:
    patch = {field: candidate.get(field) for field in ENRICHMENT_FIELDS}
    patch.update(
        {
            "exp_raw": None,
            "analysis_status": "ready",
            "analysis_attempts": 0,
            "analysis_error": None,
            "analysis_started_at": None,
        }
    )
    return patch


def review_patch(decision: dict[str, Any]) -> dict[str, Any]:
    reasons = [clean(x) for x in decision.get("review_reasons") or [] if clean(x)]
    message = "enrichment decision: " + (", ".join(reasons) or "manual review required")
    return {
        "analysis_status": "review",
        "analysis_error": message[:1000],
        "analysis_started_at": None,
    }


def _base_requires_legal_evidence(report: dict[str, Any]) -> bool:
    items = report.get("items") or []
    if len(items) != 1 or not isinstance(items[0], dict):
        return False
    return any(
        isinstance(finding, dict) and finding.get("rule") == LEGAL_EVIDENCE_RULE
        for finding in items[0].get("findings") or []
    )


def build_route_plan(
    question: dict[str, Any],
    candidate: dict[str, Any],
    *,
    policy: dict[str, Any],
    question_policy: dict[str, Any],
    legal_watch: dict[str, Any] | None = None,
    trust_current_legal_watch: bool = False,
    historical_version_checked: bool = False,
) -> dict[str, Any]:
    candidate = validate_candidate(question, candidate)
    qid = clean(question.get("id"))
    merged = merged_evaluation_row(question, candidate)

    base_report = build_report(
        [merged],
        policy=policy,
        question_policy=question_policy,
        source=f"analyzer-candidate:{qid}",
    )
    report = base_report
    current_projection: dict[str, Any] | None = None

    if trust_current_legal_watch:
        if legal_watch is None:
            raise ValueError("trusted current legal-watch mode requires legal_watch data")
        projected = apply_trusted_current_legal_watch(
            base_report,
            watch=legal_watch,
            policy=policy,
        )
        current_projection = projected.get("current_legal_watch")
        # Current-law evidence is only one prerequisite. If the base decision
        # required legal provenance, exam-time historical verification remains
        # mandatory before current-law projection may clear that review reason.
        if historical_version_checked or not _base_requires_legal_evidence(base_report):
            report = projected
        else:
            report = copy.deepcopy(base_report)
            report["current_legal_watch"] = current_projection
            report["current_legal_watch"]["historical_version_proof"] = False
    elif legal_watch is not None:
        raise ValueError(
            "legal_watch data supplied without explicit trust_current_legal_watch opt-in"
        )

    items = report.get("items") or []
    if len(items) != 1:
        raise AssertionError("single analyzer candidate must produce exactly one decision")
    decision = items[0]
    status = clean(decision.get("enrichment_status"))
    field_actions = decision.get("field_actions") or {}
    if not isinstance(field_actions, dict):
        raise ValueError("decision field_actions must be an object")

    proposed_patch: dict[str, Any] | None
    publication_allowed: bool
    route: str
    sanitized_candidate: dict[str, Any] | None = None

    if status == "passed":
        route = "ready"
        publication_allowed = True
        proposed_patch = ready_patch(candidate)
    elif status == "passed_sanitized":
        sanitized_candidate = _apply_sanitizations(candidate, field_actions)
        route = "sanitized_ready"
        publication_allowed = True
        proposed_patch = ready_patch(sanitized_candidate)
    elif status in {"needs_review", "blocked"}:
        # Blocked enrichment is routed to the existing human-review state rather
        # than publishing the candidate. The candidate itself is retained only in
        # this dry-run plan; no production draft storage is introduced here.
        route = "review"
        publication_allowed = False
        proposed_patch = review_patch(decision)
    elif status == "pending_generation":
        raise ValueError("post-generation analyzer candidate cannot be pending_generation")
    else:
        raise ValueError(f"unknown enrichment decision status: {status!r}")

    forbidden_patch = sorted(set(proposed_patch or {}).intersection(OFFICIAL_CORE_FIELDS))
    if forbidden_patch:
        raise AssertionError(
            f"route planner attempted Official Core mutation: {forbidden_patch}"
        )

    return {
        "schema_version": 1,
        "contract": "swsi_analyzer_enrichment_route_dryrun_v1",
        "mode": "dry_run_no_write",
        "question_id": qid,
        "route": route,
        "publication_allowed": publication_allowed,
        "decision": {
            "enrichment_status": status,
            "risk": decision.get("risk"),
            "automation_confidence": decision.get("automation_confidence"),
            "publish_action": decision.get("publish_action"),
            "field_actions": field_actions,
            "review_reasons": decision.get("review_reasons") or [],
            "findings": decision.get("findings") or [],
        },
        "proposed_update_patch": proposed_patch,
        "sanitized_candidate": sanitized_candidate,
        "current_legal_watch": report.get("current_legal_watch"),
        "historical_version_checked": historical_version_checked,
        "safety": {
            "official_core_modified": False,
            "production_write_performed": False,
            "model_called": False,
            "production_analyzer_modified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run analyzer candidate -> enrichment decision route planner"
    )
    parser.add_argument("--question", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--question-policy", type=Path, default=DEFAULT_QUESTION_POLICY)
    parser.add_argument("--legal-watch", type=Path)
    parser.add_argument("--trust-current-legal-watch", action="store_true")
    parser.add_argument("--historical-version-checked", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    question_payload = read_json(args.question)
    rows = normalize_questions(question_payload)
    if len(rows) != 1:
        raise SystemExit("--question must contain exactly one question")
    candidate = read_json(args.candidate)
    legal_watch = load_legal_watch(args.legal_watch) if args.legal_watch else None
    plan = build_route_plan(
        rows[0],
        candidate,
        policy=read_json(args.policy),
        question_policy=read_json(args.question_policy),
        legal_watch=legal_watch,
        trust_current_legal_watch=args.trust_current_legal_watch,
        historical_version_checked=args.historical_version_checked,
    )
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
