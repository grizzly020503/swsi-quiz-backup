# Netlify controlled production deployment

SWSI uses Cloudflare as the primary production path and Netlify as a fallback. Netlify should not independently rebuild arbitrary Git pushes once the controlled pipeline is proven.

## Target architecture

```text
main
  -> build the Netlify publish directory from netlify.toml
  -> verify release contract
  -> deploy the prebuilt _site directory to the existing Netlify project
  -> verify production HTTP
  -> run real-browser smoke tests
```

This keeps the release artifact and verification under GitHub Actions control instead of depending on Netlify's repository build state.

## One-time secrets

Create these repository Actions secrets in GitHub. Never commit their values.

- `NETLIFY_AUTH_TOKEN`
  - Netlify personal access token used only by GitHub Actions.
  - Netlify documents `NETLIFY_AUTH_TOKEN` as the CI environment variable for CLI authentication.
- `NETLIFY_SITE_ID`
  - Netlify UI calls this the **Project ID**.
  - Find it at: Project configuration -> General -> Project details -> Project information.
  - It identifies the existing `swsi-quiznetlify` project. Do not create a new project.

The token value must not be pasted into issues, PRs, chat, workflow files, screenshots, or logs.

## First cutover run

1. Confirm both GitHub Actions secrets exist. Change credentials only with Owner authorization; never print their values.
2. Go to Actions -> **Netlify Controlled Production Deploy**.
3. Choose **Run workflow** on `main` with the default `release_mode=verify_only`.
4. The workflow refuses any non-main ref.
5. The read-only preflight checks token access, the configured site ID and the existing SWSI project identity. A missing secret, HTTP 401/403/404 or wrong project blocks the run. It does not build or deploy and is not evidence of runtime parity.
6. After explicit Owner release authorization, start a separate run on the reviewed exact `main` commit with `release_mode=deploy`. Record its SHA and Run ID. A default dispatch never publishes.
7. The deploy run repeats the preflight, rebuilds `_site` using the exact `netlify.toml` command, verifies the release contract and uploads with the pinned CLI.
8. It verifies `https://swsi-quiznetlify.netlify.app` by HTTP and Chromium smoke tests, including exact runtime and Service Worker bytes. Separately verify the primary site, old IndexedDB/PWA updates and mobile behavior.

Only after this first controlled deployment is green should the old Netlify repository continuous-deployment connection be disabled/unlinked.

## Cutover safety rule

Do **not** unlink the Git repository first. Keep the current Netlify project and URL intact until the controlled GitHub Actions deployment succeeds.

After the first successful controlled deployment:

- Cloudflare remains the primary site.
- Netlify remains the fallback site.
- Disable/unlink Netlify's independent repository continuous deployment.
- Keep the GitHub Actions workflow as the only Netlify release path.
- A later follow-up may add a carefully scoped automatic trigger from `main`; the bootstrap workflow intentionally starts as `workflow_dispatch` only.

## Rollback

Before release, record the last known-good deploy ID and retain its matching source, runtime and manifest. If post-deploy verification fails, use Netlify Deploys to restore that exact deploy, then repeat HTTP/runtime/Service Worker and primary/fallback parity checks. Do not claim recovery from the dashboard status alone. Keep any independent repository build trigger from overwriting the rollback during the incident, under Owner authorization.

For the coordinated Supabase caller/function switch, use [the cutover runbook](CURRENT_AFFAIRS_OIDC_CUTOVER.md). Netlify credential verification does not authorize that switch.
