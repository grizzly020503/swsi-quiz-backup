# SWSI Project Diary — 2026-10-01

> Purpose: preserve the actual release/data-quality state for the next AI/maintainer. This is a factual work log, not a product-completion claim.

## 1. Release backlog cleared

### Merged / integrated
- #188 — Netlify verifier zero-feed-error handling.
- #192 — clean integration replacing stale stacked current-affairs PRs #179 / #182 / #185 / #189.
  - kept current live monitoring snapshots instead of blindly merging stale tracked JSON.
  - preserved social-work-management knowledge hierarchy, primary/supporting exam-subject axes and media-event filtering.
- #194 — clean integration of the reviewed #190 current-affairs semantics fixes.
  - `條例` mention alone no longer implies a law amendment.
  - generic `退休` wording no longer creates pension-history matches.
  - serious events with low policy-change signal are no longer mislabeled as mere promotion/activity noise.
- #191 — 86 conservative law-question metadata mappings across 10 priority statutes.
  - mapping strength remains `metadata_only`.
  - historical verification remains false.
- #196 + #200 — historical-law provenance V1 and parser/schema hardening.
- #202 — materialized live priority-law provenance baseline + permanent report contract.

### Superseded PRs closed, not merged
- #179 / #182 / #185 / #189: superseded by #192.
- #198: superseded by #202 after #200 hardened the parser.

## 2. Current-affairs release findings

### Deterministic trend bug found and fixed
The PR deterministic rebuild gate was not actually deterministic because the trend builder used wall-clock `datetime.now()` for recency/cooling. A snapshot built on 2026-09-26 could therefore fail a 2026-10-01 rebuild even when source data had not changed.

Resolution:
- PR-time rebuilds are anchored to tracked snapshot time.
- production/live rebuilds continue to use real current time.
- deterministic Public Monitoring gate subsequently passed.

### Fresh live monitoring result after integration
Observed during the Oct 1 release path:
- 23 / 23 configured sources healthy.
- 1,051 raw feed items scanned.
- 6 accepted current-affairs items/events after filtering.
- feed error count = 0.
- 4,800 historical questions available for history linkage.
- event/trend knowledge contracts passed.

Do not treat these numbers as permanent product constants; they describe that live run.

## 3. Historical-law provenance baseline

### Priority-law mapping layer
`data/law_question_links_priority10.v1.json`
- 10 priority laws.
- 86 law-question mappings.
- 85 unique questions.
- one intentional cross-law overlap: `SP104-2-10` appears in two law mappings.
- no keyword-only stem matches are promoted to law links.
- official answers / grading modes remain protected question-bank data.

### Historical provenance V1
Files now include:
- `scripts/historical_law_provenance.py`
- `scripts/historical_law_provenance_selftest.py`
- `scripts/build_historical_law_provenance_report.py`
- `scripts/historical_law_provenance_report_smoke.py`
- `data/historical_law_provenance_priority10.v1.json`
- `.github/workflows/historical-law-provenance-qa.yml`

Current committed triage baseline:
- 86 mappings total.
- 76 `article_resolution_required`.
- 4 `current_text_equals_exam_year_candidate`.
- 6 `effective_date_review`.
- every row still has `historical_version_checked = false`.

Interpretation:
- `article_resolution_required`: question/law metadata is known, but the stem does not state a sufficiently explicit article number. Do NOT infer a verified article merely from keywords.
- `current_text_equals_exam_year_candidate`: machine triage sees no later relevant amendment and no special effective-date issue; this is only a stage-2 candidate, NOT verified historical law.
- `effective_date_review`: official history includes delayed/special effective-date language; exact legal effect must be checked before verification.

### MOJ source instability observed
MOJ `LawHistory` pages were intermittently unreadable/unrecognized for different statutes across repeated live runs. Retry + per-law fail-closed behavior was added so one source anomaly does not erase the rest of the report.

Important rule:
- source-read failure is an observation error, never evidence that a law/version did not exist.
- source errors must remain visible in the report and must never upgrade trust.

## 4. Frontend / code-health findings to continue

