#!/usr/bin/env python3
"""Current-intake legal-watch projection for enrichment_decision.py.

The base enrichment decision engine is intentionally time-neutral. This wrapper
may clear only `ENRICHMENT_LEGAL_EVIDENCE_REQUIRED` when the caller explicitly
opts into a trusted *current/new intake* legal-watch snapshot and every named
canonical law is found and unchanged.

Never use this current-law projection as historical-law-version proof.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from enrichment_decision import (
    DEFAULT_POLICY,
    DEFAULT_QUESTION_POLICY,
    RISK_RANK,
    build_report,
    decision_metadata,
    normalize_questions,
    read_json,
    worst_risk,
    worst_status,
)


def load_legal_watch(path: Path) -> dict[str, Any]:
    raw = read_json(path)
    records = raw.get("records") if isinstance(raw, dict) else None
    if not isinstance(records, list):
        raise ValueError("legal watch JSON must contain records[]")
    by_name: dict[str, dict[str, Any]] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        name = str(row.get("canonical_name") or "").strip()
        if name:
            by_name[name] = row
    return {
        "schema_version": raw.get("schema_version"),
        "checked_at": str(raw.get("checked_at") or ""),
        "lookup_error_count": int(raw.get("lookup_error_count") or 0),
        "missing_count": int(raw.get("missing_count") or 0),
        "changed_count": int(raw.get("changed_count") or 0),
        "records": by_name,
    }


def current_watch_clears(names: list[str], watch: dict[str, Any]) -> bool:
    if not names or watch.get("lookup_error_count", 0) != 0:
        return False
    records = watch.get("records") or {}
    for name in names:
        row = records.get(name) or {}
        if row.get("found") is not True:
            return False
        if row.get("changed") is True:
            return False
    return True


def _rebuild_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
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
        "items": len(items),
        "status_counts": dict(status_counts),
        "publish_action_counts": dict(action_counts),
        "automation_confidence_counts": dict(confidence_counts),
        "finding_rule_counts": dict(rule_counts),
        "human_review_count": len(review_items),
        "safe_sanitization_count": len(sanitized_items),
    }, review_items, sanitized_items


def apply_trusted_current_legal_watch(
    report: dict[str, Any],
    *,
    watch: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    out = copy.deepcopy(report)
    if out.get("contract") != "swsi_enrichment_decision_v1":
        raise ValueError("unexpected enrichment decision contract")

    cleared_ids: list[str] = []
    for item in out.get("items") or []:
        if not isinstance(item, dict):
            raise ValueError("enrichment decision item must be an object")
        findings = item.get("findings") or []
        if not isinstance(findings, list):
            raise ValueError("item findings must be a list")
        target = [
            finding
            for finding in findings
            if isinstance(finding, dict)
            and finding.get("rule") == "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED"
        ]
        if not target:
            item.setdefault("evidence", {})["legal_watch_fresh"] = False
            continue
        names = [
            str(value)
            for value in (item.get("evidence") or {}).get("official_canonical_laws") or []
            if str(value).strip()
        ]
        if not current_watch_clears(names, watch):
            item.setdefault("evidence", {})["legal_watch_fresh"] = False
            continue

        item["findings"] = [
            finding
            for finding in findings
            if finding not in target
        ]
        remaining = item["findings"]
        status = worst_status(remaining)
        risk = worst_risk(remaining)
        if status == "passed" and item.get("field_actions"):
            status = "passed_sanitized"
            risk = max((risk, "medium"), key=lambda value: RISK_RANK[value])
        meta = decision_metadata(status, risk, policy)
        item["enrichment_status"] = status
        item.update(meta)
        item["review_reasons"] = [
            finding["rule"]
            for finding in remaining
            if finding.get("status") in {"needs_review", "blocked"}
        ]
        evidence = item.setdefault("evidence", {})
        evidence["legal_watch_fresh"] = True
        evidence["legal_watch_checked_at"] = watch.get("checked_at")
        cleared_ids.append(str(item.get("id") or ""))

    summary, review_items, sanitized_items = _rebuild_summary(out.get("items") or [])
    out["summary"] = summary
    out["human_review_queue"] = review_items
    out["safe_sanitizations"] = sanitized_items
    out["current_legal_watch"] = {
        "trusted_for_current_intake": True,
        "checked_at": watch.get("checked_at"),
        "lookup_error_count": watch.get("lookup_error_count"),
        "missing_count": watch.get("missing_count"),
        "changed_count": watch.get("changed_count"),
        "cleared_review_count": len(cleared_ids),
        "cleared_item_ids": cleared_ids,
        "historical_version_proof": False,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SWSI current-intake enrichment decision with explicit trusted legal-watch opt-in"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--legal-watch", type=Path, required=True)
    parser.add_argument("--trust-current-legal-watch", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--question-policy", type=Path, default=DEFAULT_QUESTION_POLICY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on", choices=["never", "blocked", "review"], default="never")
    args = parser.parse_args()
    if not args.trust_current_legal_watch:
        raise SystemExit(
            "current legal-watch projection requires explicit --trust-current-legal-watch; "
            "do not use it for historical-law proof"
        )

    policy = read_json(args.policy)
    base = build_report(
        normalize_questions(read_json(args.input)),
        policy=policy,
        question_policy=read_json(args.question_policy),
        source=str(args.input),
    )
    report = apply_trusted_current_legal_watch(
        base,
        watch=load_legal_watch(args.legal_watch),
        policy=policy,
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
