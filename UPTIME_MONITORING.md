# SWSI Public Uptime Monitoring

## Goal

Provide a small, cheap signal that the public SWSI study path is still reachable between releases.

This monitor is intentionally much smaller than release QA. Its job is to answer:

> Is the public site shell, question CDN and AI proxy entry point reachable right now?

It does **not** certify that every product feature is correct.

## Schedule and cost boundary

`.github/workflows/public-uptime.yml` runs once daily at approximately **08:17 Asia/Taipei** (`00:17 UTC`) after it is merged to the repository default branch.

The workflow:

- uses one small Ubuntu job;
- installs no browser;
- installs no npm/pip dependency;
- uses Python standard library only;
- makes no live AI model request;
- reads no secrets;
- writes no production data;
- has a 3-minute hard timeout.

A daily cadence is deliberate. Uptime monitoring must not recreate the GitHub Actions exhaustion problem. Full Chromium/WebKit/storage/release QA remains a release/high-risk gate, not an uptime cron.

If Actions allowance is unavailable, this sentinel may pause; the student-facing site must remain usable independently, consistent with `ZERO_COST_OPERATIONS.md`.

## What is checked

`scripts/public_uptime_smoke.py` checks four public surfaces:

1. **Netlify Home**
   - HTTP 200;
   - HTML content type;
   - SWSI product marker is present.
2. **Netlify PWA assets**
   - `/manifest.json` is HTTP 200 and valid JSON;
   - manifest retains the standalone/start-url contract;
   - `/sw.js` is HTTP 200 and looks like the SWSI Service Worker.
3. **Cloudflare question CDN**
   - `/question-shards/manifest.json` is HTTP 200 and valid JSON;
   - current official corpus invariant remains 4,800 questions / 24 shards.
4. **Cloudflare AI Worker entry point**
   - CORS preflight from the official Netlify origin returns 204;
   - allowed origin/method contract remains valid.

The AI check intentionally uses `OPTIONS`, not a real completion request. It consumes no public daily AI text/photo quota and cannot leak a prompt or student answer.

## What is NOT checked

A green uptime sentinel does not prove:

- grading logic is correct;
- all 24 shard SHA-256 hashes are correct;
- browser interactions work;
- Supabase Admin is healthy;
- AI upstream/provider generation is available;
- D1 quota writes are healthy;
- AI output quality is good;
- photo/OCR works;
- production matches a specific release candidate.

Those concerns remain covered by their dedicated release, Worker, storage, grading, Golden Set and production verification gates.

## Failure handling

If the scheduled job turns red:

1. Read the actual failed surface from the job log.
2. Do not immediately change product code.
3. Retry once only when the failure looks like a transient network error.
4. Distinguish:
   - Netlify unavailable;
   - Cloudflare assets unavailable;
   - Worker CORS/route drift;
   - expected corpus invariant drift after a verified official update;
   - GitHub runner/network infrastructure failure.
5. If a production dependency is genuinely down, preserve student core/fallback behavior and investigate the dependency before deploying a speculative fix.
6. Never weaken a content/integrity assertion merely to make monitoring green.

## Release verification remains separate

`.github/workflows/verify-netlify-production.yml` is the manual post-release verifier. It intentionally performs deeper release-specific HTTP and browser checks and therefore costs more runner time.

Do not replace that release gate with this daily sentinel. Conversely, do not schedule the heavy release verifier every day.

## Privacy

This sentinel sends no student identifier, answer, photo, contact information, session token, API key, service-role key or internal secret.

It only performs public reads and an ordinary browser-style CORS preflight from the official SWSI origin.
