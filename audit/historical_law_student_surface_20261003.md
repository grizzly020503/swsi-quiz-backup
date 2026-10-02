# Historical Law Student Surface — 2026-10-03

## Scope

This change surfaces the repo's existing historical-law verification evidence in the student quiz explanation UI. It does **not** create a second historical-law engine and does **not** claim that the full law-question corpus has been historically verified.

Authoritative derived registry for this slice:

- `data/historical_law_verified_priority10.v1.json`
- current verified records: **13**
- required level: `machine_verified_historical_v1`
- required flag: `historical_version_checked=true`

Only records satisfying both conditions may receive the student-facing historical-law panel.

## Student wording boundary

For an eligible question the existing quiz trust disclosure may show:

- `考試當時法規版本已核對`
- law name and article
- exam session
- selected official version date / effective date
- official link to the selected MOJ law version
- official MOJ law-history link
- MOEX exam-date source link

The panel explicitly says this is SWSI machine-verified metadata and **not** an MOEX official explanation. It also warns against using the 2026 current law as proof of an older exam answer.

## Data minimization

The student runtime map intentionally does **not** embed:

- historical article full text
- historical article SHA-256
- semantic similarity scores
- internal verification-basis text
- Guardian / review diagnostics

Those remain evidence-layer data. The student surface carries only the minimum metadata needed to explain the historical version and link back to official sources.

## Fail-closed behavior

`historical_law_student_surface_contract.py` requires the embedded runtime map to exactly match the compact projection of the verified registry. A registry change without a synchronized student projection therefore fails PR QA rather than silently presenting stale verification status.

A question not present in the verified registry receives **no** `考試當時法規版本已核對` claim.

## Existing systems reused

- historical-law Stage 1–7 / Guardian evidence stays the source of truth;
- existing `86.law-trust-ui.part` remains the law presentation owner;
- existing P1-4 `.swsi-answer-trust` disclosure remains the quiz trust container;
- current `legal_status` continues to describe current-law review state.

No new database, runtime part, AI call, network fetch, storage write, production migration, or production deploy is introduced by this slice.

## Remaining P1-5 boundary

This slice is **not** enough to mark all historical-law work complete. Remaining work includes broader high-risk law-question coverage and student-visible current-vs-exam-time differences where evidence exists. Until a question has the required historical evidence, the UI must keep the lower-confidence/current-law wording and must not invent a historical version.

## Related

- Issue #307 P1-5
- Issue #261 P1-B
- `PROJECT_DIARY_2026-10-02_HISTORICAL_LAW_E2E.md`
