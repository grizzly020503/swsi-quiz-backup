# SWSI Exam Scheme Versioning — 2026-10-02

## Purpose

Issue #262 P1-1 requires future Social Worker exam intake to distinguish:

- a normal new year that still follows an approved examination structure;
- bad/mismatched exam identity metadata;
- a possible examination-system change that must be quarantined instead of being silently accepted or misreported as a complete intake.

This document is about structural intake safety. It does **not** predict what ROC 116 or later examinations will look like.

## Source of truth

`data/exam_scheme_registry.v1.json` is the approved structural intake registry.

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

`scripts/build_auto_payload.py` calls this gate before it writes owned backup payloads for an exam. A structural candidate change therefore stops before the later Supabase import step.

`scripts/exam_scheme_gate.py` provides a read-only report suitable for CI and diagnostics.

## Scheme-derived downstream QA

The approved profile is now also the current-intake structural source for downstream QA.

### `scripts/exam_scheme_qa_policy.py`

This module derives structural Unified-QA expectations for a requested year/round from the effective approved profile:

- subject list;
- MCQ total / per-subject count / qno range;
- essay total / per-subject count / qno range;
- answer letters when supplied by the profile.

It **does not** replace the semantic safety policy. `data/question_qa_policy_v1.json` continues to own grading-mode rules, legal/policy risk signals, review rules and release gates. Structural versioning therefore cannot silently lower semantic QA.

### `scripts/unified_question_qa_current.py`

This is the current/new-intake wrapper around the existing `unified_question_qa.py` engine. It derives the effective structural policy first and records profile provenance in the report.

The latest-exam `Unified Question QA` workflow no longer asserts literal `210`. It requires the dashboard total to equal `exam_scheme.expected_total_items` from the approved profile.

### `scripts/full_corpus_qa.py`

Every manifest session is audited through the effective-dated profile covering that session. When a future reform is officially verified and introduced as a **new** approved profile, old sessions continue to resolve their historical profile while future sessions use the new one.

The durable `full-corpus-question-qa` semantic identity also includes:

- `data/exam_scheme_registry.v1.json`;
- the scheme-to-QA policy converter;
- the current-intake Unified-QA wrapper.

A reviewed profile change therefore invalidates stale durable checkpoints instead of being mistaken for already-completed logical work.

### `scripts/health_check_v2.py`

The production workflow already uses v2 as the grading-aware health owner. Before `base.local_check()` processes `incoming/`, v2 now replaces only the current-incoming validator with the approved effective profile. Historical 104–115 regression constants inside `health_check.py` remain pinned.

Remote per-exam counts also come from each payload's approved profile rather than literal 200/10.

No production database or importer rule is changed by this derivation layer.

## Synthetic acceptance fixtures

`scripts/exam_scheme_selftest.py` is explicitly synthetic and verifies:

1. synthetic 116-1 with the same approved shape -> `match`;
2. a much later synthetic year with the same shape -> `match`;
3. special grading (`all_credit` / `any_answer`) with the same structure -> `match` because grading semantics are not a structural reform;
4. synthetic reduction from five subjects to four -> `candidate_change`;
5. synthetic removal of essays -> `candidate_change`;
6. mismatched exam-code / round identity -> `invalid_identity`.

`scripts/exam_scheme_downstream_selftest.py` adds a second boundary:

- current synthetic 116-1 resolves the current 200+10 profile;
- a **synthetic test-only approved** 117-1 profile with four subjects, 30 MCQ per subject and no essay derives 120+0 downstream expectations **without changing QA code**;
- historical 115-2 still resolves the old 200+10 profile;
- risk, release and grading semantics remain identical to the base QA policy.

These fixtures are tests, not statements about future exam policy.

## Fixed-assumption inventory

The original inventory was performed from main `aa56054c96059072c334cd23fc28f2be35f72f7b`; later items below record the downstream migration completed on 2026-10-02. Not every numeric literal is technical debt: historical regression fixtures must remain pinned.

