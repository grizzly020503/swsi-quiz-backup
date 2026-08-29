# SWSI Zero-Cost Operations Policy

## Purpose
SWSI is a free public social-worker exam study platform. The default operating assumption is **NT$0 / US$0 recurring infrastructure spend**. Paid upgrades may never become a prerequisite for keeping the student-facing core usable.

The product should remain useful even when CI minutes, AI quota, feedback automation, or a non-core backend service is temporarily unavailable.

## Non-negotiable availability rule
The following student-facing core must not depend on GitHub Actions being available:
- Home / navigation
- 4,800 official multiple-choice questions
- standard / all_credit / any_answer grading contracts
- practice sessions
- mock exams
- wrong-answer review
- local learning progress / spaced review
- essay library / writing
- local essay drafts

If GitHub Actions, AI, Admin, or feedback automation is unavailable, these functions should continue to work whenever their existing static/local dependencies are available.

## Graceful degradation
Treat automation and cloud services as enhancements, not single points of failure.

| Dependency unavailable | Required behavior |
| --- | --- |
| GitHub Actions quota exhausted | Production site stays online; automated QA/sync/publish pauses until quota returns |
| AI provider unavailable | Preserve the user's answer/draft; show a plain-language retry/fallback message; do not block studying |
| Feedback pipeline unavailable | Core study continues; feedback may show retry-later behavior |
| Admin unavailable | Student-facing experience is unaffected |
| MOEX sync temporarily unavailable | Keep serving the last verified official corpus; do not replace it with unverified data |
| New shard publish temporarily unavailable | Keep serving the last verified shard set |

## GitHub Actions budget policy
The owner does not plan to pay for recurring GitHub Actions usage. Included monthly minutes are a finite shared maintenance budget.

Current known allowance: 2,000 included GitHub Actions minutes per billing cycle. The 2026-08-29 allowance was exhausted and GitHub reported reset on 2026-09-01.

Long-term target: normal maintenance should leave **at least 70-80% of the monthly included Actions allowance unused** whenever practical.

### Actions priority order
1. Official-data safety / release-critical invariants.
2. MOEX sync checks that can discover genuinely new official data.
3. Release-candidate full QA immediately before public deployment.
4. Everything else only when evidence justifies the cost.

### Actions conservation rules
- Do not run the full browser suite for documentation-only changes.
- Do not run the full browser suite for trivial copy-only changes unless the copy affects routing, grading, auth, legal/source trust, or release behavior.
- Use path filters so unrelated changes do not start expensive workflows.
- Use concurrency cancellation for superseded PR runs where safe.
- Prefer cheap syntax/static/invariant checks before browser installation or browser execution.
- Keep full Chromium/WebKit/storage/launch suites as release gates or deliberate manual runs rather than default-on for every small commit.
- Do not rerun a failed zero-step job repeatedly when account quota is known to be exhausted.
- Netlify build-time fail-closed static checks may provide release evidence without consuming GitHub-hosted runner minutes.

## MOEX synchronization policy
Official exam releases are infrequent; polling should reflect that.

Normal mode:
- Check no more frequently than weekly unless there is a known exam-release window or a maintainer request.
- First perform the cheapest possible change-detection step.
- If no new official exam/source revision exists, stop without rebuilding/publishing the full corpus.

Release-window mode:
- Temporarily increase checking only near an expected MOEX release.
- Restore the low-frequency schedule after the release is ingested and verified.

Never change official answers, accepted_answers, grading_mode, or historical official data automatically without verified official evidence.

## Question-shard publication policy
Do not rebuild or publish question shards merely because a scheduled job ran.

Use deterministic content/version checks:
- If canonical question content and shard manifest/checksum are unchanged, stop.
- Publish only when verified source data actually changed.
- Preserve the last known-good shard set when publishing is unavailable.

## Feedback maintenance policy
Feedback collection and triage should stay useful without becoming a cost driver.

- Collect only data needed to reproduce/triage a report.
- Do not require student accounts for ordinary studying.
- Avoid storing unnecessary personal analytics.
- Deduplicate and cluster before expensive analysis.
- Process bounded batches.
- Increase triage frequency only when report volume justifies it.
- AI triage must never auto-merge, deploy production, or auto-change official answers/grading/legal/auth/security/migrations/secrets.

## Local-first data policy
Prefer local/device storage for personal study state when server synchronization is not essential.

Good local-first candidates:
- wrong-answer state
- spaced-review state
- learning progress
- essay drafts
- target exam date / non-sensitive preferences

Use Supabase for data that genuinely benefits from a central source of truth, such as official shared data, feedback, admin operations, and required metadata. Avoid turning every student click into a database write.

## Backup / rebuild policy
The repository must contain enough non-secret source-of-truth material to rebuild the platform without relying on one hosted service.

Preserve:
- canonical official question data / generation sources
- grading contracts
- accepted_answers
- essay source/generation data
- metadata and source-provenance rules
- database migrations
- Edge Function source
- build / QA scripts
- release handoff documentation

Never commit service-role keys, passwords, private tokens, admin sessions, raw private contact information, or other credentials.

## Operating cadence
### Routine operation
The site should require little or no manual intervention. Student-facing core remains available while enhancement services may degrade safely.

### Weekly
When free capacity permits:
- cheap MOEX new-source check
- feedback backlog / high-risk review
- one concise system-health review when useful

### Monthly
When free capacity permits:
- official corpus integrity count
- grading invariant check
- metadata/backlog review
- storage/free-tier usage review
- basic production smoke
- review GitHub Actions minute consumption and reduce unnecessary triggers if usage is high

### Release only
Before a meaningful public release:
- final diff / secret / artifact scan
- full release QA when GitHub-hosted quota is available
- Netlify Deploy Preview verification
- required manual E2E for changed high-risk flows (for example feedback or admin recovery)
- explicit maintainer merge approval
- explicit production deploy approval
- post-deploy production smoke and invariant recheck

## Cost-exhaustion behavior
Reaching a free-tier limit is an operational event, not a reason to weaken tests or corrupt production data.

When a free allowance is exhausted:
1. Stop non-essential automated runs.
2. Keep the last verified production state.
3. Do not pay by default.
4. Wait for the free allowance reset when reasonable.
5. Use existing alternate/read-only evidence for diagnosis, but do not pretend a skipped hosted test passed.
6. Resume only the highest-value checks after reset.

## Product principle
SWSI should optimize for **sustainable usefulness**, not maximum automation.

Success means a student can continue preparing for the social-worker national exam for free even when the maintainer has no operating budget. Automation should reduce maintenance burden; it must not create a recurring financial obligation or make the core product fragile.
