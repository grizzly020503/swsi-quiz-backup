#!/usr/bin/env python3
"""Translate guarded MOEX intake evidence into durable-ops decisions.

Pure contract only: no network, no Supabase writes, no GitHub mutations.
The caller decides when/if to persist the returned decision through the
server-side ops ledger adapter.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = 1
TASK_ID = "moex-social-worker-sync"

PROBE_CONTINUE = {"match"}
PROBE_RETRYABLE = {"source_error"}
PROBE_QUARANTINE = {"possible_scheme_change", "target_class_missing", "unapproved_scheme"}

PAYLOAD_CONTINUE = {"match"}
PAYLOAD_QUARANTINE = {"candidate_change", "invalid_identity"}

_ALLOWED_LEDGER_OUTCOMES = {
    None, "failed_retryable", "failed_terminal", "quarantined"
}


def _clean(value: Any, *, limit: int = 1000) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _exam_code(report: dict[str, Any]) -> str:
    code = _clean(report.get("exam_code"), limit=12)
    if not re.fullmatch(r"\d{3}(030|100)", code):
        raise ValueError(f"invalid or missing exam_code: {code!r}")
    return code


def _source_ref(report: dict[str, Any]) -> str:
    return _clean(report.get("source_url") or report.get("source_ref") or _exam_code(report), limit=500)


def _fingerprint(report: dict[str, Any]) -> str:
    sha = _clean(report.get("content_sha256"), limit=128).lower()
    if re.fullmatch(r"[0-9a-f]{64}", sha):
        return sha[:16]
    stable = json.dumps(
        {
            "status": report.get("status"),
            "exam_code": report.get("exam_code"),
            "profile_id": report.get("profile_id"),
            "diffs": report.get("diffs") or [],
            "observed_subjects": report.get("observed_subjects") or [],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def _review_item(
    *,
    exam_code: str,
    reason: str,
    source_ref: str,
    evidence: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    return {
        "item_id": f"moex:{exam_code}:{reason}:{fingerprint}",
        "task_id": TASK_ID,
        "reason": reason,
        "source_ref": source_ref,
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "exam_code": exam_code,
            "evidence_fingerprint": fingerprint,
            "status": evidence.get("status"),
            "profile_id": evidence.get("profile_id"),
            "diffs": evidence.get("diffs") or [],
            "observed_subjects": evidence.get("observed_subjects") or [],
        },
    }


def classify_probe(
    report: dict[str, Any],
    *,
    retry_exhausted: bool = False,
    retry_after_seconds: int = 900,
) -> dict[str, Any]:
    """Classify a pre-parser MOEX structure probe.

    ``source_error`` stays retryable until the caller's bounded retry budget is
    exhausted. Structural/identity drift is immediately quarantined and becomes
    a manual review item.
    """
    if not isinstance(report, dict):
        raise TypeError("probe report must be an object")
    code = _exam_code(report)
    status = _clean(report.get("status"), limit=80)
    source_ref = _source_ref(report)
    fingerprint = _fingerprint(report)

    if status in PROBE_CONTINUE:
        if report.get("safe_to_parse_pdfs") is not True:
            raise ValueError("match probe must explicitly set safe_to_parse_pdfs=true")
        decision = {
            "schema_version": SCHEMA_VERSION,
            "event_type": "moex_probe_decision",
            "task_id": TASK_ID,
            "exam_code": code,
            "action": "continue",
            "ledger_outcome": None,
            "retry_after_seconds": None,
            "review_required": False,
            "review_item": None,
            "source_ref": source_ref,
        }
    elif status in PROBE_RETRYABLE:
        if retry_exhausted:
            reason = "source_unavailable_after_retries"
            decision = {
                "schema_version": SCHEMA_VERSION,
                "event_type": "moex_probe_decision",
                "task_id": TASK_ID,
                "exam_code": code,
                "action": "manual_review",
                "ledger_outcome": "failed_terminal",
                "retry_after_seconds": None,
                "review_required": True,
                "review_item": _review_item(
                    exam_code=code,
                    reason=reason,
                    source_ref=source_ref,
                    evidence=report,
                    fingerprint=fingerprint,
                ),
                "source_ref": source_ref,
            }
        else:
            decision = {
                "schema_version": SCHEMA_VERSION,
                "event_type": "moex_probe_decision",
                "task_id": TASK_ID,
                "exam_code": code,
                "action": "retry",
                "ledger_outcome": "failed_retryable",
                "retry_after_seconds": max(60, int(retry_after_seconds)),
                "review_required": False,
                "review_item": None,
                "source_ref": source_ref,
            }
    elif status in PROBE_QUARANTINE:
        reason = {
            "possible_scheme_change": "possible_exam_scheme_change",
            "target_class_missing": "target_class_missing",
            "unapproved_scheme": "unapproved_exam_scheme",
        }[status]
        decision = {
            "schema_version": SCHEMA_VERSION,
            "event_type": "moex_probe_decision",
            "task_id": TASK_ID,
            "exam_code": code,
            "action": "quarantine",
            "ledger_outcome": "quarantined",
            "retry_after_seconds": None,
            "review_required": True,
            "review_item": _review_item(
                exam_code=code,
                reason=reason,
                source_ref=source_ref,
                evidence=report,
                fingerprint=fingerprint,
            ),
            "source_ref": source_ref,
        }
    else:
        # Unknown future status must never silently continue or be guessed as
        # transient. Treat it as a structural contract change.
        reason = "unknown_probe_status"
        decision = {
            "schema_version": SCHEMA_VERSION,
            "event_type": "moex_probe_decision",
            "task_id": TASK_ID,
            "exam_code": code,
            "action": "quarantine",
            "ledger_outcome": "quarantined",
            "retry_after_seconds": None,
            "review_required": True,
            "review_item": _review_item(
                exam_code=code,
                reason=reason,
                source_ref=source_ref,
                evidence=report,
                fingerprint=fingerprint,
            ),
            "source_ref": source_ref,
        }

    if decision["ledger_outcome"] not in _ALLOWED_LEDGER_OUTCOMES:
        raise AssertionError("translator emitted an unsupported ledger outcome")
    return decision


def classify_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Classify the post-parser exam-scheme comparison."""
    if not isinstance(report, dict):
        raise TypeError("payload scheme report must be an object")
    code = _exam_code(report)
    status = _clean(report.get("status"), limit=80)
    source_ref = _source_ref(report)
    fingerprint = _fingerprint(report)

    if status in PAYLOAD_CONTINUE and report.get("approved") is True:
        return {
            "schema_version": SCHEMA_VERSION,
            "event_type": "moex_payload_scheme_decision",
            "task_id": TASK_ID,
            "exam_code": code,
            "action": "continue",
            "ledger_outcome": None,
            "retry_after_seconds": None,
            "review_required": False,
            "review_item": None,
            "source_ref": source_ref,
        }

    if status in PAYLOAD_QUARANTINE or status not in PAYLOAD_CONTINUE:
        reason = {
            "candidate_change": "post_parse_scheme_change",
            "invalid_identity": "invalid_exam_identity",
        }.get(status, "unknown_payload_scheme_status")
        return {
            "schema_version": SCHEMA_VERSION,
            "event_type": "moex_payload_scheme_decision",
            "task_id": TASK_ID,
            "exam_code": code,
            "action": "quarantine",
            "ledger_outcome": "quarantined",
            "retry_after_seconds": None,
            "review_required": True,
            "review_item": _review_item(
                exam_code=code,
                reason=reason,
                source_ref=source_ref,
                evidence=report,
                fingerprint=fingerprint,
            ),
            "source_ref": source_ref,
        }

    # A nominal ``match`` without approved=true is contradictory and must fail
    # closed instead of continuing.
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": "moex_payload_scheme_decision",
        "task_id": TASK_ID,
        "exam_code": code,
        "action": "quarantine",
        "ledger_outcome": "quarantined",
        "retry_after_seconds": None,
        "review_required": True,
        "review_item": _review_item(
            exam_code=code,
            reason="unapproved_match_contract",
            source_ref=source_ref,
            evidence=report,
            fingerprint=fingerprint,
        ),
        "source_ref": source_ref,
    }
