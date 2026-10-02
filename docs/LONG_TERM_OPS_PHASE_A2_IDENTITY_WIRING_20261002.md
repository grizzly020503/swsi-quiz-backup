# SWSI Ops Task Identity Wiring — Phase A-2

Issue: #269

This checkpoint turns the static identity contract into executable, read-only integration helpers without writing durable state or changing production workflows.

## New resolver

`scripts/ops_task_identity_resolver.py` reads `data/ops_task_identity.v1.json` and resolves one logical idempotency key using the declared strategy:

- `semantic_files_v1`: hashes every declared semantic component and fails closed if any required file is missing;
- `trigger_run_v1`: derives identity from the provider run id (for MOEX, `GITHUB_RUN_ID` or explicit `--run-id`);
- `parent_child_v1`: derives a child key from the parent key plus stable unit type/id.

The resolver validates paths as repo-relative and rejects duplicate component labels or unsupported strategies.

## Full Corpus diagnostic integration

`scripts/full_corpus_ops_identity.py` decorates an existing Full Corpus QA JSON report with:

- parent task idempotency key;
- one child idempotency key per exam session;
- stable checkpoint unit metadata.

This keeps Full Corpus QA read-only. The helper only rewrites a caller-supplied diagnostic file when `--in-place` is explicitly used.

Suggested future workflow sequence after durable storage is approved:

```bash
python scripts/full_corpus_qa.py --out /tmp/full-corpus-question-qa.json --fail-on blocked
python scripts/full_corpus_ops_identity.py --report /tmp/full-corpus-question-qa.json --in-place
```

Only after that should a separately reviewed persistence adapter claim/update ledger state.

## Safety boundary

This checkpoint does not:

- write Supabase;
- apply the candidate SQL;
- change GitHub workflow schedules;
- mutate Official Core;
- turn Guardian runtime outputs into scheduled registry tasks;
- create an external heartbeat.

## Verification

Local syntax checks were run for both new Python helpers before commit. Their self-tests cover trigger-run stability, parent-child stability, missing identity input failure, Full Corpus session uniqueness, and duplicate-session fail-closed behavior.

Refs #269 #262.
