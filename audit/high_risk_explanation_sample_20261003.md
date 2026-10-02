# High-risk explanation review sample — 2026-10-03

Scope: #307 P1-4 / #261 P1-A content-quality closeout support.

## Purpose

Create one **bounded, deterministic and reproducible review sample** from the tracked 4,800-question official corpus so high-risk explanation review has a fixed denominator and does not depend on each reviewer manually choosing different examples.

This work selects a review queue. It does **not** certify the selected explanations as correct.

## Corpus boundary

Source of truth: `cdn/question-shards/manifest.json` and its 24 tracked shard files.

The sampler must:
- verify each shard SHA-256 against the manifest before selection;
- verify per-shard counts and the 4,800-row manifest total;
- fail on blank/duplicate question IDs;
- never edit any shard or Official Core field.

The sample is pinned to the manifest `dataset_revision`; if the corpus revision changes, `--check` must fail until the sample is intentionally rebuilt and reviewed.

## Review lanes

Five unique questions are selected per lane, for 30 unique questions total:

1. `special_grading` — non-standard grading mode. These cases must stay outside ordinary single-answer semantic assumptions.
2. `multi_answer` — more than one accepted answer. Review must verify accepted-set semantics and explanation wording.
3. `historical_law` — question matches the existing `machine_verified_historical_v1` registry. Historical metadata is useful evidence but does not itself certify the platform explanation.
4. `legal_ready` — a `ready` platform explanation carries law/policy content. Review focuses on source, applicable date, law version and unsupported certainty.
5. `negative_ready` — a `ready` explanation answers a conservative negative-wording question. Review focuses on inversion mistakes and option reasoning.
6. `numeric_ready` — a `ready` explanation/question/law includes an explicit number with a unit such as %, age, year, people, currency or time. Review focuses on factual-number support and stale values.

Selection uses fixed seed `swsi-high-risk-explanation-sample-v1` plus lane + question ID SHA-256 ranking. Earlier lanes take precedence when a question qualifies for multiple lanes; later lanes skip already-selected IDs.

## Integrity evidence stored per sample row

Each selected row records:
- question ID and exam coordinates;
- risk lane and reason;
- official source URL / legal source URL when available;
- grading mode and accepted answers;
- `analysis_status` / `legal_status`;
- `official_core_sha256` covering question/options/answer/accepted answers/grading mode;
- separate `explanation_sha256` covering SWSI explanation fields;
- deterministic selection SHA;
- `review_state=pending_source_review`.

Official Core and explanation hashes are intentionally separate: changing platform explanation must not look like a protected answer change, and changing an official answer/accepted set must be immediately detectable.

## What counts as review completion later

Selection alone is not completion. Each sampled item needs a separate evidence-backed review result appropriate to its lane. At minimum the future result should record:
- question ID;
- review date;
- source(s) consulted;
- whether Official Core remained unchanged;
- explanation finding (`pass`, `needs_correction`, `held_for_review` or equivalent);
- law/date/number/negative/multi-answer finding where relevant;
- before/after explanation hash if a platform explanation is corrected.

Do not mark `ready` as human-verified merely because it appears in this sample.

## Explicit non-goals

- No automatic correction of official questions, answers, accepted answers or grading.
- No model call and no paid API.
- No claim that 30 reviewed samples statistically prove all 4,800 explanations correct.
- No substitution for #258 production analyzer behavioral validation.
- No substitution for historical-law provenance or real current-law source checks.
