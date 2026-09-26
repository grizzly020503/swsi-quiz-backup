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

1. Add both GitHub Actions secrets.
2. Go to Actions -> **Netlify Controlled Production Deploy**.
3. Choose **Run workflow** on `main`.
4. The workflow refuses any non-main ref.
5. It rebuilds `_site` using the exact `netlify.toml` build command.
6. It verifies the history-v2.2 release contract before upload.
7. It deploys `_site` with a pinned Netlify CLI.
8. It verifies `https://swsi-quiznetlify.netlify.app` by HTTP and Chromium smoke tests.

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

Netlify keeps prior production deploys. If the controlled release fails post-deploy verification, use Netlify Deploys to restore the last known-good production deploy while the cause is investigated.
