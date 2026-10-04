#!/usr/bin/env python3
"""Zero-network source contract for analyzer trust-routing activation candidate.

This intentionally does not call Supabase or the AI proxy. It proves that the
live Edge Function source routes candidates through deterministic current-law +
exam-time historical-law preflight and post-model publication gates before any
production deployment is allowed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "supabase/functions/analyze-pending-questions/index.ts"
ROUTE = ROOT / "supabase/functions/analyze-pending-questions/enrichment_route.ts"
HISTORICAL = ROOT / "supabase/functions/analyze-pending-questions/historical_law_trust.ts"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def no_attempt_consumption(index: str, marker: str, label: str) -> None:
    start = index.index(marker)
    end = index.index("continue;", start)
    require("analysis_attempts:" not in index[start:end], f"{label} must not consume analysis attempts")


def main() -> None:
    index = INDEX.read_text(encoding="utf-8")
    route = ROUTE.read_text(encoding="utf-8")
    historical = HISTORICAL.read_text(encoding="utf-8")

    for marker in (
        'from "./current_legal_trust.ts"',
        'from "./historical_law_trust.ts"',
        'from "./enrichment_route.ts"',
        'preflightQuestion(q, null, false)',
        'loadCurrentLegalTrust(sb, q)',
        'loadHistoricalLegalTrust(sb, q)',
        'preflightQuestion(q, currentTrust.decision, true)',
        'finalizeValidatedCandidate(q, candidate, preflight)',
        'historical_law_runtime_evidence_snapshot',
        'historical_law_runtime_evidence',
        'route: "hold_retry"',
        'route: "preflight_review"',
        'route: "historical_review"',
        'route: "post_model_review"',
        'model_called: false',
        'model_called: true',
    ):
        require(marker in index, f"analyzer activation marker missing: {marker}")

    # Fail-closed publication boundary: review branches write only analysis
    # control metadata; the generated candidate is written only via finalRoute.patch.
    require('updateClaimedQuestion(sb, q, finalRoute.patch)' in index,
            "ready publication must use finalRoute.patch")
    require('analysis_error: `route_review:${preflight.reason}`' in index,
            "preflight review audit reason missing")
    require('analysis_error: `route_hold:${preflight.reason}`' in index,
            "hold-retry audit reason missing")

    # Current-law health remains necessary, while Stage7 evidence is the actual
    # exam-time proof. Neither source can silently substitute for the other.
    require('historical_law_evidence_required' in route,
            "exam-time historical-law gate missing")
    require('if (!historicalVersionChecked)' in route,
            "historical law proof must remain explicit")
    for marker in (
        'historical_version_checked !== true',
        'historical_registry_batch_mismatch',
        'historical_exam_code_mismatch',
        'verified_exam_time_historical_law',
    ):
        require(marker in historical, f"historical trust marker missing: {marker}")

    # Operational current-law and historical evidence query failures must be
    # held without model calls or attempt consumption.
    no_attempt_consumption(index, 'route_hold:${currentTrust.queryError}', "current-law query hold")
    no_attempt_consumption(index, 'route_hold:${historicalTrust.queryError}', "historical-law query hold")
    require('historicalReasonIsOperationalRetry(reason)' in index,
            "historical operational/content error split missing")

    # The model call must occur after both evidence loaders in source order.
    require(index.index('loadCurrentLegalTrust(sb, q)') < index.index('loadHistoricalLegalTrust(sb, q)'),
            "historical gate must follow current-law gate")
    require(index.index('loadHistoricalLegalTrust(sb, q)') < index.index('const candidate = await analyzeOne(q, internalKey);'),
            "model must not run before historical-law gate")

    print("ANALYZER TRUST ROUTING ACTIVATION CONTRACT OK")


if __name__ == "__main__":
    main()
