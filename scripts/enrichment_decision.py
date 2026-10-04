#!/usr/bin/env python3
"""Deterministic advisory gate for SWSI MCQ enrichment.

This module evaluates already-generated enrichment against immutable official
question evidence and existing trust metadata. It never mutates Official Core,
never calls a model/network service, and never writes production state.

The output deliberately uses explainable bands instead of a fake numeric model
confidence score:
- passed / high -> safe for automatic enrichment publication;
- passed_sanitized / medium -> safe only after the returned field action;
- needs_review / low -> hold enrichment for review;
- blocked -> fail closed for enrichment only;
- pending_generation -> generation backlog, not human-review debt.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "data/enrichment_decision_policy.v1.json"
DEFAULT_QUESTION_POLICY = ROOT / "data/question_qa_policy_v1.json"

STATUS_RANK = {
    "passed": 0,
    "passed_sanitized": 1,
    "needs_review": 2,
    "blocked": 3,
}
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
VALID_LETTERS = {"A", "B", "C", "D"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    return unicodedata.normalize("NFKC", clean(value))


def normalize_questions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        return [row for row in payload["questions"] if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError("input must be a question shard with questions[] or a list")


def official_answers(row: dict[str, Any]) -> list[str]:
    raw = row.get("accepted_answers")
    if isinstance(raw, list):
        xs = []
        for value in raw:
            letter = clean(value).upper()
            if letter in VALID_LETTERS and letter not in xs:
                xs.append(letter)
        if xs:
            return xs
    answer = clean(row.get("answer")).upper()
    return [answer] if answer in VALID_LETTERS else []


def official_evidence_text(row: dict[str, Any]) -> str:
    return " ".join(
        clean(row.get(key))
        for key in ("question", "opt_a", "opt_b", "opt_c", "opt_d")
        if clean(row.get(key))
    )


def analyzer_source_text(row: dict[str, Any]) -> str:
    # Mirror the current v12 validator boundary: option labels and official
    # answer letters are source tokens; generated enrichment is never evidence.
    return " ".join(
        ["A", "B", "C", "D", official_evidence_text(row), *official_answers(row)]
    )


def ascii_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9'’\-]*", text or "")
    }


def number_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text or ""))


def regex_hits(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.I):
                hits.append(pattern)
        except re.error:
            if pattern in text:
                hits.append(pattern)
    return hits


def load_law_registry(policy: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    law_cfg = policy.get("law") or {}
    rel = clean(law_cfg.get("canonical_names_path"))
    if not rel:
        raise ValueError("law.canonical_names_path is required")
    path = ROOT / rel
    rows = read_json(path)
    if not isinstance(rows, list):
        raise ValueError("canonical law registry must be a list")
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = normalize_text(row.get("name"))
        if name and name not in names:
            names.append(name)
    aliases = {
        normalize_text(alias): normalize_text(target)
        for alias, target in (law_cfg.get("aliases") or {}).items()
        if normalize_text(alias) and normalize_text(target)
    }
    if not names:
        raise ValueError("canonical law registry is empty")
    if any(target not in names for target in aliases.values()):
        raise ValueError("law alias target is not present in canonical registry")
    return names, aliases


def extract_law_names(text: str, names: list[str], aliases: dict[str, str]) -> list[str]:
    source = normalize_text(text)
    out: list[str] = []
    for alias, target in aliases.items():
        if alias in source and target not in out:
            out.append(target)
    # Longest-first makes the evidence easier to read while still preserving all
    # exact canonical hits; de-duplication prevents alias + full-name duplicates.
    for name in sorted(names, key=len, reverse=True):
        if name in source and name not in out:
            out.append(name)
    return out


def accepted_option_labels_in_others(text: str) -> set[str]:
    labels: set[str] = set()
    patterns = [
        r"(?:^|[\n。；;])\s*(?:選項\s*)?([ABCD])(?:\s*選項)?\s*[：:]",
        r"(?:^|[\n。；;])\s*([ABCD])\s*選項\s*[：:]?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.I | re.M):
            labels.add(match.group(1).upper())
    return labels


def add_finding(
    findings: list[dict[str, Any]],
    *,
    rule: str,
    status: str,
    risk: str,
    message: str,
    evidence: Any | None = None,
) -> None:
    if status not in STATUS_RANK or risk not in RISK_RANK:
        raise ValueError(f"invalid finding status/risk: {status}/{risk}")
    finding: dict[str, Any] = {
        "rule": rule,
        "status": status,
        "risk": risk,
        "message": message,
    }
    if evidence is not None:
        finding["evidence"] = evidence
    findings.append(finding)


def worst_status(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "passed"
    return max(
        (str(row.get("status") or "passed") for row in findings),
        key=lambda value: STATUS_RANK.get(value, -1),
    )


def worst_risk(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "low"
    return max(
        (str(row.get("risk") or "low") for row in findings),
        key=lambda value: RISK_RANK.get(value, -1),
    )


def decision_metadata(status: str, risk: str, policy: dict[str, Any]) -> dict[str, str]:
    configured = (policy.get("decisions") or {}).get(status) or {}
    confidence = clean(configured.get("automation_confidence"))
    publish_action = clean(configured.get("publish_action"))
    if not confidence or not publish_action:
        raise ValueError(f"policy decisions missing metadata for {status}")
    return {
        "risk": risk,
        "automation_confidence": confidence,
        "publish_action": publish_action,
    }


def evaluate_question(
    row: dict[str, Any],
    *,
    policy: dict[str, Any],
    question_policy: dict[str, Any],
    law_names: list[str],
    law_aliases: dict[str, str],
) -> dict[str, Any]:
    item_id = clean(row.get("id"))
    if not item_id:
        raise ValueError("question id is required")

    ready_states = {clean(x).lower() for x in policy.get("ready_analysis_states") or []}
    pending_states = {clean(x).lower() for x in policy.get("pending_analysis_states") or []}
    manual_states = {clean(x).lower() for x in policy.get("manual_analysis_states") or []}
    analysis_status = clean(row.get("analysis_status")).lower()

    if analysis_status in pending_states:
        meta = (policy.get("decisions") or {}).get("pending_generation") or {}
        return {
            "id": item_id,
            "subject": clean(row.get("subject")),
            "generation_state": "pending_generation",
            "enrichment_status": "pending_generation",
            "risk": clean(meta.get("risk")) or "low",
            "automation_confidence": clean(meta.get("automation_confidence")) or "not_applicable",
            "publish_action": clean(meta.get("publish_action")) or "hold_generation",
            "field_actions": {},
            "findings": [],
            "review_reasons": [],
            "evidence": {"analysis_status": analysis_status},
        }

    if analysis_status in manual_states:
        finding = {
            "rule": "UPSTREAM_ANALYSIS_REVIEW",
            "status": "needs_review",
            "risk": "high",
            "message": "upstream analyzer already placed this question in review",
        }
        meta = decision_metadata("needs_review", "high", policy)
        return {
            "id": item_id,
            "subject": clean(row.get("subject")),
            "generation_state": "review",
            "enrichment_status": "needs_review",
            **meta,
            "field_actions": {},
            "findings": [finding],
            "review_reasons": [finding["rule"]],
            "evidence": {"analysis_status": analysis_status},
        }

    if analysis_status not in ready_states:
        finding = {
            "rule": "UNKNOWN_ANALYSIS_STATE",
            "status": "needs_review",
            "risk": "high",
            "message": f"unknown analysis_status fails closed: {analysis_status!r}",
        }
        meta = decision_metadata("needs_review", "high", policy)
        return {
            "id": item_id,
            "subject": clean(row.get("subject")),
            "generation_state": "unknown",
            "enrichment_status": "needs_review",
            **meta,
            "field_actions": {},
            "findings": [finding],
            "review_reasons": [finding["rule"]],
            "evidence": {"analysis_status": analysis_status},
        }

    findings: list[dict[str, Any]] = []
    field_actions: dict[str, str] = {}
    required_fields = [clean(x) for x in policy.get("required_enrichment_fields") or []]
    missing = [field for field in required_fields if field and not clean(row.get(field))]
    if missing:
        add_finding(
            findings,
            rule="ENRICHMENT_REQUIRED_FIELDS",
            status="blocked",
            risk="critical",
            message="required enrichment fields are blank",
            evidence={"missing": missing},
        )

    grading_mode = clean(row.get("grading_mode"))
    answers = official_answers(row)
    if grading_mode not in {"standard", "all_credit", "any_answer"}:
        add_finding(
            findings,
            rule="ENRICHMENT_UNKNOWN_GRADING_MODE",
            status="blocked",
            risk="critical",
            message=f"unknown grading_mode fails closed: {grading_mode!r}",
        )
    elif grading_mode in {"all_credit", "any_answer"}:
        add_finding(
            findings,
            rule="ENRICHMENT_SPECIAL_GRADING",
            status="blocked",
            risk="critical",
            message="generic AI explanation is not auto-published for special grading",
            evidence={"grading_mode": grading_mode},
        )
    elif len(answers) > 1 and bool((policy.get("grading") or {}).get("multi_answer_standard_requires_review", True)):
        add_finding(
            findings,
            rule="ENRICHMENT_MULTI_ANSWER_REVIEW",
            status="needs_review",
            risk="medium",
            message="standard question has multiple accepted answers; hold generic enrichment for bounded review",
            evidence={"accepted_answers": answers},
        )
    elif not answers:
        add_finding(
            findings,
            rule="ENRICHMENT_OFFICIAL_ANSWER_MISSING",
            status="blocked",
            risk="critical",
            message="no usable official answer is available for enrichment validation",
        )

    source_text = analyzer_source_text(row)
    bound_fields = [clean(x) for x in policy.get("source_bound_text_fields") or []]
    generated_text = " ".join(clean(row.get(field)) for field in bound_fields if field)
    allowed_ascii = ascii_tokens(source_text)
    artifact_tokens = {
        clean(x).lower() for x in policy.get("format_artifact_ascii_tokens") or [] if clean(x)
    }
    extra_ascii = sorted(ascii_tokens(generated_text) - allowed_ascii - artifact_tokens)
    if extra_ascii:
        add_finding(
            findings,
            rule="ENRICHMENT_UNGROUNDED_ASCII",
            status="blocked",
            risk="critical",
            message="generated enrichment introduces ASCII/English tokens absent from official source",
            evidence={"tokens": extra_ascii[:30]},
        )
    extra_numbers = sorted(number_tokens(generated_text) - number_tokens(source_text))
    if extra_numbers:
        add_finding(
            findings,
            rule="ENRICHMENT_UNGROUNDED_NUMBER",
            status="blocked",
            risk="critical",
            message="generated enrichment introduces numeric claims absent from official source",
            evidence={"tokens": extra_numbers[:30]},
        )

    exp_others_labels = accepted_option_labels_in_others(clean(row.get("exp_others")))
    accepted_in_others = sorted(exp_others_labels.intersection(answers))
    if accepted_in_others:
        add_finding(
            findings,
            rule="ENRICHMENT_ACCEPTED_ANSWER_IN_OTHERS",
            status="needs_review",
            risk="high",
            message="exp_others explicitly labels an accepted answer option; possible answer-consistency conflict",
            evidence={"accepted_labels": accepted_in_others},
        )

    official_text = official_evidence_text(row)
    source_laws = extract_law_names(official_text, law_names, law_aliases)
    generated_law = clean(row.get("law"))
    generated_laws = extract_law_names(generated_law, law_names, law_aliases) if generated_law else []
    legal_status = clean(row.get("legal_status")).lower()
    checked_legal = {clean(x).lower() for x in policy.get("checked_legal_states") or []}
    changed_legal = {clean(x).lower() for x in policy.get("changed_legal_states") or []}

    # Mirror the production provenance principle without claiming this Python
    # projection replaces the DB canonicalizer: unsupported ordinary law metadata
    # is safe to omit, not a reason to block the whole explanation.
    evidence_backed_extension = legal_status in {"verified_current", "changed"}
    if generated_law and not evidence_backed_extension:
        if not generated_laws or not set(generated_laws).issubset(set(source_laws)):
            field_actions["law"] = "drop"
            add_finding(
                findings,
                rule="ENRICHMENT_LAW_AUTO_DROP",
                status="passed_sanitized",
                risk="medium",
                message="unverified generated law is non-canonical or not explicitly supported by official question/options; drop only law",
                evidence={
                    "generated_canonical_laws": generated_laws,
                    "official_canonical_laws": source_laws,
                },
            )

    legal_patterns = list((question_policy.get("risk_signals") or {}).get("legal_or_policy_high") or [])
    legal_hits = regex_hits(official_text, legal_patterns)
    if legal_hits or source_laws:
        if legal_status in changed_legal:
            add_finding(
                findings,
                rule="ENRICHMENT_LAW_CHANGED_REVIEW",
                status="needs_review",
                risk="high",
                message="legal content is marked changed; enrichment remains version-sensitive",
                evidence={"legal_status": legal_status, "canonical_laws": source_laws},
            )
        elif legal_status not in checked_legal:
            add_finding(
                findings,
                rule="ENRICHMENT_LEGAL_EVIDENCE_REQUIRED",
                status="needs_review",
                risk="high",
                message="legal/policy official content lacks checked evidence status",
                evidence={
                    "legal_status": legal_status,
                    "canonical_laws": source_laws,
                    "signal_count": len(legal_hits),
                },
            )

    status = worst_status(findings)
    risk = worst_risk(findings)
    if status == "passed" and field_actions:
        status = "passed_sanitized"
        risk = max((risk, "medium"), key=lambda value: RISK_RANK[value])
    meta = decision_metadata(status, risk, policy)
    review_reasons = [
        finding["rule"]
        for finding in findings
        if finding["status"] in {"needs_review", "blocked"}
    ]

    return {
        "id": item_id,
        "subject": clean(row.get("subject")),
        "generation_state": "ready",
        "enrichment_status": status,
        **meta,
        "field_actions": field_actions,
        "findings": findings,
        "review_reasons": review_reasons,
        "evidence": {
            "analysis_status": analysis_status,
            "grading_mode": grading_mode,
            "official_answers": answers,
            "official_canonical_laws": source_laws,
            "generated_canonical_laws": generated_laws,
            "legal_status": legal_status,
            "extra_ascii_tokens": extra_ascii[:30],
            "extra_number_tokens": extra_numbers[:30],
        },
    }


def build_report(
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
    question_policy: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    if policy.get("schema_version") != 1:
        raise ValueError("enrichment decision policy must be schema_version=1")
    if question_policy.get("schema_version") != 1:
        raise ValueError("question QA policy must be schema_version=1")
    safety = policy.get("safety") or {}
    if safety.get("official_core_mutation_allowed") is not False or safety.get("production_write_enabled") is not False:
        raise ValueError("advisory enrichment policy must forbid Official Core mutation and production writes")
    if safety.get("numeric_confidence_score_used") is not False:
        raise ValueError("V1 must use explainable confidence bands, not numeric pseudo-confidence")

    law_names, law_aliases = load_law_registry(policy)
    items = [
        evaluate_question(
            row,
            policy=policy,
            question_policy=question_policy,
            law_names=law_names,
            law_aliases=law_aliases,
        )
        for row in rows
    ]
    status_counts = Counter(item["enrichment_status"] for item in items)
    action_counts = Counter(item["publish_action"] for item in items)
    confidence_counts = Counter(item["automation_confidence"] for item in items)
    rule_counts = Counter(
        finding["rule"]
        for item in items
        for finding in item.get("findings") or []
    )
    review_items = [
        {
            "id": item["id"],
            "status": item["enrichment_status"],
            "risk": item["risk"],
            "review_reasons": item["review_reasons"],
        }
        for item in items
        if item["enrichment_status"] in {"needs_review", "blocked"}
    ]
    sanitized_items = [
        {"id": item["id"], "field_actions": item["field_actions"]}
        for item in items
        if item.get("field_actions")
    ]
    return {
        "schema_version": 1,
        "contract": "swsi_enrichment_decision_v1",
        "mode": "advisory_dry_run",
        "source": source,
        "summary": {
            "items": len(items),
            "status_counts": dict(status_counts),
            "publish_action_counts": dict(action_counts),
            "automation_confidence_counts": dict(confidence_counts),
            "finding_rule_counts": dict(rule_counts),
            "human_review_count": len(review_items),
            "safe_sanitization_count": len(sanitized_items),
        },
        "human_review_queue": review_items,
        "safe_sanitizations": sanitized_items,
        "items": items,
        "safety": {
            "official_core_modified": False,
            "production_write_performed": False,
            "model_called": False,
            "numeric_model_confidence_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SWSI deterministic MCQ enrichment decision advisory")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--question-policy", type=Path, default=DEFAULT_QUESTION_POLICY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fail-on", choices=["never", "blocked", "review"], default="never")
    args = parser.parse_args()

    rows = normalize_questions(read_json(args.input))
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be positive")
        rows = rows[: args.limit]
    report = build_report(
        rows,
        policy=read_json(args.policy),
        question_policy=read_json(args.question_policy),
        source=str(args.input),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    counts = report["summary"]["status_counts"]
    blocked = int(counts.get("blocked", 0))
    review = int(counts.get("needs_review", 0))
    if args.fail_on == "blocked" and blocked:
        return 2
    if args.fail_on == "review" and (blocked or review):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
