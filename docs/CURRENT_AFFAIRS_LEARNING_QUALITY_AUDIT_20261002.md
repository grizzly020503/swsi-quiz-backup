# SWSI Current-Affairs Learning Quality Audit

Issue: #261 P1-C  
Scope: deterministic audit only; no automatic semantic rewrite or production mutation.

## Why this exists

The current-affairs pipeline already has source ingestion, event clustering, primary/supporting exam subjects, historical-question relations, trend scoring and student-facing study directions. The remaining product-quality risk is different: a card can be structurally valid while still **looking stronger than its evidence**.

Examples from the current snapshot include events with:

- only one declared source;
- many medium/concept historical relations but zero strong match;
- explicit law context in related historical questions while the event has no `related_laws` entry.

Those are not automatically errors. They are exactly the cases that should be queued for semantic/editorial review instead of being “fixed” by another keyword rule.

## Contract

Policy:

- `data/current_affairs_learning_quality_policy.v1.json`

Audit CLI:

- `scripts/current_affairs_learning_quality_audit.py`

Default source:

- `auto/current_affairs_trends.json`

The audit produces two intentionally different layers.

### Hard errors

These are deterministic contract failures and are safe to block on:

- missing event ID/title;
- primary subject count outside 1–2;
- duplicate or overlapping primary/supporting roles;
- role subjects missing from `exam_subject_axes`;
- primary subject without a concrete `subject_topics` entry;
- invalid source counts (`official_source_count > source_count`);
- missing evidence or malformed source name/URL;
- related historical question missing ID or `match_reason`;
- student-facing card missing all `why` evidence;
- student-facing card missing both essay practice direction and MCQ focus.

These checks do not require guessing semantics.

### Review-only flags

These never mutate data and never block merely because the semantic risk exists:

- `single_source`;
- single-source event labelled `rising` / `sustained`;
- historical relations exist but `strong=0`;
- large relation volume (policy default >=8) with no strong match;
- declared source/history count differs from emitted evidence/list;
- related historical questions explicitly contain law/regulation context while event `related_laws=[]`.

The final case is only a **review candidate**. It does not mean the event must be attached to that law. Reviewers must decide whether the legal relation is substantive, indirect, historical-only, or irrelevant.

## Student presentation tiers

The audit also computes a conservative presentation tier from existing match evidence:

- `strong_historical_support`: at least one strong historical match;
- `medium_historical_relation`: no strong match, but one or more medium relations;
- `concept_observation`: only concept-level or no historical relations.

These labels are guidance for student-facing copy. None is an exam probability and none automatically changes `trend_score` or pipeline data.

## Important boundary

This audit must **not**:

- attach a law from keywords alone;
- delete historical-question relations automatically because they are not strong;
- infer that one official source equals independent cross-source confirmation;
- convert source count, observation count, trend score, or model agreement into a probability of appearing on the exam;
- modify source allowlists, current-affairs snapshots, Official Core, production database, or frontend automatically.

The intended flow is:

```text
current snapshot
  -> deterministic hard-contract audit
  -> evidence-thin / semantic-risk review queue
  -> human/evidence review
  -> separately reviewed source-rule or content correction
```

## Validation

Offline regression:

```sh
python3 scripts/current_affairs_learning_quality_audit.py --self-test
```

Current snapshot audit:

```sh
python3 scripts/current_affairs_learning_quality_audit.py \
  --output /tmp/current-affairs-learning-quality.json \
  --fail-on-hard
```

The PR-only QA runs both commands and prints only aggregate counts plus a compact per-event review summary. It has no schedule, no production write and no external model/provider call.

## How this advances #261 P1-C

This does not replace the required card-by-card semantic review. It makes that review bounded and reproducible by separating:

1. things software can prove are structurally wrong;
2. cards whose evidence strength or legal/historical relationship deserves human review.

That avoids the two failure modes called out in the project handoff: **weak evidence being presented too strongly** and **automatic rules inventing law/topic relations just to increase coverage**.
