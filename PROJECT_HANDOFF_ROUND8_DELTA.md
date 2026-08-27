# SWSI Round 8 handoff delta — 2026-08-27

This file supplements `PROJECT_HANDOFF.md`, whose section 8 still describes the pre-patch state. Read both files; for Round 8 frontend/code-health status, this delta is newer and wins on conflicts.

## Current branch and release safety

- Working branch: `fix/code-health-p0-20260826`.
- `main` was safely incorporated earlier with a non-force merge; do not rewrite history.
- Do not deploy Netlify production unless the user explicitly asks.
- Keep changes atomic; after each independently verifiable group, commit and run the relevant Actions gates.

## P1-7 runtime ownership consolidation completed

The following formerly layered runtime ownership has been reduced and regression-locked:

- `renderHome`: final canonical owner is `20.product-philosophy.part`. The learning-loop and final-runtime wrappers were removed without changing the home round contract.
- `normalize`: final owner is `00.part` only.
- grading helpers `gradingMode / isCorrectAnswer / answerLabel`: final canonical owner is `00.part`. `zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part` no longer redefines them.
- `code_health_p0.part` intentionally retains only the late fail-closed edge guards needed for invalid `acceptedAnswers()` and invalid-question rendering.
- Current monthly patch parts contain no legacy `SWSI_ANY_ANSWER_LEGACY_IDS` inference and no `/一律給分|送分/` answer-text inference.
- `runAIFeedback` and `gradePhoto`: the superseded implementations were removed from `99_p0_mobile_ai_guardrails.part`. Final execution ownership is now `00.part -> 99z.essay-trust-layer.part`.
- `99_p0_mobile_ai_guardrails.part` remains intentionally responsible for mobile/privacy/cache/timeout helpers such as `effectiveEssayLength`, `swsiSetAIBusy`, AI cache helpers and `swsiFetchWithTimeout`.

## Deliberate owners — do not collapse just to reduce owner count

- `renderReview`: `00.part -> 70.learning-loop.part` is deliberate. `70.learning-loop.part` is a full product-level review implementation (wrong-cause grouping, spaced review, weak-topic grouping, re-practice sets), not a small shim.
- MK: `zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part` is the single canonical MK owner. Earlier diagnostics showing the same file twice were a regex false positive caused by matching the suffix of `legacyMK=`; matcher fixed in `8407aa6`.
- `zzzzzzzzzzzzzzzzzzzzzzzzzz_mk_record_policy.part` intentionally owns `swsiShouldRecordMockAnswer`.

## Key commits in this continuation

- `3e9281b` — consolidate normalize ownership to `00.part`.
- `17d5c5f` — regression-lock invalid `acceptedAnswers()` behavior.
- `bd65696` — expose legacy grading inference owners in Runtime Owner QA.
- `ab6d42e` — make base grading helpers canonical owners.
- `2d0e485` — remove superseded AI feedback/photo grading owners from `99_p0_mobile_ai_guardrails.part`.
- `8407aa6` — fix MK owner matcher and prove MK has one canonical owner.

## Latest verified gates

For `ab6d42e` grading consolidation: Runtime Owner QA, Monthly Frontend static + Chromium interaction, Cloudflare Preview, Knowledge Runtime Snapshot, and Storage Durability all succeeded.

For `2d0e485` AI ownership consolidation: Runtime Owner QA #11, Cloudflare Frontend Preview #105, Monthly Frontend QA #125 (including Chromium interaction), Knowledge Runtime Snapshot #27, and Storage Durability QA #35 all succeeded.

For `8407aa6`: Runtime Owner QA #12 succeeded.

## Current next step

Continue P1 code-health only by inspecting remaining late overrides and separating deliberate product owners from removable shims. Do not re-open the completed `renderHome`, `normalize`, grading, or AI-feedback ownership work unless a regression gate fails. Do not treat `renderReview` or MK as debt merely because they are late owners.
