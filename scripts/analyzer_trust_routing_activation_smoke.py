#!/usr/bin/env python3
"""Zero-network source contract for analyzer trust-routing activation candidate.

This intentionally does not call Supabase or the AI proxy. It proves that the
live Edge Function source routes candidates through deterministic preflight and
post-model publication gates before any production deployment is allowed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "supabase/functions/analyze-pending-questions/index.ts"
ROUTE = ROOT / "supabase/functions/analyze-pending-questions/enrichment_route.ts"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    index = INDEX.read_text(encoding="utf-8")
    route = ROUTE.read_text(encoding="utf-8")

    for marker in (
        'from "./current_legal_trust.ts"',
        'from "./enrichment_route.ts"',
        'preflightQuestion(q, null, false)',
        'loadCurrentLegalTrust(sb, q)',
        'finalizeValidatedCandidate(q, candidate, preflight)',
        'route: "hold_retry"',
        'route: "preflight_review"',
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

    # Current-law health is necessary but cannot masquerade as historical proof.
    require('historical_law_evidence_required' in route,
            "exam-time historical-law gate missing")
    require('if (!historicalVersionChecked)' in route,
            "historical law proof must remain explicit")

    # Operational legal-watch query failures must be held without model calls.
    require('route_hold:${trust.queryError}' in index,
            "legal-watch query error must route to hold")
    require('analysis_attempts:' not in index[index.index('route_hold:${trust.queryError}'):
                                             index.index('continue;', index.index('route_hold:${trust.queryError}'))],
            "legal-watch query hold must not consume analysis attempts")

    print("ANALYZER TRUST ROUTING ACTIVATION CONTRACT OK")


if __name__ == "__main__":
    main()
