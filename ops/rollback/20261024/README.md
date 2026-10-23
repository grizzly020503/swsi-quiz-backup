# SWSI controlled recovery snapshot — 2026-10-24

This **branch-only** copy preserves exact existing production Supabase `sync-current-affairs` v3 source captured via Supabase API.  Verify JWT gateway = `false`. Git blob index.ts = `466d4c700994a3aad89c906937f6e046866f031a`. Production function returned exactly one `index.ts` file. It is retained solely as a **known-degraded** rollback reference; the legacy GitHub write-token authorizer yields HTTP 403 under the new workflow caller, so do not label the old pair healthy.

Pre-pause GitHub caller workflow is stored separately as `public-monitoring-feed-legacy.yml` from main `b01070c5cad32afe1aacc2f0c20312354e738e7c`. Do not re-enable it against OIDC-only Edge and do not change production without pausing writer and recording the approved action. This branch contains *no exported student data or runtime credential values*.

Recovery procedure: with production writer paused, use exactly the original index.ts and gateway verify_jwt=false to redeploy to the existing function, then pair with the legacy caller only after a separate deliberate decision. The previous 403 can recur. Maintain a clean failure audit, do not claim successful recovery merely for source rollback.