These items were audited on Oct 1 and must remain visible until actually remediated.

### A. Late override / patch-stack debt
Current frontend still contains legacy-core + later-patch behavior. Historically some runtime ownership depended on lexical load order and `zzz...` style late overrides.

Required direction:
- do not add new `zzz` / late-override layers.
- keep runtime-owner smoke/gates.
- migrate one bounded owner at a time into explicit modules.
- never do a big-bang rewrite while students are using production.

### B. Multiple runtime owners / lexical ordering
Some frontend functions or state have existed in more than one layer, with the later-loaded definition winning.

Required direction:
- one canonical owner per behavior.
- regression test behavior before extracting each owner.
- remove superseded owner only after parity is proven.

### C. Dynamic `innerHTML` / Stored-XSS surface
Historical frontend code uses dynamic `innerHTML` in multiple places. Existing XSS audits/gates reduce risk, but this remains a structural attack surface.

Required direction:
- use `textContent` / DOM construction for plain text.
- use context-aware escaping for the few places that truly require HTML.
- validate/sanitize URL-bearing attributes separately; escaping HTML text is not sufficient for URLs.
- prioritize user-controlled / DB-controlled / AI-controlled fields before static trusted markup.

### D. `window.xxx` global state / functions
The app still exposes multiple `window.*` functions/state objects. This increases collision risk as patch layers grow.

Required direction:
- do not expand the global namespace for new work.
- move bounded domains behind modules/namespaces as owners are consolidated.
- retain small compatibility bridges only while old callers exist.

### E. Dangerous-code / secret spot check
Oct 1 audit found no evidence of:
- `eval()`-based arbitrary external-code execution.
- obvious hardcoded production service-role key/private key.
- obvious mining/backdoor/exfiltration code.

Existing repo secret scanning and environment-variable based service-role access should remain enforced.

This does NOT mean security review is permanently complete; it records what was checked in this audit.

## 5. CI / Actions lessons from this release

- A workflow run with zero steps / missing logs was previously an Actions quota/infrastructure symptom, not a test failure.
- After Oct 1 quota reset, real gates produced normal steps/logs and were treated as authoritative.
- Re-running an old PR workflow can test the old merge snapshot rather than the latest branch head; do not use an old rerun as proof of a new fix.
- API commits may not trigger recursive GitHub Actions. Close → reopen can create a fresh pull-request check suite when the PR is mergeable.
- bot-written main snapshots frequently move `main`; use a fresh integration branch rather than manually choosing ours/theirs for monitored JSON.
- use `expected_head_sha` when merging reviewed PRs.
- temporary write workflows used only to materialize data must be removed before final merge.

## 6. Next data-quality work

Priority order after this diary:
1. Stage-2 article resolution for the 76 `article_resolution_required` mappings.
   - AI may suggest candidate articles, but may not mark them verified.
   - official legal text/history evidence must corroborate the candidate.
2. Exact effective-date handling for the 6 `effective_date_review` mappings.
3. Source compatibility/fallback for intermittently unreadable MOJ LawHistory pages.
4. Integrate the historical-law exception categories into Data Guardian / human exception queue.
5. Continue existing review queue, especially social policy/legislation and remaining 115-2 enrichment.
6. Gradual frontend de-patching / runtime-owner consolidation / XSS surface reduction.

## 7. Product boundary

SWSI should not become more complex on the student surface just because the backend becomes more capable.

Long-term direction:
- backend keeps full historical bank and provenance.
- student practice can expose simple modes such as `推薦練習 / 近五年 / 全部歷屆`.
- recommendation weighting may use recency, current exam regime, topic frequency, user weakness, spacing, legal validity, verification level and prior exposure.
- do not delete old questions merely because newer years accumulate.

## 8. Trust statement

As of this diary:
- official question/answer integrity remains a separate protected layer.
- a generated explanation marked `ready` is not automatically human-verified.
- `metadata_only` is not historical-law verification.
- `current_text_equals_exam_year_candidate` is not historical-law verification.
- the platform should prefer a visible exception queue over silently manufacturing certainty.
