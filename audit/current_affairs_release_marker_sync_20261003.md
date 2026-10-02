# Current-affairs release marker sync — 2026-10-03

## Why

PR #314 intentionally renamed the student-facing current-affairs heading from `命題趨勢雷達` to `目前 3 個國考重點`. The product UI and current-affairs smoke were updated, but several active release/uptime gates still required the old literal heading. This created false-negative release checks even when the production-shaped build was otherwise valid.

## Updated active checks

- `.github/workflows/verify-netlify-production.yml`
- `.github/workflows/netlify-manual-deploy-artifact.yml`
- `scripts/public_uptime_smoke.py`

The Netlify controlled production workflow had already been aligned in PR #315.

## What did not change

No health threshold or evidence requirement was relaxed. The existing checks still require, where applicable:

- expected Netlify release marker;
- Service Worker v7;
- at least 17 current-affairs feeds and zero feed errors;
- 4,800-question signal baseline;
- deterministic-v2.2 events/trends contracts;
- exact runtime parity / cache-bust checks;
- preview-marker exclusion from production;
- existing browser and grading smokes.

This work does not deploy production, fetch private data, change Official Core, or modify current-affairs generation/ranking. It only aligns active verification with the student heading already merged in #314.
