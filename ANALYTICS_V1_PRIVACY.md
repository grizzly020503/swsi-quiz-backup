# SWSI Anonymous Usage Analytics V1

## Purpose

Provide operationally useful aggregate usage counts in the protected SWSI Admin center without adding third-party tracking or collecting unnecessary personal data.

## What is counted

- Approximate anonymous browsers today
- Page views today
- Approximate unique anonymous browsers over the last 7 days
- Approximate cumulative anonymous browsers since activation
- Cumulative page views since activation
- Daily users/page views for the latest 7 days

A "user" is an anonymous browser identifier, not a verified human identity. One person using multiple browsers/devices can count more than once. Clearing site storage can create a new identifier.

## What is stored

The browser already has a random SWSI client ID for existing AI/feedback rate-limit behavior. Analytics reuses that random value. The public analytics Edge Function hashes it with SHA-256 before database storage.

The analytics table stores only:

- Taiwan usage date
- SHA-256 client hash
- daily page-view count
- first/last seen timestamps

It does not add fields for name, email, account ID, raw IP address, User-Agent, referrer history, device fingerprint, screen dimensions, location, or page content.

## Collection boundary

The public runtime sends analytics only when `location.origin` exactly matches:

`https://wandering-wave-4418.c022050333.workers.dev`

Cloudflare branch previews, Netlify, localhost and other origins do not send analytics. This prevents QA/preview traffic from inflating production counts.

The Edge Function independently enforces the same production Origin and accepts only a small `page_view` event body plus the anonymous client ID header.

## Accuracy and abuse boundary

These figures are operational estimates, not verified human-account counts. The browser Origin check is useful for the normal browser/CORS boundary, but a direct HTTP client can spoof the `Origin` header and generate random client IDs. Therefore Analytics V1 is not designed to provide tamper-proof traffic numbers.

Do not use these counts as billing data, security/audit evidence, legal evidence, or proof of a precise number of unique people. They are appropriate for lightweight product-operation questions such as whether the site is being used and whether usage is broadly increasing or decreasing.

## Access boundary

- `swsi_usage_daily` has RLS enabled.
- `anon` and `authenticated` roles receive no direct table access.
- Recording and summary RPCs are service-role-only.
- Aggregate summaries are exposed only through the existing authenticated `swsi-admin` Edge Function after administrator membership verification.

## Historical limitation

Usage before Analytics V1 is enabled cannot be reconstructed. Admin totals therefore start from the production activation date and must not be presented as lifetime usage before that date.
