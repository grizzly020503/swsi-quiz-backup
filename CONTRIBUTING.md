# Contributing to SWSI

Thanks for helping improve SWSI. The project exists to make social-worker national-exam preparation more accessible while preserving official-source integrity and long-term maintainability.

## Before changing code

1. Read `README.md`, `PROJECT_HANDOFF.md`, `AGENTS.md`, and the documents relevant to the area you are changing.
2. Re-check the current `main`, open Pull Requests, open Issues, and relevant CI/release status. Do not assume an old SHA or chat summary is still current.
3. Search for an existing runtime owner, script, data model, or test before adding a parallel implementation.
4. Keep the change scoped. Do not combine a bug fix with unrelated cleanup or cosmetic refactoring.

## Official Core is special

Official examination content is not ordinary editable app copy.

Do not silently alter:

- official question wording;
- official options;
- official answers;
- `accepted_answers`;
- `grading_mode`;
- official exam identity / source metadata.

When official-source evidence and repository data disagree, fail closed and create a reviewable finding instead of guessing.

## AI and explanations

SWSI-authored explanations, classifications, theory links, legal links, and AI feedback are learning layers. They must not be presented as official examination authority.

If confidence is insufficient, prefer an explicit review state over fabricated completeness.

## Security and privacy

Never commit or paste:

- service-role keys;
- API keys or provider tokens;
- passwords;
- MFA / recovery codes;
- private backups;
- private user data;
- administrator personal identifiers;
- secrets copied from logs or local environment files.

Environment-variable names and documented secret *names* are allowed; secret *values* are not.

See `SECURITY.md` for vulnerability-reporting rules.

## Development flow

Prefer:

`branch -> focused change -> deterministic/local tests -> Pull Request -> review -> CI -> merge`

Avoid direct changes to production and avoid force-pushing validated release history unless there is a documented, necessary recovery reason.

A Pull Request should explain:

- the user-visible or operational problem;
- the root cause;
- the exact scope of the change;
- what was deliberately not changed;
- tests / evidence;
- data, security, migration, or deployment risks.

## Testing

Follow `TESTING.md` and the regression tests owned by the changed area. At minimum:

- syntax / deterministic checks must pass;
- no credential value may appear in the diff;
- official exam content must remain protected;
- changes to grading, legal mappings, schema, authentication, production deployment, or security require stronger evidence than cosmetic UI changes;
- a failed CI job must be diagnosed as code, data, infrastructure, quota, permission, or configuration failure before changing code to make the light green.

Do not delete or weaken a release gate just to obtain a passing run.

## Public-source and copyrighted material

Prefer links, metadata, short summaries, and structured facts over copying third-party articles or copyrighted explanatory text into the repository.

Government / official exam material must keep provenance and must not be represented as SWSI-authored content.

## Dependencies

Avoid adding a dependency when the standard library or an existing project dependency can safely do the job. Release-critical GitHub Actions and package versions should remain pinned or otherwise deliberately controlled.

## Public repository operations

A public repository is not permission to expose internal operations. Credentials, private backups, incident-sensitive details, user reports, and provider-account recovery material remain private even when source code is public.

License selection for SWSI-authored source code is a maintainer decision. Do not assume that public visibility automatically grants reuse rights beyond the license actually committed to the repository.
