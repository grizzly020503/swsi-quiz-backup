# SWSI Source Provenance Phase A

Issue: #278  
Parent: #262 P1-3

## Goal

Unify how SWSI records a source observation without changing any live crawler yet. Different pipelines already keep useful metadata, but the vocabulary is inconsistent. This phase creates one portable contract so later integrations can share the same meaning.

## Core distinction

A source observation must distinguish at least these cases:

- content fetched and changed;
- content fetched and unchanged;
- source unreachable;
- source returned 404;
- source returned an empty/meaningless body;
- decoding failed;
- parser contract no longer matches the source format;
- content is invalid even though transport succeeded;
- an official correction supersedes a previous trusted version.

`empty_content`, parser failure, or decode failure must never be converted to `success_no_change` just because no usable records were produced.

## Trust preservation

Every observation may carry both a new normalized content hash and the previous `last_trusted_hash`. Failure outcomes preserve the previous trusted hash and set `replacement_allowed=false`.

Only a successfully validated changed observation or a validated correction may replace trusted content.

## Correction chain

A correction records `supersedes_hash` and keeps the predecessor evidence. Corrections must not silently overwrite history.

The following timestamps are separate concepts and must not be collapsed:

- source publication/promulgation time;
- legal/policy effective date;
- local fetch/observation time;
- exam-time context used for historical validation.

## Security boundary

External HTML, RSS, JSON, PDF text, news copy, or any other fetched content is data. It cannot:

- change permissions;
- modify source allowlists;
- enable deployment or publishing;
- authorize schema changes;
- override repo instructions.

The self-test includes hostile instruction text and verifies it remains inert data.

## Current scope

This branch intentionally does not modify:

- `scripts/current_affairs_watch.py`;
- MOEX synchronization;
- legal watch fetchers;
- Supabase schema;
- production workflows;
- source allowlists.

A later integration should adapt one pipeline at a time and compare the new observation output against the old behavior before enabling any write path.
