# SWSI Maintainability Policy

> Goal: stop AI-assisted development from turning every fix into another late override layer while preserving the behavior already verified by the release QA system.

## 1. No new `zzz...` layers

Existing `z...` files are historical debt with some deliberate, tested owners. They are grandfathered, not a naming template.

**New runtime parts must not be created by adding more `z` characters to force later execution.**

If a change needs to run later, first ask why the existing canonical owner cannot own it.

`config/monthly_patch_structure.json` and `scripts/maintainability_smoke.py` enforce this.

## 2. Keep the part count flat or lower

Current baseline: **36 runtime `.part` files**.

A normal change should:

- edit an existing owner; or
- consolidate an old owner when introducing a replacement.

The structure guard fails if the count grows above the reviewed ceiling. Raising the ceiling is an architectural decision, not a routine AI fix, and requires explicit maintainer review.

## 3. New file naming

When a genuinely new subsystem requires a new part, preferred format is:

`NN.descriptive-kebab-name.part`

Do not use `_fix`, `_final`, `_lock`, `_v2`, `_p0`, or repeated `z` prefixes as a way to express execution priority.

Existing exceptions are grandfathered and recorded in the structure config.

## 4. Runtime order is a contract

`cat monthly_patch_parts/*.part` means lexical filename order is execution order.

Therefore do not casually rename or mass-renumber parts, and do not assume filename-only cleanup is behavior-neutral. Any ownership/order migration needs relevant runtime-owner and behavior regression tests.

## 5. One PR, one outcome

For every PR, write one primary outcome. Once acceptance criteria pass: **stop**.

Do not add unrelated cosmetic refactors, code-health cleanup, student features, QA frameworks, dependency migrations, or architecture rewrites. Use a follow-up issue/PR instead.

## 6. Canonical-owner rule

Before editing runtime behavior:

1. read `ARCHITECTURE.md`;
2. read `PROJECT_HANDOFF.md`;
3. inspect `scripts/runtime_owner_smoke.js`;
4. identify the current canonical/deliberate owner;
5. modify that owner when practical instead of wrapping it again.

If ownership is unclear, mark the state `UNKNOWN` and investigate. Do not create a new override just to make the symptom disappear.

## 7. Safe consolidation pattern

`lock current behavior -> move to canonical owner -> owner/subsystem tests -> delete old shim -> re-test -> update architecture/handoff`

Do not combine several unrelated owner migrations into one PR.

## 8. High-impact changes require human approval

Never auto-merge or auto-deploy changes to official answers, `accepted_answers`, `grading_mode`, legal content with grading consequences, Auth/authorization/RLS, security controls, migrations, secrets/credentials, or production deployment.

A Draft PR is not a completed fix.

## 9. Test expectation

For changes touching `monthly_patch_parts/**`:

- `python3 scripts/maintainability_smoke.py`
- `node scripts/runtime_owner_smoke.js`
- relevant subsystem regression tests

Use full browser/release QA only when change risk warrants it.

## 10. AI working contract

Default process:

`Inspect -> Diagnose -> Plan -> Implement -> Test -> Security/Regression Review -> Report`

Rules:

- read the real current HEAD; do not trust old SHA values from chat;
- state UNKNOWN when evidence is missing;
- do not modify production simply to prove a change;
- do not weaken a contract to make QA green;
- do not invent extra work after acceptance criteria pass;
- report changed files, tests, results, risks and unresolved items.

The target is a codebase a new human engineer can understand and safely maintain, not the maximum number of AI-generated improvements.
