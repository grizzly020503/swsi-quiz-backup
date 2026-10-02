# SWSI Portable Evidence Manifest / Storage Governance

Issue: #283

## Goal

Treat long-lived SWSI data and rebuild contracts as portable assets instead of assuming the current GitHub, Supabase, Cloudflare or CI provider will exist forever.

This contract is read-only. It does not export private production data, copy secrets, buy storage or deploy anything.

## Commands

```bash
python3 scripts/portable_evidence_manifest_selftest.py
python3 scripts/portable_evidence_manifest.py --check-determinism --output /tmp/swsi_portable_manifest.json
```

The generator uses only the checked-out repository and performs no network calls.

## Storage classes

### `long_term_public_knowledge`

Versioned, hashable, non-private knowledge that should not depend on a short CI-artifact retention window. Current required examples include question shards, canonical law/theory data, current-affairs source metadata, verified historical-law metadata and essay/current-affairs public runtime data.

### `rebuild_contract`

Source and contracts needed to recreate the system: migrations, Edge Function source, Worker source, Wrangler config, workflows, scripts and operating/handoff documents. Provider-specific source may be marked `provider_independent=false`; this means the asset is still retained so a future migration can understand the old implementation.

### `short_term_diagnostic`

Logs and temporary reports are explicitly not source of truth. The policy can classify them when present, but their absence does not block a portable manifest.

### `private_external`

Private mutable production data, Auth users, contact data and encrypted private backups are policy entries only. Their payloads must not be copied into Git merely to satisfy a 10/20/30-year platform goal. Their retention belongs to privacy/backup policy and #157.

## Manifest fields

Each repo file entry contains only:

- path;
- byte size;
- SHA-256;
- storage class;
- whether its rule is required;
- provider-independence flag;
- retention class.

No file body is embedded in the manifest.

## Fail-closed rules

- a required glob with no non-private files fails;
- one path assigned by more than one rule fails;
- private exclusion globs are applied before entries are emitted;
- policy schema or unsupported storage classes fail;
- any `private_external` policy that does not explicitly keep payloads outside Git fails;
- output is deterministically sorted and can be built twice for equality.

## Provider independence

`provider_independent=true` means a future maintainer can interpret that asset without the original provider account. `false` does not mean disposable: provider-specific source/config remains part of the rebuild record, but credentials and live account identifiers are not portable evidence payloads.

Question IDs, official-content provenance, schema/migration history and rebuild instructions must remain stable enough to survive a provider migration.

## Retention boundaries

- public knowledge: versioned and hashable; no arbitrary 14-day expiry;
- rebuild contracts: versioned and hashable;
- diagnostics: explicit short retention and never the only source of truth;
- private data: separate privacy and backup retention; 30-year platform ambition does not imply 30-year retention of personal data.

## Safety boundaries

- no Supabase private rows/Auth export;
- no feedback contact export;
- no secret/token/key values in manifest;
- no production/storage/provider mutation;
- no paid storage/provider;
- no production deploy;
- no scheduled workflow.

The PR-only QA for this work package may build a temporary manifest on the exact checkout and print counts only; it must not upload private data or convert CI artifacts into long-term source of truth.
