# SWSI Public Repository — Historical Identity Decision Options

Date: 2026-10-04

This document records the two remaining historical identity/privacy decisions that must be made before the repository is switched from Private to Public. It intentionally does **not** contain the actual personal Email address or personal name found in history.

## Scope

Two findings are already known in reachable `main` ancestry:

1. An old admin recovery revision previously embedded a personal Email address in an admin-login field. The current admin UI no longer pre-fills that address.
2. An old public-attribution revision previously contained a personal-name attribution. The current source has already been de-identified and the current privacy QA uses structural attribution patterns instead of hard-coded names.

These are historical identity/privacy exposures. They are **not** evidence of a password, service-role key, provider token, private database dump, or other live credential leak.

## Decision A — historical admin Email linkage

### A1. Accept historical linkage as public history

Use this only if the owner is comfortable with the old Git history showing that the personal address was previously used as an admin identifier.

Required before Public:

- confirm the address is not a secret or recovery credential;
- confirm current UI/source does not pre-fill it;
- preferably ensure the active production admin identity is no longer dependent on that personal address;
- record acceptance in Issue #330.

Pros: no history rewrite; preserves commit SHAs and audit continuity.

Cons: the old relationship between the personal address and SWSI admin access remains discoverable in Git history.

### A2. Move production admin identity to a dedicated non-personal address, then accept history

This is the recommended practical option if the old personal address is still the active admin identifier.

Required before Public:

- migrate the active admin account to a dedicated SWSI-only identity;
- verify admin allow-list / membership and recovery still work;
- remove the personal address from any current production configuration that treats it as the active admin identifier;
- keep the old Git history unchanged;
- record the migration and acceptance in Issue #330 without publishing the address itself.

Pros: materially reduces current identity-targeting risk without rewriting Git history.

Cons: requires an auth/account migration and verification step.

### A3. Rewrite reachable Git history

Use only if the owner requires the old address to be removed from reachable history.

Do **not** perform casually. A rewrite can invalidate commit SHAs, PR ancestry, links, signatures, audit evidence, cached clones, automation references, and recovery documentation.

Minimum requirements:

- freeze repository writes;
- back up refs;
- identify all reachable occurrences;
- rotate/revoke any credential first if a real credential is ever found;
- rewrite all affected refs deliberately;
- force-push only with an explicit coordinated plan;
- re-run the complete history scanner afterward;
- re-check open PR ancestry and automation references.

## Decision B — historical personal-name attribution

### B1. Accept historical attribution as public history

Recommended if the old attribution is not itself sensitive and the current tree is already de-identified.

Required before Public:

- confirm current source does not contain the personal-name literal;
- keep generic privacy regression in place;
- record acceptance in Issue #330.

### B2. Remove it through the same coordinated history rewrite as A3

Do this only if the owner explicitly requires the name to be absent from reachable Git history. Do not perform a second independent rewrite if A3 is already planned; combine the work into one controlled rewrite.

## Recommended default

Unless the owner specifically requires historical erasure:

- **Admin Email:** choose A2 if the old personal Email is still the active production admin identity; otherwise A1.
- **Personal-name attribution:** choose B1.
- Avoid history rewrite unless there is a strong privacy requirement or a true credential leak.

This recommendation minimizes current security/privacy exposure while preserving repository history, PR ancestry, audit evidence, and operational continuity.

## Owner sign-off template

Record one choice for each item in Issue #330 before switching visibility:

- Historical admin Email linkage: `A1 / A2 / A3`
- Historical personal-name attribution: `B1 / B2`
- Decision date: `YYYY-MM-DD`
- Production admin identity migration required before Public: `yes / no`

Do not place the actual personal Email address or personal-name value in this file or in a public Issue comment.