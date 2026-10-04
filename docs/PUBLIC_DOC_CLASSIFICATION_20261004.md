# Public Documentation Classification — 2026-10-04

This document records the public-facing documentation policy for SWSI.

## Keep in the repository root

Root should contain only durable entry points and high-value project documents, such as:

- `README.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `TESTING.md`
- `AGENTS.md`
- stable release / maintenance policies that are genuinely useful to contributors

`AGENTS.md` must stay vendor-neutral and contain only minimum operating boundaries.

## Do not keep as current root documentation

The following are unsuitable as public project entry points and should not continue accumulating in the root:

- vendor-specific prompts such as `CLAUDE.md` or `GEMINI.md`;
- chat-session takeover instructions;
- long AI coordination prompts;
- daily project diaries;
- old release-candidate handoff snapshots;
- multiple files that repeat which model should read which other model's instructions.

Current work status belongs primarily in GitHub Issues / Pull Requests. Historical audits that remain useful should live under `docs/` or `audit/` and be clearly marked as snapshots.

## Compatibility pointer

`PROJECT_HANDOFF.md` is retained only as a short compatibility pointer because older documentation and tooling may still reference the path. It must not grow back into a chat transcript or rolling AI diary.

## Public but never secret

Architecture, deterministic QA concepts, maintenance rules and general recovery design can be public when they contain no sensitive values.

Never publish through Git history, Issues, PRs, Actions artifacts, logs or screenshots:

- real `.env` values;
- Supabase service-role credentials;
- GitHub / Netlify / Cloudflare / AI provider tokens;
- passwords;
- MFA / recovery codes;
- private backup encryption identities;
- plaintext private database dumps;
- raw private user or admin payloads;
- provider account takeover / recovery material.

## Historical Git boundary

Removing a file from the current tree does **not** erase older Git history. Historical identity/privacy and credential review remains a separate Public-readiness task. Do not rewrite repository history casually.

## Decision

SWSI should present itself as a normal public software/data project, not as a transcript of which AI worked on it. Long-term knowledge belongs in stable project documentation; current task state belongs in Issues / PRs.
