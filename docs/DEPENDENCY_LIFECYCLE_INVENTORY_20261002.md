# SWSI Dependency / Runtime Lifecycle Inventory

Issue: #281  
Scope: read-only inventory and drift policy only.

## Purpose

Long-lived operation cannot assume the same GitHub Actions majors, Python/Node runtimes, browser tooling, package services or Deno/Supabase remote import hosts will remain available for 10/20/30 years. This work package makes those dependencies observable without upgrading them.

## Commands

```bash
python3 scripts/dependency_inventory_selftest.py
python3 scripts/dependency_inventory.py --check-determinism --output /tmp/swsi_dependency_inventory.json
```

Both commands are zero-network and require no GitHub, Supabase, Cloudflare or Netlify credentials.

## Inventory scope

The generator scans:

- `.github/workflows/*.yml` / `*.yaml`
  - external `uses:` action refs;
  - `python-version`;
  - `node-version`;
  - versioned CLI/package tokens such as Playwright or Netlify CLI when present in workflow text.
- `supabase/functions/**`
  - `jsr:` imports;
  - `npm:` imports;
  - `esm.sh` imports;
  - `deno.land` imports.
- repo package/runtime manifests and lock/config files when they actually exist.

The scanner does not invent a package manager or provider that is not present in the repository.

## Drift semantics

A drift finding means the same dependency/runtime is referenced by more than one ref. It does **not** mean the older or newer ref is wrong.

High severity is reserved for cross-major drift in GitHub Actions, Python or Node runtime records. Other multiple-ref findings are medium review signals by default.

Every finding is `review_only_do_not_auto_upgrade`. The inventory does not edit workflow files, install packages, open upgrade PRs or change production runtime.

Pin classifications include:

- `commit_sha`
- `exact_version`
- `minor_pin`
- `major_only`
- `floating`
- `dynamic`
- `other`

## Lifecycle metadata

`data/dependency_lifecycle_policy.v1.json` supplies the default metadata attached to each discovered record:

- criticality;
- core vs enhancement;
- fallback class;
- whether paid service is required;
- upgrade gate.

The generated record additionally carries `owner_role`, `replacement_path`, and `last_verified_date`. `last_verified_date` remains null until that dependency/provider has actually been checked; discovery alone must not be represented as lifecycle verification.

Provider EOL/deprecation evidence should later populate a verified date and concrete replacement path. A new major is never accepted merely because it is newer.

## Cost and safety boundaries

- no Dependabot/Renovate activation in this work package;
- no automatic dependency upgrade;
- no automatic merge;
- no new paid service;
- no production deploy/runtime mutation;
- no new scheduled GitHub Actions workflow;
- provider failure follows `ZERO_COST_OPERATIONS.md` and #279 bounded recovery rather than silently buying or switching services.

## Deterministic fixture coverage

The self-test covers:

- `actions/checkout@v3` vs `@v4` major drift;
- Python 3.11 vs 3.12;
- Node 20 vs 22.13.0;
- Playwright exact pin discovery;
- Deno std import;
- `esm.sh` scoped package import;
- JSR import;
- stable repeated inventory output;
- global no-auto-upgrade policy and per-record upgrade/cost metadata.

## Remaining acceptance evidence

Before closing #281, run the generator on the exact current repository checkout and retain a compact summary of the observed drifts. Do not commit a large generated diagnostic snapshot merely to prove the scanner runs; the script and policy are the durable source, while generated reports may be regenerated from a checked-out revision.
