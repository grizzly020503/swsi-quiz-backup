# Cloudflare Frontend Preview Contract Note — 2026-09-01

## Scope

This branch fixes a CI-only stale marker in `.github/workflows/cloudflare-frontend-preview.yml`.

The preview workflow still ran the stronger frontend gates successfully before the stale marker failure:

- `scripts/p0_frontend_preflight.js`
- `scripts/service_worker_update_smoke.js`
- JavaScript syntax checks
- `scripts/monthly_frontend_smoke.py`

The failing literal expected the retired marker `SWSI My Learning Center V1 2026-08-28`. The current canonical owner is `monthly_patch_parts/71.my-learning-center.part`, whose marker is `SWSI Learning Center V3 2026-08-29`.

## Change

- Update the build-time preview marker from Learning Center V1 to the current V3 owner marker.
- Update the main-only live-preview verification to the same V3 marker.
- Upgrade this workflow's checkout action from `actions/checkout@v4` to `actions/checkout@v5`.
- Keep every other existing preview assertion intact.

## Safety boundary

This change does not modify student runtime, official questions, grading, AI, Supabase, Cloudflare Worker source, D1 schema, secrets, or production configuration.

On non-main branches, the workflow's publish and live-deployment steps remain skipped. Cloudflare's GitHub integration may create an isolated branch preview version/alias; that is not the production release URL.

Do not merge or deploy production without explicit maintainer approval.
