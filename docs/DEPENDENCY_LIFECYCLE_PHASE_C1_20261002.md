# Dependency / Runtime / API Lifecycle — Phase C-1

Issue: #281

This work is inventory-only. It does not upgrade any dependency, runtime, action, model, provider, or plan.

## Live-main findings observed before implementation

The repository currently contains legitimate but non-uniform version choices that should be tracked rather than silently normalized:

- `actions/checkout` appears at multiple majors including v4, v5 and v7.
- `actions/setup-python` appears at multiple majors including v5 and v7.
- Python workflow runtimes include 3.11 and 3.12.
- `actions/setup-node` appears at v4 and v7.
- Node workflow runtimes include 20 and exact 22.13.0.
- Playwright is commonly pinned to 1.55.0.
- axe-core appears pinned to 4.13.0 in launch/release browser QA.
- Netlify CLI is pinned to 27.9.0 in controlled production deployment.
- Supabase Edge Functions use both `jsr:@supabase/supabase-js@2` and `https://esm.sh/@supabase/supabase-js@2` import forms.
- Analyzer model IDs include `qwen/qwen3.8-27b` and `openai/gpt-oss-120b`.

These observations are **drift inventory**, not a claim that newer versions should replace older ones immediately.

## Inventory tool

`scripts/dependency_lifecycle_inventory.py` is zero-network and read-only. It scans:

- GitHub Actions `uses:` refs;
- Python / Node runtime versions;
- container image tags;
- selected pinned CLI/browser dependencies (Playwright, axe-core, Netlify CLI, Wrangler);
- pip-install commands and whether packages are exact/range/unpinned;
- Supabase/Deno remote imports and their source host (for example JSR vs esm.sh);
- source-defined AI model IDs;
- common dependency manifest / lock files when they exist.

Output is stable-sorted with stable dependency IDs. Drift is reported when the same dependency has multiple versions, remote import sources differ, or refs are non-exact/floating/unpinned.

## Policy

`data/dependency_lifecycle_policy.v1.json` deliberately sets:

- `auto_upgrade=false`;
- `auto_merge=false`;
- `paid_upgrade_allowed=false`;
- major runtime/action/provider/model changes require review;
- security fixes still require relevant tests;
- fallback providers/models require equivalent quality evidence;
- quota exhaustion never weakens safety gates.

## Self-test evidence

The zero-network fixture verifies:

- mixed `actions/checkout` majors are detected;
- mixed Python runtimes are detected;
- JSR / esm.sh import-source drift for the same Supabase package is detected;
- unpinned pip packages are surfaced;
- exact pip pins are preserved;
- AI model IDs are inventoried;
- repeated scans of identical input are byte-equivalent at the data-structure level.

Local fixture result before branch checkpoint: **PASS** (`deterministic=true`).

## Not done in this phase

- no Dependabot or Renovate enabled;
- no automated PR creation;
- no dependency upgraded;
- no workflow version normalized;
- no provider/model switched;
- no production deploy/runtime changed;
- no paid plan or service introduced.

A later phase may use this inventory to create candidate upgrade PRs, but major/provider/model changes must remain review-gated and must not auto-merge.
