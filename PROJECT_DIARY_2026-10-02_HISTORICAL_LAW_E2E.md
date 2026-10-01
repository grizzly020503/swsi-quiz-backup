# SWSI Project Diary — 2026-10-02 Historical-Law E2E Production Handoff

> **READ THIS BEFORE TOUCHING HISTORICAL-LAW QA / GUARDIAN.**
>
> Do not trust any SHA below as permanently current. Always re-read `main`, open PRs, current workflow runs, and this diary before making changes. Multiple AI/automation workers may push concurrently.

## Final production state

The historical-law pipeline is no longer the old repeated-fetch Stage 1→6 chain.

Current production architecture:

1. **Stage 2** pins exact exam dates and produces a hash-bound MOJ `LawHistory` snapshot.
2. **MOJ Open API** downloads the official current Chinese law/order corpus and persists target-only current-law snapshots.
3. **Stage 3** resolves article candidates and preserves shadow calibration / false-machine controls.
4. **Stage 4 hybrid evidence**:
   - current selected versions use **official MOJ Open API** snapshots;
   - historical selected versions use strict **MOJ `LawOldVer` HTML identity validation**;
   - accepted evidence is stored as hash-bound all-article snapshots.
5. **Stage 5** applies the promotion contract.
6. **Stage 6** performs semantic reranking from the exact Stage 4 snapshot and makes **no second MOJ network fetch**.
7. **Data Guardian** consumes the `historical-law-stage2-6-live-evidence` artifact and treats Stage 6 as authoritative for promotion/review/source-routing decisions.

The superseded standalone snapshot pilot workflow has been removed. The consolidated production workflow is:

- `.github/workflows/historical-law-stage1-6-qa.yml`
- `.github/workflows/historical-law-guardian-routing-qa.yml`

## Why the architecture changed

Repeated MOJ HTML requests were unstable. MOJ sometimes returned HTTP 200 pages whose HTML was actually an error page (`<title>Error</title>`, `Unreachable Server`). This produced false source-identity mismatches when Stage 4 and Stage 6 fetched the same source seconds apart.

**Do not fix this by weakening source identity checks.**

The production fix is evidence handoff:

- fetch/verify source evidence once at the owning stage;
- bind evidence with hashes;
- pass the verified snapshot downstream;
- downstream stages recompute identity/hash contracts and fail closed on mismatch.

## Source identity rules — do not regress

### Current law versions

Use official MOJ Open API target snapshots.

Stage 6 verifies, among other things:

- Stage 4 / Stage 5 selected URL agreement;
- selected version `kind == current`;
- official MOJ API endpoint;
- PCode identity;
- aggregate article hash;
- per-article hashes;
- target article fingerprint;
- Stage 4 row / snapshot source identity method agreement;
- re-derived `snapshot_id`.

### Historical versions

Use official MOJ `LawOldVer` HTML only after strict page identity validation.

Stage 6 verifies:

- Stage 4 / Stage 5 selected URL and version-kind agreement;
- selected version `kind == oldver`;
- official source URL;
- page SHA-256;
- aggregate evidence SHA-256;
- per-article hashes;
- target article fingerprint;
- re-derived `snapshot_id = sha256(URL + newline + page_sha256)`.

A missing/tampered/mismatched snapshot must fail closed.

## Protected trust boundary

These fields are protected and must never be modified by historical-law QA automation:

- `stem`
- `options`
- `official_answer`
- `accepted_answers`
- `grading_mode`

Also:

- never auto-write `historical_version_checked = true`;
- current workflows assert `historical_version_checked_count == 0`;
- evidence and Guardian outputs are read-only QA/routing artifacts.

## Important merged PRs

- **#217** — harden Stage 6 source identity using Stage 4 article fingerprints.
- **#218** — add Data Guardian routing over existing Stage 1–6 artifact.
- **#220** — make Stage 6 authoritative for Guardian routing.
- **#222** — verified Stage 4→Stage 6 hybrid snapshot handoff; current laws via MOJ Open API, historical versions via strict `LawOldVer` HTML.
- **#223** — promote hybrid evidence handoff into consolidated production Stage 1–6 workflow.
- **#224** — remove superseded standalone snapshot pilot workflow.
- **#226** — make Stage 1–6 / Guardian contracts data-driven and scalable; add byte-identical Stage 6 check and final routable-evidence gate.
- **#227** — validation-only post-#226 E2E trigger; closed without merge after successful Stage 1–6 → Guardian verification.

