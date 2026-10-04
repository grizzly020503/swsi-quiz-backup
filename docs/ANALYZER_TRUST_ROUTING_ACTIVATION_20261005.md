# Analyzer Trust-Routing Activation Gate — 2026-10-05

This branch is a **source-only production activation candidate**. It is not a deployment authorization.

## Intended runtime flow

1. claim one pending question
2. deterministic preflight before any model call
3. special grading / multiple accepted answers / missing official answer -> review
4. legal-risk question without canonical mapping -> review
5. legal-watch operational outage -> pending hold/retry without consuming analysis attempts
6. current-law watcher health is necessary but never treated as exam-time provenance
7. legal-risk question without verified historical exam-time evidence -> review
8. only ordinary eligible questions call draft + audit models
9. validated candidate passes a second deterministic publication gate
10. candidate is written only when final route is ready or sanitized-ready

## Important legal boundary

`current_legal_trust.ts` proves only that the latest current-law monitoring batch is healthy and internally consistent. It explicitly does **not** prove which law version was effective on a historical exam date.

This candidate therefore passes `historicalVersionChecked=false` in the live analyzer and intentionally keeps legal-risk questions out of automatic publication until the Stage-7/adjudicated historical-law registry is wired as a separate trusted runtime evidence source.

## Production prerequisites before any deployment

- `legal_watch_run_health` migration applied to production
- `sync-legal-watch` source from PR #368 deployed and one healthy non-baseline batch completed
- exact-head AI Analyzer Route QA green
- exact-head DR Restore Drill green
- verify production AI queue/config state before deployment
- deploy only `analyze-pending-questions` from the exact reviewed head
- run a bounded canary with at most one eligible non-legal question
- verify no Official Core field changed
- verify review/hold routes do not publish candidate enrichment

## Explicitly not included

- no Supabase migration application
- no Edge Function deployment
- no cron/schedule change
- no automatic publication of legal-risk questions
- no change to Official Core, answers, accepted answers, or grading semantics
- no activation of Draft PR #360
