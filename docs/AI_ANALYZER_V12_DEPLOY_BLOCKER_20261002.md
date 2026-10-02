# AI Analyzer v12 Deployment Boundary — 2026-10-02

> Production handoff note. Re-read live GitHub/Supabase state before acting; counts below are a timestamped snapshot, not a permanent truth.

## GitHub state

- PR #250 merged to `main` at `8e0b4575f3be73c6bb77bd7c283fae29463426f6`.
- Main push checks completed successfully:
  - AI Analyzer Route QA #8: success.
  - Disaster Recovery Restore Drill #56: success.
- The merged analyzer change adds:
  - one retry for malformed model JSON-array output;
  - one repair audit when the unchanged strict validator rejects the first audited result.
- The validator remains fail-closed and unchanged in policy: exact fields, required nonblank fields, major/mistake allowlists, no unapproved ASCII terms, no newly invented numbers.
- Models remain Qwen 3.8 draft + GPT-OSS audit.
- No question, option, official answer, grading, schema, auth, or quota change is part of PR #250.

## Production deployment state

- **Do not claim PR #250 is deployed to Supabase production yet.**
- At the last live check, `analyze-pending-questions` is still production **v11 / ACTIVE / verify_jwt=false** with the pre-#250 analyzer source.
- A direct connector deploy of the merged source was blocked by the platform safety layer before Supabase accepted any deployment. No partial production deployment occurred.
- Do not bypass that safety block by obfuscating credentials, splitting secret-related code merely to evade scanning, exposing secret values, or changing the authentication model just to force a deploy.
- There is no known repository GitHub Actions workflow with a confirmed Supabase function deployment credential. Do not invent a secret name.
- Safe next action: deploy the exact merged main source only through an authorized Supabase deployment path that can handle the existing server-side authentication architecture without exposing credentials; then re-read the live function and verify the new version/source before calling it deployed.

## Production validation probes after v12 deploy

Do not use random questions as the first proof. The current review queue contains three standard single-answer rows whose failures map directly to the two hardening paths introduced by PR #250:

- `SP-115-2-006` — `AI 回傳找不到 JSON array` (3 attempts)
- `SP-115-2-009` — `exp_others 空白` (3 attempts)
- `SP-115-2-037` — `AI 回傳找不到 JSON array` (3 attempts)

After v12 is confirmed live by re-reading the deployed function source/version:

1. requeue these three as a **dedicated bounded validation batch**, not together with the old-405 backlog;
2. keep Official Core (`question/options/answer/accepted_answers/grading_mode`) unchanged;
3. verify each reaches `ready` only through the unchanged strict validator;
4. if any still fails, preserve the exact validation error and return it to `review` rather than weakening QA;
5. keep the cron cadence, one-row claim limit, and 25 successful completions / rolling 24h cap unchanged.

`SW-105-2-03` is a separate quarantine case (prior `exp_others 空白` plus a later transient Qwen HTTP 502). Do not put it ahead of the three deterministic v12 validation probes until queue fairness/backoff is addressed or the main pending queue is clear.

## Recovery snapshot

At approximately 2026-10-02 12:44 Asia/Taipei:

- pending: 12
- ready: 4,683
- review: 105
- completed in previous 24h: 14 / 25 safety cap

The existing production cron remains every 30 minutes, one claim at a time. PR #252 extended only the pg_net transport timeout to 120 seconds; live `cron.job.command` was verified to contain `timeout_milliseconds := 120000`. Do not increase cadence or bypass the 25/day guard merely to clear backlog faster.

## Recovery rules still apply

- Standard + effectively single-answer + old HTTP 405 may be recovered in bounded batches.
- Current review split: 60 standard-single old-405 rows; 25 standard multi-answer holds; 16 special-grading holds; 3 deterministic format/validator failures above; 1 transient/validator quarantine (`SW-105-2-03`).
- Do not mix multi-answer or special grading into standard infra recovery.
- Genuine content/format failures (`AI 回傳找不到 JSON array`, `exp_others 空白`, etc.) are not HTTP-405 infrastructure failures.
- Existing production v11 can still recover items; #250 is a reliability hardening to absorb common one-off format failures before they consume DB attempts.

See also `docs/AI_RECOVERY_HANDOFF_20261002.md` for the broader recovery history, queue-starvation finding, and already-verified production probes.
