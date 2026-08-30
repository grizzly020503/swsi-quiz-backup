# SWSI Maintainability Policy

> Goal: stop AI-assisted development from turning every fix into another late override layer while preserving the behavior already verified by the release QA system.

## 1. No new `zzz...` layers

Existing `z...` files are historical debt with some deliberate, tested owners. They are grandfathered, not a naming template.

**New runtime parts must not be created by adding more `z` characters to force later execution.**

If a change needs to run later, first ask why the existing canonical owner cannot own it.

`config/monthly_patch_structure.json` and `scripts/maintainability_smoke.py` enforce this.

## 2. Keep the part count flat or lower

Current baseline: **38 runtime `.part` files**.

A normal change should:

- edit an existing owner; or
- consolidate an old owner when introducing a replacement.

The structure guard fails if the count grows above the reviewed ceiling. Raising the ceiling is an architectural decision, not a routine AI fix, and requires explicit maintainer review.

## 3. New file naming

When a genuinely new subsystem requires a new part, preferred format is:

`NN.descriptive-kebab-name.part`

Examples:

- `76.exam-history.part`
- `94.feedback-accessibility.part`

Do not use `_fix`, `_final`, `_lock`, `_v2`, `_p0`, or repeated `z` prefixes as a way to express execution priority.

Existing exceptions are grandfathered and recorded in the structure config.

## 4. Runtime order is a contract

`cat monthly_patch_parts/*.part` means lexical filename order is execution order.

Therefore:

- do not casually rename a part;
- do not mass-renumber parts for aesthetics;
- do not assume a filename-only cleanup is behavior-neutral;
- any ownership/order migration needs the relevant runtime-owner and behavior regression tests.

## 5. One PR, one outcome

AI is good at finding extra work. That is also a scope-creep risk.

For every PR, write one primary outcome. Once the acceptance criteria pass:

**stop.**

Do not add unrelated:

- cosmetic refactors;
- code-health cleanup;
- new student features;
- new QA frameworks;
- dependency/tool migrations;
- architecture rewrites.

Create a follow-up issue/PR instead.

## 6. Release candidate freeze

A release-candidate PR is not a general cleanup branch.

After RC acceptance criteria are satisfied, only release-blocking P0/P1 fixes belong in that RC. Maintainability work should be stacked separately and merged after the release unless the maintainer explicitly changes scope.

## 7. Canonical-owner rule

Before editing runtime behavior:

1. read `ARCHITECTURE.md`;
2. read `PROJECT_HANDOFF.md` and the newest applicable delta;
3. inspect `scripts/runtime_owner_smoke.js`;
4. identify the current canonical/deliberate owner;
5. modify that owner when practical instead of wrapping it again.

If ownership is unclear, mark the state `UNKNOWN` and investigate. Do not create a new override just to make the symptom disappear.

## 8. Safe consolidation pattern

Use this sequence for future debt reduction:

```text
lock current behavior with regression evidence
        ->
move behavior to canonical owner
        ->
run owner + subsystem tests
        ->
delete old shim/wrapper
        ->
re-run regression
        ->
update architecture/handoff
```

Do not combine several unrelated owner migrations into one PR.

## 9. High-impact changes require human approval

Never auto-merge or auto-deploy changes to:

- official answers;
- `accepted_answers`;
- `grading_mode`;
- legal content with grading consequences;
- Auth / authorization / RLS;
- security controls;
- migrations;
- secrets / credentials;
- production deployment.

A Draft PR is not a completed fix.

## 10. Test expectation

For changes touching `monthly_patch_parts/**`:

- `python3 scripts/maintainability_smoke.py`
- `node scripts/runtime_owner_smoke.js`
- relevant subsystem regression tests

Use full browser/release QA only when change risk warrants it, consistent with `ZERO_COST_OPERATIONS.md`.

## 11. AI working contract

When AI works on this repository, default process is:

`Inspect -> Diagnose -> Plan -> Implement -> Test -> Security/Regression Review -> Report`

Rules:

- read the real current HEAD; do not trust old SHA values from chat;
- state UNKNOWN when evidence is missing;
- do not modify production simply to prove a change;
- do not weaken a contract to make QA green;
- do not invent extra work after acceptance criteria pass;
- report changed files, tests run, results, risks and unresolved items.

The target is a codebase a new human engineer can understand and safely maintain, not the maximum number of AI-generated improvements.
