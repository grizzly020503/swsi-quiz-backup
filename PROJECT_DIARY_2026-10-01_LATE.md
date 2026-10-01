# SWSI Project Diary — 2026-10-01 Late Update

> Continuation of `PROJECT_DIARY_2026-10-01.md`. This is a factual handoff record. Do not reinterpret source outages or intermediate evidence states as question errors.

## 1. Historical-law Stage 4 completed — official exam-date article text

### #210 merged
Merge commit: `e370f46427c681e242e67ed62c721281b2f4e17d`.

Stage 4 now performs:

`Stage 3 machine candidate -> target article -> official MOJ LawHistory -> article-scoped effective date -> official exam window -> MOJ LawOldVer/current full text -> exact target article -> SHA-256 fingerprint`.

Important implementation findings:
- MOJ `LawHistory.aspx` does not expose usable old-version links; official promulgation dates are used to derive `LawOldVer.aspx?pcode=...&lnndate=YYYYMMDD&lser=001` URLs.
- Effective dates are resolved per article, not per whole statute.
- administrative implementation-date announcements are treated as effective-date evidence, not new text versions.
- delayed/special effective-date rules remain fail-closed if not deterministically resolvable.
- historical MOJ pages can use `col-no` + `law-article` HTML blocks; Stage 4 has a historical-page fallback parser without changing the Stage 3 current-law parser.

Verified good live run before merge:
- Stage 3 machine candidates: 19.
- `historical_text_evidence_ready`: 19 / 19.
- every ready record had an official history URL, exact exam-date source URL, selected MOJ version URL and exact article SHA-256.
- `historical_version_checked_count = 0` at Stage 4.
- protected question core mutation count = 0.

## 2. Stage 5 promotion contract completed

### #211 merged
Merge commit: `e83c37734d985aee2fc64d2b9618ff3f5bdcd117`.

Stage 3 control questions now also run in a shadow mode with their explicit article reference removed. This tests whether the unknown-article routing thresholds would accidentally auto-route a known wrong result.

Latest good calibration:
- explicit controls: 10.
- top-1 article match: 9 / 10.
- top-3 article match: 9 / 10.
- shadow machine candidates: 7.
- **false machine candidates: 0**.

Stage 5 requires:
- zero false-machine shadow controls;
- Stage 3 high-confidence machine route;
- Stage 4 official historical-text evidence with SHA-256;
- article agreement and required provenance URLs.

Verified good live run:
- Stage 3 machine candidates: 19.
- Stage 4 ready: 19 / 19.
- Stage 5 `promotion_candidate`: 19 / 19.
- `historical_version_checked_count = 0` at Stage 5.

Stage 5 is still a promotion-candidate layer; it does not modify question data.

## 3. Stage 6 historical-text semantic cross-check

### #212 merged
Merge commit: `a9c3fb05f2e24cf11c60f0cd6305f2a0891163b1`.

Stage 6 independently re-ranks the original question stem plus all four answer-option texts against all articles in the exact historical MOJ version selected by Stage 4. It does not read the official answer.

Good live run before later source instability:
- Stage 5 promotion candidates: 19.
- `historical_semantic_confirmed`: 11.
- `historical_semantic_support`: 2.
- `source_identity_mismatch`: 6.
- `historical_semantic_conflict`: 0.
- question-shard errors: 0.

Interpretation:
- 11 had sufficiently strong top-1 historical-text agreement.
- 2 supported the same top article but did not meet the strongest machine-confirmation threshold.
- 6 were blocked by source-identity handling, not classified as semantic conflicts.
- 0 semantic conflicts were observed in that run.

Do not convert `historical_semantic_support` to verified automatically.

## 4. Historical-law Actions consolidation

### #215 merged
Merge commit: `11faf392a0a8889bf32fb80c1e616941678b2b1e`.

Before #215 the repo had four overlapping historical-law workflows that repeatedly rebuilt overlapping Stage 1/2/3, Stage 4, Stage 5 and Stage 6 evidence, increasing Actions usage and repeated MOJ traffic.

#215 replaced them with one:
- `.github/workflows/historical-law-stage1-6-qa.yml`

The single workflow preserves:
- Stage 1 V1 baseline/materialized contract.
- Stage 2 exact exam-date evidence.
- Stage 3 article candidate + zero-false-machine shadow calibration.
- Stage 4 exact official historical article fingerprint.
- Stage 5 promotion contract.
- Stage 6 historical-version semantic cross-check.
- protected-core AST trust boundary.
- one combined read-only evidence artifact.

The four superseded historical-law workflows were removed.

This is a CI/operations consolidation only; no question data or evidence algorithm was changed by #215.

## 5. Stage 7 verified metadata overlay

### #216 merged
Merge commit: `379e62ab68feb1608fb327050eb3816b4cda5cea`.

