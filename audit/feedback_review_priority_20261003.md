# Feedback review-priority closeout slice — 2026-10-03

Scope: #307 P1-4 / #261 feedback-to-review-priority evidence.

## Live production observation (read-only, count-only)

Supabase project: `Swsi` (`yumjtrdctaxyczpspuyo`).

Observed on 2026-10-03 without mutating production:
- active Edge Functions: no dedicated feedback-triage worker is deployed;
- `cron.job` entries matching feedback: `0`;
- `public.swsi_feedback_reports`: `2` total rows;
- rows with existing `metadata.triage`: `1`;
- pending rows: `0`;
- fixed rows: `1`;
- no-change rows: `1`;
- latest report timestamp: 2026-09-03 13:48:41 UTC;
- latest persisted triage timestamp: 2026-09-03 14:25:03 UTC.

This proves historical triage metadata exists, but does **not** prove an hourly triage worker is currently active. Older handoff text saying feedback triage was enabled hourly must therefore not be used as current-state evidence.

No report body, contact detail, user-agent, client identifier, or other private payload is copied into this audit.

## Safe fallback added in this slice

`swsi-admin` already clusters actionable feedback but previously assigned reports without persisted triage metadata to `untriaged`, which sorted them after high/medium/low groups.

The new fallback derives only review priority from the existing fixed `category` field:

| Category | Derived priority | Action |
| --- | --- | --- |
| `answer_question` | high | `needs_review` |
| `law_outdated` | high | `needs_review` |
| `question_display` | medium | `needs_review` |
| `explanation_error` | medium | `needs_review` |
| `theory_question` | medium | `needs_review` |
| `site_bug` | medium | `needs_review` |
| `ai_feedback` | medium | `needs_review` |
| `suggestion` | medium | `needs_review` |
| `other` / unknown | untriaged | `pending_triage` |

Conservative choices are intentional. Broad categories are not silently downgraded to low risk merely to reduce the queue.

## Trust and authority boundaries

- persisted `metadata.triage.risk_level` remains authoritative when present;
- the fallback does not write `swsi_feedback_reports`;
- it does not change report status;
- it does not create GitHub Issues or PRs;
- it cannot merge, deploy, mutate Official Core, or modify grading/law data;
- free-form report text is deliberately ignored by the classifier, so untrusted learner prose cannot instruct or steer priority logic;
- admin authentication / membership / service-role handling is unchanged.

## Production activation boundary

This repo change is **not** a production Edge Function deployment. Until `swsi-admin` is explicitly released and live source is re-verified, production still uses its currently deployed version and the fallback must be described as `release-ready`, not `active`.

A future production release must re-read the deployed function version/source, deploy through the existing authorized release path, and verify that admin feedback clusters show derived priority only for reports lacking persisted triage metadata. No new feedback cron or wider credential scope is required for this fallback design.
