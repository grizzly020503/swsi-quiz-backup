# SWSI Architecture Map

> Purpose: make the system understandable to a maintainer who did not build it. Read this before changing runtime ownership, grading, deployment, Auth, or data contracts.

## 1. Product north star

SWSI exists to let people prepare for Taiwan's social-worker national exam for free, publicly, and with low friction.

Student core:

`practice -> explanation -> wrong-answer/review -> weak points -> essay -> optional AI feedback`

AI, Admin, feedback triage, hosted CI, and MOEX automation are enhancement/maintenance layers. They must degrade without taking the student core down.

## 2. High-level topology

```text
Browser / PWA
  |
  +-- static student app (Netlify build artifact)
  |     |
  |     +-- official question shards / manifest
  |     +-- local-first study state
  |
  +-- Cloudflare Worker
  |     +-- AI proxy / quota / request guardrails
  |
  +-- Supabase
        +-- Auth
        +-- production data
        +-- Admin / Feedback Edge Functions
```

GitHub is the source repository and review/QA control plane. Netlify production deployment and other high-impact production actions remain human-approved.

## 3. Student front-end build model

The front end is intentionally transitional rather than a modern component rewrite.

```text
legacy index.html
  |
  +-- scripts/monthly_patch_build.py exact/fail-closed transforms
  |
  +-- monthly_patch_parts/*.part
        concatenated in lexical filename order
        -> _site/monthly_patch.js
  |
  +-- public-content sanitizer / static QA / runtime-owner QA
  |
  -> deployable _site
```

**Important:** filename order is runtime order. Renaming a `.part` file can change behavior even if its contents do not change.

The current `.part` layout contains historical late layers. They are grandfathered because several now have deliberate, regression-tested responsibilities. Do not rename them just to make the tree look cleaner.

## 4. Current runtime ownership map

This is a navigation map, not permission to refactor broadly.

| Area | Primary / deliberate owner |
| --- | --- |
| Base runtime, normalize, grading helpers | `monthly_patch_parts/00.part` |
| Layout foundation | `15.layout-foundation.part` |
| Home product surface | `20.product-philosophy.part` |
| Focused quiz presentation | `30.focused-quiz-style.part` |
| Mobile reading | `40.mobile-reading-polish.part` |
| Storage durability | `60.storage-durability.part` |
| Review / progress learning loop | `70.learning-loop.part` |
| Learning Center | `71.my-learning-center.part` |
| Launch guidance / countdown | `73.launch-guidance-countdown.part` |
| Knowledge path | `80.knowledge-path.part` |
| Law trust presentation | `86.law-trust-ui.part` |
| Theory trust presentation | `88.theory-trust-ui.part` |
| Public branding / platform info | `89.public-branding-info.part` |
| Feedback core/context/UI/error copy | `90` / `91` / `92` / `93` parts |
| Mobile AI client / timeout / busy utilities | `99_p0_mobile_ai_guardrails.part` |
| Essay AI trust/privacy/error boundary | `99z.essay-trust-layer.part` |
| Essay navigation | `zzz_fix_essay_navigation.part` |
| Quick essay scope | `zzzzz_quick_essay_scope_fix.part` |
| Learning direct route | `zzzzzz_learning-center-direct-route.part` |
| Invalid grading/render fail-closed guards | `zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part` |
| Mock record policy | `zzzzzzzzzzzzzzzzzzzzzzzzzz_mk_record_policy.part` |
| Mock grading contract | `zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part` |
| Complete-question-bank invariant | `zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_question_bank_invariant.part` |

Exact ownership chains are enforced by `scripts/runtime_owner_smoke.js`. If this table and the smoke test disagree, stop and re-read the actual runtime before changing code.

## 5. Question and grading data

Production historical invariant:

- 4,800 official choice questions.
- 24 multi-answer questions.
- 4,784 `standard`.
- 12 `all_credit`.
- 4 `any_answer`.

The official grading contract is data, not UI copy. Never infer special grading from strings such as `一律給分`.

High-impact grading fields include:

- official answer
- `accepted_answers`
- `grading_mode`

Changes to them require explicit human approval plus the relevant grading/integrity QA.

## 6. Back-end boundaries

### Cloudflare Worker

`cloudflare/wandering-wave-4418/worker.js`

Responsibilities include the AI proxy and cost/abuse controls. Secrets stay server-side. The student core must remain usable when AI is unavailable.

### Supabase

Responsibilities include Auth, production data, Admin access and feedback operations. Service-role credentials never belong in browser code.

Tracked Edge Function source includes:

- `supabase/functions/swsi-admin/index.ts`
- `supabase/functions/swsi-feedback/index.ts`

## 7. Release and QA boundaries

Relevant guardrails include:

- `scripts/runtime_owner_smoke.js`
- `scripts/maintainability_smoke.py`
- grading contract / question shard integrity checks
- storage durability QA
- knowledge runtime snapshot QA
- browser interaction QA
- launch readiness QA
- secret/privacy build checks

A deploy succeeding is not equivalent to product verification.

## 8. Human-only decisions

AI or automation must not independently decide to:

- change official answers / accepted answers / grading mode;
- weaken Auth, authorization, RLS, security, secret handling or CORS;
- create or apply production migrations;
- expose or rotate production secrets without explicit instruction;
- merge `main`;
- deploy production.

## 9. How to make the codebase easier over time

The goal is **not** a big-bang rewrite.

Preferred direction:

1. identify the tested canonical owner;
2. add/strengthen regression evidence;
3. move behavior into that owner;
4. remove the obsolete wrapper/shim in the same bounded change;
5. keep the `.part` count flat or lower;
6. only then update the ownership map.

See `MAINTAINABILITY_POLICY.md` for the rules that prevent new historical layers from accumulating.
