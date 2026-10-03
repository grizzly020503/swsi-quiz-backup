# Historical Law Student Surface — 2026-10-03

## Scope

This surface shows only historical-law verification metadata that has passed one of the repo's two explicit evidence methods. It does **not** create a second historical-law engine and does **not** claim that the full law-question corpus has been historically verified.

Authoritative verified evidence for this slice is now a deterministic union:

- 13 × `machine_verified_historical_v1`
- 6 × `evidence_adjudicated_historical_v1`
- **19 verified records total**

The 13 machine records remain in `data/historical_law_verified_priority10.v1.json`. The six evidence-adjudicated records are replayed from `data/historical_law_evidence_adjudication.v1.json` + the durable minimized evidence snapshot + current tracked question data. Stage 6 thresholds are not lowered.

## Student wording boundary

Both methods may show the shared conclusion:

- `考試當時法規版本已核對`
- law name and article
- exam session
- selected official version date / effective date
- official link to the selected MOJ law version
- official MOJ law-history link
- MOEX exam-date source link

But the method must stay visible and distinct:

- machine high-confidence record → `核對方式：規則驗證`
- evidence-adjudicated record → `核對方式：官方證據交叉核對`

The evidence-adjudicated copy explains that the record was held when automatic comparison confidence was insufficient and was only surfaced after the exam-time law text, official answer and selected answer option were cross-checked. It does not call this human/owner review and does not call it an MOEX official explanation.

## Data minimization

The student runtime map intentionally does **not** embed:

- historical article full text
- historical article SHA-256
- semantic similarity scores / Stage 6 diagnostics
- internal verification-basis text
- evidence-adjudication provenance payload
- question stem/options/official answer or other Official Core fields

Those stay in the evidence layer. The browser receives only the compact metadata needed to explain the historical version and link to official sources.

## Deterministic synchronization

`scripts/historical_law_student_surface_sync.py` rebuilds the compact 19-record projection from the authoritative evidence chain. It owns synchronization of the private `HISTORICAL_VERIFIED` map inside `86.law-trust-ui.part`.

`--check` is part of Progressive Explanation QA. Therefore:

- a verified-registry/evidence change without a synchronized student map fails CI;
- an unknown verification level fails closed;
- duplicate question IDs fail closed;
- evidence internals cannot silently leak into the browser map.

## Runtime trust boundary

The existing `86.law-trust-ui.part` remains the only historical-law student presentation owner. No new runtime part or `window.*` global is added. The existing no-network/no-storage boundary remains:

- no historical-law `fetch()` path;
- no `localStorage.setItem` / `sessionStorage.setItem` side effect;
- no historical full-text/hash payload in the browser.

A question outside the 19 verified records receives **no** `考試當時法規版本已核對` claim.

## Remaining P1-5 boundary

19 verified records still do **not** equal full historical-law coverage. Remaining work is broader high-risk law-question verification and, where evidence exists, clearer current-law vs exam-time-law differences. Until a question has one of the two accepted verified evidence methods, the UI must not invent a historical version.

## Related

- Issue #307 P1-5
- Issue #261 P1-B
- PR #313 (initial 13-record student surface)
- PR #319 (six durable evidence-adjudicated records)
- `PROJECT_DIARY_2026-10-02_HISTORICAL_LAW_E2E.md`
