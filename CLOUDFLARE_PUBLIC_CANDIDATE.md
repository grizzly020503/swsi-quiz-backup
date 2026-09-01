# SWSI Cloudflare public candidate

This file documents the temporary Cloudflare public-candidate branch used to validate the SWSI frontend on a Cloudflare `workers.dev` origin before any production cutover.

## Safety boundary

- Non-production branch preview only.
- Does not merge PR #33 or change `main`.
- Does not replace the Netlify production site.
- Does not promote a Cloudflare Worker version to production.
- The candidate build must run `scripts/public_content_sanitize.py` before publishing any student HTML.
- The candidate origin is `https://swsi-public-candidate-wandering-wave-4418.c022050333.workers.dev`.
- Candidate content is marked `noindex,nofollow,noarchive`.

## Candidate acceptance

The hosted candidate must verify:

1. `/` serves the current SWSI release-candidate frontend.
2. Third-party study-guide markers are absent.
3. `manifest.json`, `sw.js`, `monthly_patch.js`, `essay_guides.js`, icons and `auto/` payloads resolve.
4. `/admin/` remains protected by the existing Supabase Auth/allowlist flow.
5. `/question-shards/manifest.json` still exposes the verified 4,800-question corpus.
6. AI preflight accepts only the explicitly allowlisted candidate origin.
7. Existing Netlify and Cloudflare production are unchanged.

This candidate is not the final long-term hosting architecture. The final public frontend should be a separate Cloudflare frontend project so that student static hosting and the AI/D1 Worker remain separate deployment units.
