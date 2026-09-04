# Cloudflare D1 quota recovery contract

## Why this exists

The SWSI AI Worker uses Cloudflare D1 database `swsi-ai-quota` through binding `AI_QUOTA_DB`.

The current Worker relies on two tables:

- `ai_daily_client_usage`
- `ai_daily_global_usage`

The Worker uses those tables to reserve and refund public daily text/photo quota. In particular, its SQL depends on these conflict keys:

- client row: `ON CONFLICT(usage_date, client_key)`
- global row: `ON CONFLICT(usage_date)`

Historically, the D1 quota feature was created outside a repo-owned migration flow. The repository documents the database/table names and contains the Worker DML, but the original production `CREATE TABLE` statements are not present in Git history inspected for the current recovery baseline.

Therefore the exact existing production DDL is **UNKNOWN from repository evidence alone**.

## What `recovery_schema.sql` is

`recovery_schema.sql` is a **recovery-compatible bootstrap for a new/empty D1 database**. It is derived only from what the current Worker demonstrably requires:

- the two table names;
- columns read/written by the Worker;
- non-negative integer counters;
- the conflict keys required by the current `INSERT ... ON CONFLICT` statements;
- timestamp storage used by quota updates.

It is not represented as an exact snapshot of production internals, indexes, historical migrations, or any unknown extra metadata.

## What it is NOT

It is not:

- an automatic production migration;
- permission to alter the current production D1 database;
- proof that production DDL is byte-for-byte identical;
- a telemetry schema;
- a reason to reset or delete existing quota rows.

There is intentionally **no scheduled or deploy workflow that executes this SQL**.

## Safe recovery procedure

If D1 ever needs to be rebuilt:

1. Re-read the current Worker and `wrangler.jsonc`; do not trust old table assumptions.
2. If the existing production D1 is still readable, export/inspect its schema first (`sqlite_master` / `PRAGMA table_info` / relevant indexes) and save evidence outside secrets.
3. Compare the live schema with the Worker contract and this bootstrap.
4. Create a **new/empty** D1 recovery database; do not overwrite the old database as the first action.
5. Apply `recovery_schema.sql` to the new database.
6. Run `python3 scripts/cloudflare_d1_recovery_smoke.py` locally/in CI.
7. Bind a Worker preview to the recovery DB and run the existing Cloudflare Worker smoke plus explicit quota tests.
8. Only after human review should any production binding be changed.
9. Keep the old database/binding available for rollback until the replacement is verified.

Any production binding change remains an explicit human-approved production operation.

## Privacy

The Worker hashes its client identifier before using `client_key`; recovery tables should not be expanded into a per-user analytics store. Do not add raw IP, raw User-Agent, student answers, images, names, email addresses, or other personal data to these quota tables.

Operational telemetry, if added later, should use aggregate counters and a separate reviewed schema rather than turning quota storage into behavioral tracking.

## Executable contract

`scripts/cloudflare_d1_recovery_smoke.py` uses Python's built-in SQLite implementation to:

- apply the recovery bootstrap to a clean in-memory database;
- verify the required columns and primary/conflict keys;
- exercise the same reserve/cap/refund semantics the Worker requires;
- fail if destructive bootstrap statements are introduced;
- fail if the current Worker starts relying on a quota table/column that the recovery bootstrap does not provide.

This gives the repository a reproducible disaster-recovery contract without pretending that unobserved production DDL is known.