| Location | Fixed assumption | Classification / action |
| --- | --- | --- |
| `scripts/moex_sync.py` | five subject adapters (`0301`–`0305`), 40 MCQ parsing, first two essays, 200+10 final count | **Current parser adapter.** Safe for the approved profile. Before approving a structurally changed profile, parser discovery/parsing must be updated and tested; do not loosen it automatically. |
| `scripts/moex_sync_v2.py` | correction rules expect 40 answer positions | **Current parser adapter.** Keep fail-closed until a reviewed scheme change also updates answer parsing. |
| `scripts/build_auto_payload.py` | previously hardcoded 200+10 | **Migrated.** Approved registry gate decides whether an exam can enter owned auto payloads. |
| `scripts/health_check.py` | five subjects, 200+10, 1–40 MCQ, 1–2 essays; historical essay ROC 104–115-1 constraints | Mixed. Historical constraints stay pinned. **Current workflow intake is now parameterized through `health_check_v2.py`'s scheme-derived validator.** |
| `scripts/health_check_v2.py` | remote per-exam 200 questions + 10 essays | **Migrated.** Current local/remote per-exam structure comes from the effective approved profile. |
| `data/question_qa_policy_v1.json` | five subjects, 40/2, 200/10 | Remains the base semantic/risk policy. **Current structural fields are overridden only through the approved scheme-derived layer.** |
| `.github/workflows/unified-question-qa.yml` | latest dashboard asserted total 210 | **Migrated.** Latest total is checked against the effective profile's `expected_total_items`. |
| `scripts/full_corpus_qa.py` | passed one static structural policy to every session | **Migrated.** Each session resolves its effective approved profile. |
| `supabase/functions/import-moex-social-worker/index.ts` | allowed five subjects, exactly 200+10 and 40+2 distribution | **Final downstream import gate intentionally remains strict.** A changed regime cannot be imported until a maintainer approves a new scheme and deliberately migrates/tests the importer. |
| `.github/workflows/moex-social-worker-sync.yml` | 115-2 essay enrichment QA is hardcoded | **Historical teaching-enrichment regression.** Keep 115-2 verification pinned; it is not a future intake structure rule. |
| `scripts/historical_answer_audit*.py` | pinned historical years / exam codes / subject knowledge | **Historical evidence.** Do not generalize or delete merely to remove literals. |
| `scripts/official_exam_readonly_guard.py`, lock data, shard regression checks | fixed 104–115 official counts/hashes | **Immutable historical baseline.** Future exams are additive; never rewrite old expectations to make a new scheme fit. |
| production/browser smoke checks referencing 24 shards or 115-2 | current release snapshot | **Release regression.** May gain additive future checks, but old evidence should not be rewritten as a generic future rule. |

## Safety boundary

### What is automatic

- A future session using the currently approved structure can pass the structural gate without editing year-specific code.
- Current incoming payloads can be audited in bulk against one versioned contract.
- A different observed subject/count/qno structure yields a machine-readable candidate diff.
- Candidate changes are not auto-approved and cannot enter `auto/questions_auto.json` / `auto/essays_auto.json` through the normal builder.
- Current Unified QA, Full Corpus QA and health-check v2 derive structural expectations from an approved effective profile.
- Changing the exam-scheme registry invalidates the Full Corpus durable logical-work fingerprint.

### What is intentionally NOT automatic

- discovering brand-new MOEX subject codes from an unknown future reform;
- deciding from a news item or model output that an official examination reform is real;
- changing Supabase importer rules, grading rules, or historical QA baselines;
- turning an observed candidate into an approved profile;
- interpreting a parser failure alone as proof that the exam system changed;
- changing parser option-field shape or importer schema merely because a synthetic profile can be represented in the registry.

Those require official evidence and a reviewed migration. This is a safety feature, not missing ambition.

## Remaining P1-1 follow-up

One repo-level detection gap remains before P1-1 is fully closed:

1. Add an official-page structure/discovery probe before the current PDF parser so a future missing/new subject can be reported as `possible_scheme_change` with official-page evidence instead of only surfacing as a parser/download failure.

When an actual reform is officially verified, the release process must add a **new** approved profile with an effective date and migrate/test parser + importer together. Never edit the old profile to rewrite history.

## CI

- `.github/workflows/exam-scheme-versioning-qa.yml` compiles the scheme/downstream scripts, runs both synthetic fixture suites, gates all current `incoming/` payloads, runs the scheme-aware local health check, rebuilds the auto payload and re-runs the immutable Official Core guard.
- `.github/workflows/unified-question-qa.yml` validates the latest published session against the profile-derived expected item total.
- `.github/workflows/full-corpus-qa.yml` audits every manifest session through its effective approved profile while preserving immutable Official Core checks.