Current known production merge at the time of writing: `7ab974d36f6dd4d6326b48f9755b119feffd22df` (#226). Re-read `main` before using it.

## Latest verified live baseline

Post-#226 validation used Stage 1–6 run `36896323252`, followed by Guardian `workflow_run` `36896441959`.

Stage 1–6 live result:

- Stage 2 mappings: **86**
- unique questions: **85**
- MOJ history snapshots: **10 ready / 0 source failure**
- MOJ Open API targets: **10 ready / 0 not found**
- Stage 3 routes: **57 AI review / 19 machine candidate**
- explicit controls: **9/10 top-1, 9/10 top-3, 0 false-machine candidate**
- Stage 4: **19/19 historical text evidence ready**
  - **15** current-law snapshots via `moj_open_api_current`
  - **4** historical snapshots via `stage4_moj_title`
  - **3** unique historical full-text URLs
  - **4** historical full-text HTTP requests total
- Stage 5: **19 promotion candidates**
- Stage 6: **13 `historical_semantic_confirmed` + 6 `historical_semantic_support` + 0 conflict**
- Stage 6 ran twice and outputs were byte-identical.
- Final `Require routable Stage 2-6 evidence` gate succeeded.

Guardian E2E result:

- mappings: **86**
- unique questions: **85**
- lanes:
  - `machine_promotion`: **13**
  - `ai_semantic_review`: **6**
  - `ai_article_review`: **57**
  - `effective_date_resolution`: **6**
  - `machine_direct_source_check`: **4**
  - `human_review`: **0**
- priority counts:
  - high: **9**
  - normal: **60**
  - low: **17**
- `historical_version_checked_count`: **0**

Stage 6 authority held exactly:

- Stage 6 confirmed **13** → Guardian machine promotion **13**
- Stage 6 support **6** → Guardian AI semantic review **6**
- Stage 6 conflict **0** → Guardian human review **0**

## Scalability changes in #226

Do not reintroduce pilot-era fixed cardinality assertions such as hard-coded `86 / 85 / 10 / 19 / 15` as production invariants.

Production QA now derives:

- mapping count from current evidence;
- unique-question count from current question IDs;
- control count from current Stage 3 controls;
- API target count from current probe output;
- Stage 4/5/6 relationships from their upstream artifacts;
- Guardian mapping/unique counts from Stage 2 evidence.

The current 86/85/10/19/15 numbers above are a **verified baseline**, not permanent schema constants.

## Production success semantics

Live source steps keep `continue-on-error` so partial diagnostics/artifacts can still be uploaded when an upstream source fails.

However, the consolidated Stage 1–6 workflow now has a final routable-evidence gate. The workflow may only conclude successfully for Guardian routing when:

- Stage 2 outcome = success
- MOJ API outcome = success
- Stage 3 outcome = success
- Stage 4 outcome = success
- Stage 5 outcome = success
- Stage 6 outcome = success
- required Stage 2–6 JSON evidence files exist and parse.

This prevents a half-complete source run from looking routable.

## Guardian contract

Guardian is Stage 6 authoritative for Stage 5 promotion candidates:

- `historical_semantic_confirmed` → `machine_promotion`
- `historical_semantic_support` → `ai_semantic_review`
- `historical_semantic_conflict` → `human_review`
- Stage 6 source failures / identity mismatches / unavailable historical articles → source retry / fail-closed path

Stage 3 AI review, direct-source checks, and effective-date resolution remain separate lanes.

## Files added/used by the hybrid chain

Key scripts:

- `scripts/historical_law_stage2_history_snapshot.py`
- `scripts/historical_law_moj_api_probe.py`
- `scripts/historical_law_stage4_snapshot_runner.py`
- `scripts/historical_law_stage6_snapshot_semantic.py`
- `scripts/historical_law_snapshot_pipeline_selftest.py`
- `scripts/historical_law_guardian_queue.py`
- `scripts/historical_law_guardian_queue_selftest.py`

Key runtime evidence:

- `auto/qa/historical_law_exam_date_stage2.v1.json`
- `auto/qa/historical_law_history_snapshot.v1.json`
- `auto/qa/historical_law_moj_api_probe.v1.json`
- `auto/qa/historical_law_moj_api_targets.v1.json`
- `auto/qa/historical_law_article_stage3.v1.json`
- `auto/qa/historical_law_oldver_stage4.v1.json`
- `auto/qa/historical_law_stage5_promotion.v1.json`
- `auto/qa/historical_law_stage6_semantic.v1.json`
- `auto/qa/historical_law_guardian_queue.v1.json`

## Operational notes

- MOJ Open API corpus download can take roughly tens of seconds to more than a minute on GitHub runners. Do not interpret that by itself as a stuck job.
- The Open API publishes the current corpus only; historical versions still require the old-version source path unless a verified official historical API becomes available.
- Do not re-add a second MOJ fetch in Stage 6.
- Do not weaken identity validation merely to make intermittent MOJ pages pass.
- Do not merge validation-only PRs that only exist to trigger workflows.
- Use `expected_head_sha` when merging because concurrent AI/automation may move the PR head.
- Re-read `main`, open PRs, and latest Actions before any write.

## Next useful work

Historical-law transport/routing is now production-stable enough to stop adding architecture for architecture's sake.

Next priorities should return to the broader data-quality plan unless a real regression appears:

1. Continue MCQ analysis/review cleanup, especially social policy / social legislation.
2. Finish remaining 115-2 essay enrichment and verification layers.
3. Continue student-law-card coverage for high-frequency laws; legal watch coverage is not the same as student teaching coverage.
4. Continue current-affairs semantic quality: event importance, subject primary/supporting classification, law links, historical-question evidence.
5. Keep historical-law pipeline as a monitored foundation; fix only evidence-backed failures.

Do not turn this completed transport layer into an endless refactor project.
