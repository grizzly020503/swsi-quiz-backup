# Independent observation of GitHub scheduled maintenance

Cloudflare Cron executes the production Worker's `scheduled` handler every 15 minutes. It performs exactly six bounded GET requests to public GitHub workflow history, using the existing `ops_task_registry.v1.json` task IDs/freshness windows. Contract tests reject registry drift. It does not require GitHub credentials, run AI, invoke Supabase, retry tasks, change quiz data or send messages.

`GET /ops/task-heartbeat` reads the last observation only. It never starts a probe or writes data. Before the first real schedule or after 45 minutes without evidence it returns 503 with `independent_monitoring_active=false`. The one-row `ops_task_heartbeat` D1 table is separate from quota counters and stores public task metadata only. Older/repeated ticks cannot replace newer evidence. The scheduled handler creates only this additive table; the recovery bootstrap also includes its schema.

Observer freshness and task health are separate: a fresh observer can report a failed MOEX schedule. Manual runs and PR checks never substitute for successful scheduled maintenance. Other heartbeat components explicitly remain `unknown/not_probed`; this is not an AI, grading or private-backup acceptance claim.

The observer is independent of GitHub Actions scheduling, but shares the Cloudflare account with the site. Existing GitHub uptime checks remain complementary. No claim of full multi-provider failure independence is made. GitHub API errors/limits remain visible as `error`; source failures are never called healthy.

Activation evidence must come from an actual scheduled record, not CI fixtures or a deployment success. The main-only acceptance job waits for that record and checks all six GitHub observations are readable. Cron changes can take up to 15 minutes to propagate, followed by the next scheduled tick. Rollback: remove the Cron trigger and handler/route through a tested release; leave the single non-sensitive D1 row intact. Never drop quota tables.

References: https://developers.cloudflare.com/workers/configuration/cron-triggers/ and https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/ .
