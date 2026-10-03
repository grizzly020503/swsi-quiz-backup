# AI law metadata provenance guard — 2026-10-03

## Why this exists

The 4,800-question Official Core is structurally clean, but the optional `law`
enrichment field can currently be filled by the general AI analyzer without a
semantic source gate. That allowed useful-looking but unsupported metadata such
as `DS-115-2-039 -> 社會工作師法` even though the official disaster-response
question/options never name that law.

This is an enrichment-quality problem, **not** an Official Core problem.

## Read-only production dry run

Using the existing production function `extract_legal_canonical_names()` and
only official `question + opt_a..opt_d` as source evidence, current non-empty
`law` rows split as follows:

| provenance result | ready | review |
| --- | ---: | ---: |
| canonical law is explicitly present in official question/options | 462 | 4 |
| canonical law exists only in generated `law`, not official question/options | 150 | 1 |
| generated `law` cannot be canonicalized by the existing registry | 31 | 0 |

So a retrospective hard cleanup would touch 181 `ready` rows. That would be too
broad: this set mixes genuine but inferred learning extensions with wrong or
vague metadata. **This change therefore does not backfill or bulk-delete legacy
rows.** Legacy cleanup remains a separate evidence-adjudication task.

## Contract introduced by this change

For future ordinary generated explanations (`analysis_status = ready` and legal
status not evidence-backed):

1. `law` is optional.
2. A non-empty `law` must canonicalize through the existing database function.
3. Every canonical law claimed by `law` must also be explicitly present in the
   immutable official question/options.
4. If either condition fails, the database drops only `law`; the rest of the
   explanation stays ready.
5. `legal_canonical_names` is recalculated from official text so a removed AI law
   cannot leave stale canonical metadata behind.
6. `verified_current` / `changed` are not silently stripped because those states
   belong to a separate evidence-backed legal review lifecycle.

This intentionally favors precision over automatic law coverage. A separate
law-enrichment pipeline with official evidence may later add a useful legal
extension that the exam stem did not explicitly name.

## What this does NOT mean

- A canonical name appearing in an option is **not** proof that the law is the
  correct answer basis; it may be a distractor.
- `legal_canonical_names` is an impact/reference index, not a trust label.
- A resolved `legal_watch_hits` event is not proof that the entire question is
  `verified_current`.
- Existing 181 legacy candidates are not automatically wrong and are not changed
  by this migration.
- Official question text, options, answers and grading metadata are untouched.

## Follow-up after the guard is proven

1. Separately correct the nine over-broad `verified_current` rows whose current
   provenance only records resolution of the 2026-08-17 Civil Code Article 1223
   watch event.
2. Adjudicate legacy law-only / non-canonical rows in small evidence-backed
   batches, starting with known 115-2 defects.
3. Regenerate question shards whenever production enrichment data is corrected,
   so DB and student runtime cannot drift.
4. Keep historical-law verification separate from current-law watch state.