Stage 7 is the first layer permitted to emit `historical_version_checked = true`, and it does so **only inside a separate derived registry**:
- `data/historical_law_verified_priority10.v1.json`

It does NOT mutate:
- question shards;
- stems;
- options;
- official answers;
- accepted answers;
- grading modes.

Current committed verified registry:
- verified records: 11.
- `historical_version_checked = true`: 11.
- verification level: `machine_verified_historical_v1`.

Promotion basis:
- Stage 3 zero-false-machine calibration;
- Stage 4 official exam-date article fingerprint;
- Stage 6 historical-version semantic top-1 high-confidence confirmation.

The registry is monotonic:
- a source outage cannot delete an already verified record;
- article/fingerprint/selected-version evidence drift causes a conflict and fails closed instead of silently overwriting provenance.

Stage 7 has a separate deterministic QA workflow. It does not re-fetch MOJ and therefore does not recreate the former live-HTTP Actions duplication.

## 6. Stage 6 source-identity hardening

### #217 merged
Merge commit: `9b9cd7ccf7ee974f9a04c34fe210039dfec036e1`.

The six Stage 6 source-identity mismatches shared a suspicious pattern: Stage 4 had already successfully fingerprinted the selected official MOJ article, while Stage 6 re-fetched the same selected version and could reject the second response on a title-level identity check.

#217 keeps source verification fail-closed but strengthens it:
1. selected URL must be HTTPS on `law.moj.gov.tw` and use the official LawAll/LawOldVer path;
2. normal MOJ title identity remains accepted;
3. if the title check fails, Stage 6 may continue only if the exact target article can be parsed from that response and its SHA-256 exactly equals the independent Stage 4 fingerprint;
4. a missing article, wrong hash, non-MOJ URL or transport failure remains blocked.

Deterministic regression tests cover:
- official URL allowlist;
- Stage-4-fingerprint recovery;
- wrong-fingerprint rejection;
- non-MOJ URL rejection.

### Important live-source limitation after #217
Two immediate live reruns encountered a separate MOJ outage/availability problem:
- Stage 3 current-law fetch still succeeded with `law_source_error_count = 0`;
- Stage 4 historical-source fetch returned `source_failure` for all 19 candidates;
- Stage 5 therefore correctly blocked all 19;
- Stage 6 had zero promotion candidates to evaluate.

These runs were green because the system failed closed; they are **not evidence that the six previous mismatches have been live-resolved**.

Do not interpret the temporary Stage 4 source outage as invalid historical evidence or wrong questions. The earlier 19/19 Stage 4 evidence run remains an observed successful run, and the Stage 7 registry remains monotonic at 11 verified records until fresh evidence can safely add more.

## 7. Current historical-law state at this handoff

Priority-10 mapping population:
- 86 law-question mappings.
- 85 unique questions.
- 1 intentional cross-law overlap.

Stage 2 baseline:
- 76 article-resolution cases.
- 4 current-text/exam-date candidates.
- 6 effective-date review cases.

Stage 3:
- 19 machine candidates.
- 57 AI-review routes.
- 10 explicit controls.
- 0 false-machine control routes.

Stage 4:
- one verified-good run produced 19 / 19 official historical-text evidence records.

Stage 5:
- one verified-good run produced 19 / 19 promotion candidates.

Stage 6 good-run baseline:
- 11 confirmed.
- 2 support.
- 6 source-identity mismatch.
- 0 semantic conflict.

Stage 7 committed overlay:
- 11 verified historical-law metadata records.

Important: the 11 verified records are an overlay-level verification state, not a rewrite of official question-bank core data.

## 8. Next steps

1. When MOJ historical endpoints are healthy again, rerun the single Stage 1→6 chain and inspect #217 `source_identity_method_counts`.
2. Determine whether the prior six source-identity mismatches become:
   - semantic confirmed;
   - semantic support;
   - real semantic conflict;
   - or remain source failures.
3. Only Stage 6 `historical_semantic_confirmed` records may be considered for Stage 7 materialization under the current policy.
4. Never upgrade the two `historical_semantic_support` records solely because they rank top-1; they intentionally remain below the strongest machine-verification threshold.
5. Continue the remaining 57 Stage-3 AI-review cases through constrained evidence review; do not send all 57 directly to humans.
6. Continue the 6 effective-date review cases separately with exact legal-effect evidence.
7. Feed unresolved historical-law categories into Data Guardian / exception queues.
8. Keep frontend debt frozen by the existing z-layer, URL-safety and window-global inventory gates while data-quality automation continues.

## 9. Trust statement

At this handoff:
- official answer/grading data remains protected and is not used as a shortcut for historical-law inference;
- 11 records are machine-verified only in the dedicated historical-law metadata overlay;
- all other cases remain explicitly unverified or review-routed;
- source outages cannot create verification;
- evidence drift cannot silently overwrite an existing verified overlay record;
- AI suggestions remain subordinate to official-source, date/version and deterministic safety evidence.
