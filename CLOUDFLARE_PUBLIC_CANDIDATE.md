# SWSI Cloudflare public candidate

Temporary non-production Cloudflare candidate used to validate the current SWSI release candidate on a `workers.dev` origin before any public cutover.

## Safety boundary

- Non-production branch preview only.
- Does not merge PR #33 or change `main`.
- Does not replace the Netlify production site.
- Does not promote a Cloudflare Worker version to production.
- Public HTML must run `scripts/public_content_sanitize.py` before publication.
- Candidate origin: `https://swsi-public-candidate-wandering-wave-4418.c022050333.workers.dev`.
- Candidate content is `noindex,nofollow,noarchive`.

## Acceptance gate

1. `/` serves the current SWSI release-candidate frontend.
2. Third-party study-guide markers are absent.
3. PWA/runtime assets resolve.
4. `/admin/` keeps the existing Supabase Auth/allowlist protection.
5. `/question-shards/manifest.json` still reports the verified 4,800-question corpus.
6. AI preflight accepts the explicitly allowlisted candidate origin.
7. Existing Netlify and Cloudflare production remain unchanged.

The final public frontend should become a separate Cloudflare frontend project so student static hosting and the AI/D1 Worker remain separate deployment units.
