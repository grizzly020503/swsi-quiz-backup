# SWSI Supabase Free-tier private-data backup runbook

This runbook covers the **hosted mutable data layer** that Git source and the isolated
schema restore drill cannot reproduce by themselves.

It is deliberately separate from the normal GitHub Actions disaster-recovery drill.

## Safety rules

1. **Never run a production private-data dump in GitHub Actions, Netlify, Cloudflare build, or another shared CI runner.**
2. Run the backup only on a maintainer-controlled local computer.
3. Never commit or paste:
   - database connection strings,
   - database passwords,
   - Supabase secret/service-role keys,
   - age private identity files,
   - plaintext SQL dumps,
   - decrypted Auth / feedback / analytics contents.
4. Plaintext dump files exist only in an OS temporary directory and are deleted after encryption.
5. The destination directory must be outside the Git worktree.
6. A created encrypted bundle is **not yet restore proof**. Issue #157 should remain open until one encrypted backup is restored into an isolated target and validated.

## Why this is required on the Free plan

Supabase's current backup documentation says automatic daily database backups are
provided on paid Pro / Team / Enterprise projects, while Free projects should
regularly use `supabase db dump` and retain off-site backups.

The repository already proves that source-controlled platform state can be rebuilt.
This runbook handles mutable hosted rows that are not appropriate to store in Git.

## What the local helper captures

`scripts/supabase_private_backup_local.sh` creates the standard Supabase CLI migration set:

- `roles.sql`
- `schema.sql`
- `data.sql` using `--use-copy --data-only`
- a count-only `source-counts.json`
- `metadata.json` containing source Git SHA, tool versions, file sizes and SHA-256 values

Those files are tarred and encrypted with **age** before the bundle leaves the temporary directory.

The output is:

- `swsi-supabase-private-<UTC>-<git-sha>.tar.age`
- the matching `.sha256` sidecar

### Important Auth caveat

Supabase documentation describes managed `auth` / `storage` schema handling differently
depending on migration context and CLI path. Therefore SWSI does **not** declare Auth restored
merely because `supabase db dump` completed.

The source bundle records only the count of `auth.users`. A restore is accepted only when the
isolated target is checked and the target Auth count matches the source count baseline.

This turns documentation/version ambiguity into an executable acceptance check instead of an assumption.

## Prerequisites

Install locally:

- Supabase CLI
- Docker (required by Supabase CLI dump operations)
- PostgreSQL client / `psql`
- `age`
- Python 3
- Git

Create an age identity outside the repository and store the private identity somewhere protected.
Only the public `age1...` recipient is used by the backup helper.

Do not store the private identity in this repository.

## Create an encrypted backup

From the SWSI repository on the maintainer computer:

```bash
export SWSI_SUPABASE_DB_URL='...'
export SWSI_BACKUP_AGE_RECIPIENT='age1...'
export SWSI_BACKUP_DIR="$HOME/swsi-private-backups"

bash scripts/supabase_private_backup_local.sh
```

The script intentionally refuses to run when `CI` or `GITHUB_ACTIONS` is present.

After creation:

1. keep the encrypted bundle and its SHA-256 sidecar together;
2. copy them to at least one additional off-site location;
3. do not upload plaintext SQL anywhere;
4. run the local integrity verifier:

```bash
bash scripts/verify_supabase_private_backup_local.sh \
  "$HOME/swsi-private-backups/swsi-supabase-private-....tar.age"
```

The verifier decrypts into a temporary local directory, checks all internal SHA-256 values,
prints only the source Git SHA and row-count baseline, then removes the temporary directory.

## Recommended zero-cost cadence

Until a paid provider backup tier is intentionally chosen:

- **weekly** encrypted local/off-site backup,
- plus an extra backup before destructive schema/Auth changes or a major release,
- keep at least two recent verified encrypted generations in separate locations.

With a weekly cadence, the operational hosted-data RPO target is at most 7 days.
The actual RPO must be calculated from the timestamp of the newest verified backup available
when an incident happens.

## Isolated restore drill

Do not restore over production.

Use a new isolated Supabase project or a local/self-hosted Supabase target.

