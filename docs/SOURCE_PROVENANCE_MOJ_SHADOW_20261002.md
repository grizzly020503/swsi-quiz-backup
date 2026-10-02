# SWSI Source Provenance — MOJ Legal Watch Shadow Adapter

Issue: #278  
Mode: read-only shadow integration.

## Purpose

The shared `source_observation_contract.py` already defines transport/parser outcomes, raw and normalized SHA-256 evidence, replacement boundaries, trusted predecessor handling and correction rules. Until this adapter, that contract was not connected to a real existing source pipeline.

This work connects it **in shadow mode** to the existing MOJ legal watcher without changing the legal watch's official state or report.

## Existing pipeline reused

Existing production-owned source path:

- `scripts/moj_law_watch.py`
- `data/legal_watch_report.json`
- `data/legal_watch_state.json`

The shadow adapter:

- `scripts/moj_law_watch_shadow_observation.py`

reads one already-resolved, verified `law.moj.gov.tw/LawClass/LawAll.aspx?...` record from `data/legal_watch_report.json`, fetches that exact official URL, reuses the existing `moj_law_watch` parser helpers, and emits the provider-neutral observation contract.

It does **not** call the legal-watch writer and does not overwrite its files.

## Evidence captured

For the selected official LawAll page the adapter records:

- stable source ID derived from the canonical HTTPS URL;
- requested URL and verified final URL;
- redirect count;
- HTTP status / transport outcome;
- SHA-256 of exact response bytes;
- normalized decoded-text SHA-256;
- parser ID/version;
- parser item count based on the existing article-fingerprint parser;
- `success_changed`, `success_no_change`, transport/parser failure, etc.;
- last trusted normalized hash in a **separate shadow state**;
- effective date from the already-verified legal-watch record.

The mutable shadow state defaults to `/tmp/swsi_moj_shadow_state.json`; the observation defaults to `/tmp/swsi_moj_shadow_observation.json`. Neither is a production state file.

## Trust boundary

The adapter fails closed around source identity:

- requested source must be HTTPS;
- hostname must be exactly `law.moj.gov.tw`;
- requested path must be an existing `LawAll.aspx` URL from the legal-watch report;
- redirects are followed only for observation, and the final hostname must still be `law.moj.gov.tw` for parser success;
- a redirect to another host is classified as invalid content and cannot replace trusted shadow evidence;
- missing `pnLawFla` article body after the law name is present is treated as parser-contract drift;
- timeout/network failure preserves the previous trusted shadow hash.

No external content may alter permissions, source allowlists, publication authorization or production state; those constraints remain inherited from `source_observation_contract.py`.

## Deterministic offline regression

```sh
python3 scripts/moj_law_watch_shadow_observation.py --self-test
```

The synthetic regression proves:

1. first valid official-like response → `success_changed` with raw hash;
2. same bytes with shadow predecessor → `success_no_change`;
3. cross-host redirect → `invalid_content`, trusted predecessor retained;
4. missing article-body container → `parser_contract_changed`;
5. timeout → `source_unavailable`, trusted predecessor retained.

## Live PR-only shadow proof

The dedicated PR-only workflow performs exactly two read-only official fetches using one existing legal-watch record:

1. first run creates only `/tmp` shadow state and observation;
2. second run reuses that shadow state and must produce `success_no_change` for the same official bytes.

It then checks that raw/normalized hashes are present and that Official Core, legal-watch state/report and production publication are not mutable through the adapter.

No artifact is uploaded, no repository state is written, no schedule is added, and the workflow does not run on main push.

## What this does not do

- does not replace `moj_law_watch.py`;
- does not mutate `data/legal_watch_state.json`;
- does not mutate `data/legal_watch_report.json`;
- does not modify question shards, answers or Official Core;
- does not publish source observations to Supabase or any production database;
- does not enable automatic correction publication;
- does not change the legal-watch schedule;
- does not add a paid provider.

After exact-head offline + live shadow QA passes, #278's previously documented "one real pipeline shadow adapter" gap is satisfied. Any future write-path adoption must be a separate reviewed change and must preserve the current fail-closed replacement/correction rules.
