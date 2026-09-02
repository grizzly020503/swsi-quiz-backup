# swsi-usage

Public anonymous page-view collector for SWSI Usage Analytics V1.

Deployment contract:

- Deploy only after migration `20260902143000_add_anonymous_usage_analytics.sql` is applied.
- This function is intentionally public (`verify_jwt=false`) because students do not sign in.
- Authorization is replaced by a strict single-production-Origin boundary, a random client-ID format check, a tiny body limit, and a single allowed `page_view` event.
- The raw random client ID is SHA-256 hashed before the service-role RPC and is never stored directly.
- Do not add raw IP, User-Agent, device fingerprint, email, or other identity fields.

Production origin:

`https://wandering-wave-4418.c022050333.workers.dev`
