# MOEX Official-Page Structure Discovery — 2026-10-05

Parent: #262  
Related: `docs/EXAM_SCHEME_VERSIONING_20261002.md`

## Why this exists

The versioned exam-scheme registry already protects parsed payloads, but the old
MOEX sync path could first discover a future examination reform only after a PDF
subject download/parser failed. That is too late and makes a real structural
change look like an ordinary network/parser incident.

This work package adds a read-only discovery gate **before PDF parsing**.

## Components

### `scripts/moex_structure_probe.py`

- fetches the official MOEX exam page (or accepts an offline HTML fixture);
- isolates the `高考_社會工作師` class section;
- extracts visible subject names plus MOEX subject codes from official Q/A links;
- compares the observed set with `data/exam_scheme_registry.v1.json`;
- records source URL, fetch time and content SHA-256;
- returns `match` only for the approved subject/code set;
- returns `possible_scheme_change`, `target_class_missing`, `unapproved_scheme`
  or `source_error` otherwise;
- never edits or approves the exam-scheme registry.

External page content is treated strictly as data. Unknown text cannot instruct
the agent to relax the registry or publish a candidate scheme.

### `scripts/moex_sync_guarded.py`

This is a wrapper around the existing reviewed `moex_sync.build_exam()` parser.
It deliberately does not fork or rewrite Official Core parsing.

Intake order:

1. official-page structure probe;
2. only when `status=match` and `safe_to_parse_pdfs=true`, run the existing PDF parser;
3. run the existing `exam_scheme.compare_payload()` gate again on the complete payload;
4. only a second `match` can be written as incoming payload.

A page mismatch/source failure therefore cannot degrade into "try the PDFs
anyway". A parser result also cannot bypass the existing versioned scheme gate.

Probe reports are written separately from the question payload so a blocked
future exam leaves machine-readable evidence for review.

## Deterministic fixtures

- `scripts/moex_structure_probe_selftest.py`
  - approved five-subject shape;
  - missing subject;
  - extra subject;
  - renamed subject;
  - recoded subject;
  - target class absent;
  - neighboring professions and duplicate links do not leak into the result;
  - hostile/untrusted page text remains data and fails closed.

- `scripts/moex_sync_guarded_selftest.py`
  - structure mismatch blocks before `build_exam()`;
  - source error blocks before `build_exam()`;
  - approved page can continue;
  - post-parse scheme mismatch is still quarantined.

## Current integration boundary

This branch intentionally does **not**:

- apply Supabase migrations;
- enable live durable-ledger writes;
- deploy production;
- mutate Official Core;
- auto-approve a changed examination scheme;
- add a new high-frequency schedule.

After deterministic/CI validation, the next reviewed step is to switch the
existing MOEX workflow entrypoint to the guarded wrapper (or call the probe from
the existing entrypoint) while preserving the existing importer/release gates.
The durable ledger/runtime activation under #274 remains a separately gated
production step.

## Expected long-term behavior

A normal future session with the same approved structure proceeds without a
new year-specific code change. If MOEX changes the subject set/code structure,
the system emits a reviewable `possible_scheme_change` report and stops before
PDF parsing/publishing. Humans then review official evidence and add a new
effective-dated profile only when the reform is confirmed.
