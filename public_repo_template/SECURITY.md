# Security Policy

SWSI is a public learning tool. Please do not post passwords, API keys, tokens, private user data, authentication cookies, or other credentials in public Issues, Discussions, pull requests, screenshots, or logs.

## Reporting a security issue

If the repository offers GitHub's private vulnerability-reporting feature, use that channel for security-sensitive reports. If private reporting is not available, do not paste exploit details or secrets into a public issue; report only that a private security contact is needed.

For ordinary non-sensitive bugs, a normal GitHub Issue is appropriate.

## Security boundaries

- Client-visible URLs and public client configuration are not authorization boundaries.
- Supabase authorization must be enforced through Auth, RLS, grants and the admin allowlist.
- AI provider credentials and internal access keys must remain deployment secrets.
- Cloudflare Worker access checks, rate limits and quota controls must fail closed when their security dependency is unavailable.
- No production service-role key, AI provider key, internal key, Cloudflare token, Netlify token or password belongs in this repository.

## If a secret is accidentally committed

Treat it as compromised even if the commit is later deleted. Revoke or rotate the credential first, then remove it from repository history and verify dependent services before resuming normal deployment.
