# SWSI Exam Scheme Versioning — 2026-10-02

## Purpose

Issue #262 P1-1 requires future Social Worker exam intake to distinguish:

- a normal new year that still follows an approved examination structure;
- bad/mismatched exam identity metadata;
- a possible examination-system change that must be quarantined instead of being silently accepted or misreported as a complete intake.

This document is about structural intake safety. It does **not** predict what ROC 116 or later examinations will look like.

## New source of truth

`data/exam_scheme_registry.v1.json` is now the approved structural intake registry.

Current approved profile: `social-worker-five-subjects-v1`.

It records:

- effective start session;
- 030 / 100 exam-code suffix mapping;
- five subject names, MOEX subject codes and stable ID prefixes;
- 40 MCQ per subject / 200 total;
- 2 essays per subject / 10 total;
- qno ranges;
- evidence and the explicit policy that future same-shape sessions inherit the latest approved profile **until an observed structural difference appears**.

The registry is not permission to assume the system will never change. `auto_approve_candidate=false` is intentional.

## Runtime intake gate

`scripts/exam_scheme.py` compares an official payload against the approved registry and returns exactly one of these broad outcomes:

- `match`: approved structure; downstream processing may continue;
- `candidate_change`: observed structure differs; keep quarantined and surface the diff;
- `invalid_identity`: year / round / exam-code / row identity metadata contradict each other;
- `unapproved_scheme`: no approved profile covers the session.

Candidate output is observation-only. It does not invent MOEX subject codes/prefixes and cannot become executable without a reviewed registry change.

`scripts/build_auto_payload.py` now calls this gate before it writes owned backup payloads for an exam. This is the current fail-closed publication/import boundary in the MOEX workflow: a structural candidate change stops before the later Supabase import step.

`scripts/exam_scheme_gate.py` provides a read-only report suitable for CI and diagnostics.

## Synthetic acceptance fixtures

`scripts/exam_scheme_selftest.py` is explicitly synthetic and verifies:

1. synthetic 116-1 with the same approved shape -> `match`;
2. a much later synthetic year with the same shape -> `match`;
3. special grading (`all_credit` / `any_answer`) with the same structure -> `match` because grading semantics are not a structural reform;
4. synthetic reduction from five subjects to four -> `candidate_change`;
5. synthetic removal of essays -> `candidate_change`;
6. mismatched exam-code / round identity -> `invalid_identity`.

These fixtures are tests, not statements about future exam policy.

## Fixed-assumption inventory

The following search/inventory was performed from main `aa56054c96059072c334cd23fc28f2be35f72f7b`. Not every numeric literal is technical debt; historical regression fixtures must remain pinned.

| Location | Fixed assumption | Classification / action |
| --- | --- | --- |
| `scripts/moex_sync.py` | five subject adapters (`0301`–`0305`), 40 MCQ parsing, first two essays, 200+10 final count | **Current parser adapter.** Safe for the approved profile. Before approving a structurally changed profile, parser discovery/parsing must be updated and tested; do not loosen it automatically. |
| `scripts/moex_sync_v2.py` | correction rules expect 40 answer positions | **Current parser adapter.** Keep fail-closed until a reviewed scheme change also updates answer parsing. |
| `scripts/build_auto_payload.py` | previously hardcoded 200+10 | **Migrated in this change.** Approved registry gate now decides whether an exam can enter owned auto payloads. |
| `scripts/health_check.py` | five subjects, 200+10, 1–40 MCQ, 1–2 essays; historical essay ROC 104–115-1 constraints | Mixed. **Incoming/current duplicate gate remains pinned for defense-in-depth; historical 104–115 constraints are intentional regression evidence and must stay pinned.** Parameterize the incoming portion when a changed profile is actually approved. |
| `scripts/health_check_v2.py` | remote per-exam 200 questions + 10 essays | **Downstream safety gate.** It currently agrees with the approved profile and must be updated only together with an approved changed regime. It cannot silently widen intake because the build gate runs earlier. |
| `data/question_qa_policy_v1.json` | five subjects, 40/2, 200/10 | **Unified-QA policy debt.** Still valid for the approved profile. Follow-up should derive current-intake structural expectations from the scheme registry while retaining historical QA fixtures. |
| `.github/workflows/unified-question-qa.yml` | latest dashboard asserts total 210 | **Current-profile QA assertion.** Fails closed if structure changes; follow-up should derive the total from the approved profile rather than literal 210. |
| `supabase/functions/import-moex-social-worker/index.ts` | allowed five subjects, exactly 200+10 and 40+2 distribution | **Final downstream import gate.** Intentionally remains strict. A changed regime cannot be imported until a maintainer approves a new scheme and the importer is deliberately migrated/tested. |
| `.github/workflows/moex-social-worker-sync.yml` | 115-2 essay enrichment QA is hardcoded | **Historical teaching-enrichment regression.** Keep 115-2 verification as a pinned regression; do not treat it as future intake structure. The new scheme gate is the future structural boundary. |
| `scripts/historical_answer_audit*.py` | pinned historical years / exam codes / subject knowledge | **Historical evidence.** Do not generalize or delete merely to remove literals. |
| `scripts/official_exam_readonly_guard.py`, lock data, shard regression checks | fixed 104–115 official counts/hashes | **Immutable historical baseline.** Must remain pinned. Future exams are additive; never rewrite old expectations to make a new scheme fit. |
| production/browser smoke checks referencing 24 shards or 115-2 | current release snapshot | **Release regression.** May gain additive future checks, but old evidence should not be rewritten as a generic future rule. |

## Safety boundary after this change

### What is now automatic

- A future session using the currently approved structure can pass the structural gate without editing year-specific code.
- Current incoming payloads can be audited in bulk against one versioned contract.
- A different observed subject/count/qno structure yields a machine-readable candidate diff.
- Candidate changes are not auto-approved and cannot enter `auto/questions_auto.json` / `auto/essays_auto.json` through the normal builder.

### What is intentionally NOT automatic yet

- discovering brand-new MOEX subject codes from an unknown future reform;
- deciding from a news item or model output that an official examination reform is real;
- changing Supabase importer rules, grading rules, or historical QA baselines;
- turning an observed candidate into an approved profile;
- interpreting a parser failure alone as proof that the exam system changed.

Those require official evidence and a reviewed migration. This is a safety feature, not missing ambition.

## Remaining P1-1 follow-up

1. Make current-intake `unified_question_qa.py` / dashboard totals derive from the approved scheme registry instead of the static 210 profile, while preserving historical regression fixtures.
2. Parameterize the *current incoming* part of `health_check.py` / `health_check_v2.py` from the registry; keep historical 104–115 checks pinned.
3. Add an official-page structure/discovery probe before the current PDF parser so a future missing/new subject can be reported as `possible_scheme_change` with official page evidence instead of only surfacing as a parser/download failure.
4. When an actual reform is officially verified, add a new approved profile with an effective date and migrate/test parser + importer together. Never edit the old profile to rewrite history.

## CI

`.github/workflows/exam-scheme-versioning-qa.yml` compiles the new scripts, runs the synthetic fixtures, gates all current `incoming/` payloads, rebuilds the auto payload through the same structural gate, and re-runs the immutable Official Core guard.
