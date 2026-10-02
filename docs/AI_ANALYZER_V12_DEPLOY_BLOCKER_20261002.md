# AI Analyzer v12 Production Deployment — 2026-10-02

> Production handoff note. Re-read live GitHub/Supabase state before acting; counts below are timestamped snapshots, not permanent truth.

## GitHub source

- PR #250 merged to `main` at `8e0b4575f3be73c6bb77bd7c283fae29463426f6`.
- Main source blob for `supabase/functions/analyze-pending-questions/index.ts` used for production deployment: `bc9bd36109d467e0f6fe01d2a5509321b39615df`.
- PR #250 adds:
  - one retry for malformed / missing model JSON-array output;
  - one repair audit when the unchanged strict validator rejects the first audited result.
- The validator remains fail-closed and unchanged in policy: exact fields, required nonblank fields, major/mistake allowlists, no unapproved ASCII terms, no newly invented numbers.
- Models remain Qwen 3.8 draft + GPT-OSS audit.
- No question, option, official answer, grading, schema, quota or model-policy change is part of PR #250.

## Production deployment state — CLOSED

- `analyze-pending-questions` is now production **v12 / ACTIVE / verify_jwt=false**.
- Deployment was performed through the authorized Supabase Edge Function connector using the exact `main` source above; no GitHub secret name was guessed and no credential value was read, copied, logged or committed.
- `verify_jwt=false` was preserved from v11. This is not a new auth relaxation: the function continues to enforce its existing server-side custom authentication by comparing the request `x-job-key` against `ai_analysis_job_config.job_key`.
- Live v12 metadata after deployment:
  - function id: `4e7f9587-e2a3-4816-9a66-0e5dbd29723c`
  - status: `ACTIVE`
  - version: `12`
  - verify_jwt: `false`
  - deployed bundle SHA-256: `06b242a734749ade75a3c2fd32c4a71ae99d089053bf85f1fa11978c7c3e44de`
- `Supabase.get_edge_function` was re-read after deploy and the live source contains both PR #250 hardening paths (`formatRetries` and `auditRepairPrompt` / two audit attempts).
- The earlier safety-blocked direct deployment attempt is historical only; do not repeat or work around it. The authorized connector path has now completed deployment successfully.

## Production validation probes

Do not use random questions as the first proof. The review queue contains three standard single-answer rows whose previous failures map directly to the two hardening paths introduced by PR #250:

- `SP-115-2-006` — `AI 回傳找不到 JSON array` (3 attempts before v12)
- `SP-115-2-009` — `exp_others 空白` (3 attempts before v12)
- `SP-115-2-037` — `AI 回傳找不到 JSON array` (3 attempts before v12)

**These three probes have not yet been re-run after v12 deployment.** Keep that distinction explicit: source/version parity is verified; behavioral probe validation is still pending.

When it is safe to run them:

1. first finish Issue #254's required second natural post-fairness cron observation; do not manufacture that observation by requeueing these rows;
2. requeue only these three as a dedicated bounded validation batch, not together with the old-405 backlog;
3. keep Official Core (`question/options/answer/accepted_answers/grading_mode`) unchanged;
4. let the normal one-row / 30-minute cron path process them where practical;
5. verify each reaches `ready` only through the unchanged strict validator;
6. if any still fails, preserve the exact validation error and return it to `review` rather than weakening QA;
7. keep the 25 successful completions / rolling 24h cap unchanged.

`SW-105-2-03` remains a separate quarantine case (prior `exp_others 空白` plus a later transient Qwen HTTP 502). Queue fairness is now deployed, but do not mix that row into the three deterministic v12 probes.

## Queue / scheduler protections still apply

- AI queue fairness migration from PR #256 is live in production.
- `claim_pending_ai_questions(integer)` prioritizes never-attempted rows, then oldest attempted rows using `analysis_last_attempt_at`.
- Max one claimed row per invocation remains enforced.
- Rolling 24h successful-completion cap remains 25.
- Cron job id 3 remains `*/30 * * * *`, body `{"limit":1}`.
- pg_net transport timeout remains 120,000 ms.
- Queue claim RPC remains service-role-only; `anon` and `authenticated` cannot execute it.

## Latest pre-probe snapshot

After the first natural post-fairness cron cycle at 2026-10-02 13:00 Asia/Taipei:

- pending: 11
- analyzing: 0
- ready: 4,684
- review: 105
- completed in previous rolling 24h: 15 / 25

Re-read live counts before any requeue.

## Recovery rules still apply

- Standard + effectively single-answer + old HTTP 405 may be recovered only in bounded batches after the v12 probes are validated.
- Current review split before v12 probes: 60 standard-single old-405 rows; 25 standard multi-answer holds; 16 special-grading holds; 3 deterministic v12 probes; 1 quarantine (`SW-105-2-03`).
- Do not mix multi-answer or special grading into standard infra recovery.
- Genuine content/format failures are not HTTP-405 infrastructure failures.

See also `docs/AI_RECOVERY_HANDOFF_20261002.md` for the broader recovery history and queue-fairness rollout.