### Preferred guarded helper

The repository now includes:

`scripts/restore_supabase_private_backup_isolated.sh`

It refuses CI and requires an explicit write acknowledgement.

For a local target, it only accepts a loopback database host. For a hosted isolated target,
it requires both the production and target project refs and fails if they are equal or if the
target URL appears to reference production.

It also requires the target to begin with:

- `auth.users = 0`
- `storage.objects = 0`

If the source backup contains Storage objects, the helper fails closed because database restore
cannot prove Storage object bytes.

Example for a hosted isolated target:

```bash
export SWSI_RESTORE_TARGET_DB_URL='...'
export SWSI_RESTORE_TARGET_KIND='hosted-isolated'
export SWSI_PRODUCTION_PROJECT_REF='...'
export SWSI_TARGET_PROJECT_REF='...'
export SWSI_RESTORE_ACK='I_UNDERSTAND_THIS_WRITES_THE_ISOLATED_TARGET'

bash scripts/restore_supabase_private_backup_isolated.sh \
  "$HOME/swsi-private-backups/swsi-supabase-private-....tar.age"
```

Do not paste any of those database credentials or project-specific secret values into chat or GitHub.

The helper:
1. verifies the encrypted bundle;
2. verifies the isolated target is empty enough;
3. applies roles → schema → data;
4. captures target count-only baselines;
5. fails on any source/target count mismatch;
6. records measured database restore RTO in a local count-only JSON report outside the repository.

### 1. Record start time

Record UTC restore start time. This is the start of the measured hosted-data RTO.

### 2. Verify and decrypt locally

Run the verifier first. Then decrypt the bundle into a local temporary directory.

### 3. Restore using the Supabase CLI migration pattern

Follow the current Supabase backup/restore guide for the target version. The standard restore
order is roles → schema → data, with triggers disabled during data import where the official
guide requires it.

Do not improvise around permission errors by weakening RLS or granting public access.

### 4. Restore non-database configuration separately

Database dump files do not constitute a complete backup of:

- Edge Function deployment state — canonical source is in `supabase/functions/`;
- secret **values** — recreate them in the target secret manager, never from Git;
- Auth provider/OAuth configuration;
- SMTP configuration;
- custom domain / DNS routing;
- Storage **object bytes**.

The repo may record required configuration **names**, but never production secret values.

### 5. Validate source vs target counts

The encrypted bundle contains `source-counts.json`. On the isolated target, run an equivalent
count-only query and compare at least:

- `auth.users`
- `public.swsi_feedback_reports`
- `public.swsi_usage_daily`
- `public.swsi_ai_telemetry_client_daily`
- `public.swsi_ai_telemetry_5m`
- `storage.buckets`
- `storage.objects`

A mismatch is a failed restore drill until explained and resolved.

Do **not** compare by exporting personal row contents into GitHub.

### 6. Storage rule

If the source baseline reports `storage_objects > 0`, the database dump is not enough.
Storage object bytes require a separate object-backup procedure before #157 can be closed.

### 7. Validate platform contracts

After data is present, rerun the repo-owned isolated recovery/security contracts as appropriate:

- RLS / privilege boundary
- SECURITY DEFINER execute boundary
- grading / official-question contracts
- Edge Function compile
- D1 recovery
- local student browser/PWA smoke
- mocked admin auth/recovery smoke

### 8. Record RTO and RPO

- **RTO:** restore start → isolated target passes the required acceptance checks.
- **RPO:** incident time → newest successfully verified encrypted backup timestamp.

Record timings and counts, not secret values or personal row contents.

## Conditions for closing Issue #157

The hosted mutable-data portion is complete only after all of the following are true:

- at least one real production encrypted backup bundle exists outside Git;
- its checksum and internal manifest verify locally;
- an isolated target restore has succeeded;
- source/target count-only baselines match or any expected differences are documented;
- Auth restore coverage is empirically proven, not assumed;
- Storage object handling is proven if objects exist;
- measured hosted-data RTO and RPO are recorded;
- production was never overwritten during the drill.

Until then, the repo/source DR layer is complete, but the private hosted-data backup layer remains open.
