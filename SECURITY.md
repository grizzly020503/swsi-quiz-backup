# Security Policy

SWSI treats security, exam-data integrity, and production credential isolation as release-critical concerns.

## Supported code

Security fixes should target the current `main` line and the currently supported production release. Historical snapshots may remain available for auditability but are not independently maintained as supported releases.

## Reporting a vulnerability

Please do **not** publish secrets, access tokens, private user information, working exploit payloads, or sensitive production details in a public Issue, Pull Request, discussion, screenshot, or log.

Preferred reporting path:

1. Use GitHub private vulnerability reporting / a private security advisory if it is enabled for this repository.
2. If a private reporting channel is not available, open a minimal public Issue that says a security problem needs a private contact path. Do not include the exploit, secret, credential, private user data, or reproduction detail that would make abuse easier.

Maintainers will triage reports on a best-effort basis and may ask for a minimal reproduction in a private channel.

## High-priority security scope

Examples include:

- authentication or admin-authorization bypass;
- Supabase RLS / database privilege bypass;
- exposure of service-role keys, API keys, tokens, passwords, MFA/recovery material, or private backups;
- Cloudflare / AI proxy quota or rate-limit bypass that can create abuse or unexpected cost;
- stored or reflected script injection through database, AI, current-affairs, feedback, or other dynamic text;
- release-pipeline or GitHub Actions paths that allow untrusted code to obtain production secrets;
- integrity failures that allow official exam wording, official answers, accepted answers, or grading modes to be silently altered;
- supply-chain compromise in release-critical dependencies or actions.

## Credential policy

Production credentials must remain outside the repository. Source code may reference environment-variable or GitHub Secret **names**, but credential **values** must not be committed, copied into fixtures, printed into logs, pasted into Issues/PRs, or embedded in generated artifacts.

If a credential value is ever committed or printed, removing it from the latest file is not sufficient. Treat the credential as compromised: revoke/rotate it first, then clean history or logs as appropriate.

## Data-integrity boundary

SWSI separates official exam content from SWSI-authored learning material. Security or data-integrity changes must not silently rewrite official question wording, options, official answers, accepted-answer sets, or grading modes.

AI-generated or SWSI-authored explanations are enhancement layers and must not be presented as official examination authority.

## Public repository boundary

Making this repository public does not make production credentials, private backups, user reports, administrator data, or provider-account recovery information public. Those materials must remain in external secret stores or explicitly private operational storage.
