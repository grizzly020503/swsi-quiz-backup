# Portable Evidence Manifest / Storage Retention — Phase C-2

Issue: #283  
Branch: `ops/portability-manifest-283`

This phase creates a **content-free inventory contract** for non-secret repository assets. It does not export private user data, create backups, upload data to another provider, or change production.

## Why this exists

A 10/20/30-year platform cannot treat every file the same. Long-term value depends on preserving enough non-sensitive, verifiable material to reconstruct the service while also avoiding indefinite retention of private data.

The policy separates four classes:

1. `long_term_public_knowledge`
   - official question shard artifacts and manifest;
   - exam/QA structural contracts;
   - curated law/theory/source registries;
   - reviewed non-private evidence when present.
2. `rebuild_contract`
   - migrations/recovery SQL;
   - Edge Function source;
   - build/QA scripts;
   - workflow source;
   - release and operating rules.
3. `short_term_diagnostic`
   - tracked QA/diagnostic outputs that are useful for troubleshooting but must not become the only source of truth.
4. `private_external`
   - hosted mutable private rows, Auth/session data, private feedback/contact data and encrypted backup payloads.
   - **Payloads are not included in the repo manifest.** Their backup/retention remains governed by #157 and the private-backup procedure.

## Verified required anchors on current main

Before writing the policy, current main was read and the following durable anchors were confirmed to exist:

- `cdn/question-shards/manifest.json`
- `data/exam_scheme_registry.v1.json`
- `data/question_qa_policy_v1.json`
- `data/laws.canonical.json`
- `data/theories.canonical.json`
- existing current-affairs and legal-watch source registries

The manifest policy is intentionally conservative. It does not claim every repo file is a permanent asset.

## Manifest contract

`scripts/portability_manifest.py`:

- runs offline / zero-network;
- reads `data/portability_asset_policy.v1.json`;
- expands policy globs in deterministic order;
- emits only:
  - path;
  - SHA-256;
  - byte size;
  - storage class;
  - retention class;
  - provider-independence flag;
  - rule ID;
- never embeds file contents;
- accepts an optional externally supplied `--source-revision` but does not call Git/GitHub itself;
- fails closed when a required rule matches no files;
- fails closed when one path is assigned to multiple rules/classes;
- fails closed when a manifest rule reaches a forbidden private path.

## Private-data boundary

The policy forbids common private backup/key patterns such as `.env`, private backup directories, database dump/encrypted dump paths, private-key formats and similar credential material.

This is defense in depth, not a replacement for secret scanning. A manifest being clean does **not** prove the repository contains no secret; normal release/secret gates remain authoritative.

The long-term platform horizon does not imply indefinite personal-data retention. Private data must follow data-minimization, privacy, backup and deletion policies independently of the public knowledge archive.

## Self-test evidence

The zero-network synthetic self-test covers five cases:

1. same inputs produce the same manifest;
2. content modification changes SHA-256;
3. a missing required class fails closed;
4. cross-rule duplicate assignment fails closed;
5. a private backup path is rejected even if a normal rule attempts to include it.

Local result before branch checkpoint: **5/5 PASS**.

## Deliberately not done

- no private database/Auth/feedback export;
- no backup payload committed;
- no production/storage/provider mutation;
- no paid archival service;
- no automatic upload;
- no scheduled workflow;
- no claim that short-lived CI artifacts are durable evidence;
- no change to #157 private-backup safety boundaries.

A later phase can produce a reviewed portable package from this manifest and test reconstruction on a new provider/account, but only with the same no-secret and private-data boundaries.
