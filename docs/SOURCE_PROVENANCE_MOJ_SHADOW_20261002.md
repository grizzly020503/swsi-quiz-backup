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

## Raw evidence vs stable normalized content

The first live shadow run exposed an important real-world property: two successful requests to the same MOJ LawAll page returned the same 136 parsed articles but different whole-page bytes/content because the HTML contains request-varying page machinery.

Therefore this adapter deliberately keeps two evidence layers separate:

1. **raw evidence** — `raw_content_hash` is SHA-256 of the exact HTTP response bytes and is allowed to differ between requests;
2. **normalized content evidence** — the existing legal-watch parser produces per-article SHA-256 fingerprints over `div#pnLawFla`. The adapter serializes a deterministic projection of law name + fingerprint contract version + sorted article fingerprints and supplies that projection to the shared normalized-content hash contract.

The adapter explicitly records:

- `raw_hash_basis = exact_http_response_bytes`
- `normalized_payload_basis = article_fingerprint_projection_v1`

This prevents MOJ view-state/navigation noise from becoming false legal-content changes while still preserving the exact fetched response hash for forensic evidence. The adapter does not invent a new legal parser; it reuses the current `moj_law_watch.py` article-fingerprint contract.

## Evidence captured

For the selected official LawAll page the adapter records:

- stable source ID derived from the canonical HTTPS URL;
- requested URL and verified final URL;
- redirect count;
- HTTP status / transport outcome;
- SHA-256 of exact response bytes;
- stable normalized parser-projection SHA-256;
- parser ID/version and normalization basis;
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
2. a second response with different dynamic page bytes but identical parsed articles → `success_no_change`;
3. raw hashes may differ while normalized parser-projection hash remains identical;
4. cross-host redirect → `invalid_content`, trusted predecessor retained;
5. missing article-body container → `parser_contract_changed`;
6. timeout → `source_unavailable`, trusted predecessor retained.

## Live PR-only shadow proof

The dedicated PR-only workflow performs exactly two read-only official fetches using one existing legal-watch record:

1. first run creates only `/tmp` shadow state and observation;
2. second run reuses that shadow state and must produce `success_no_change` for the same parsed legal content, even if dynamic raw HTML differs.

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
