# GitHub Actions budget policy — 2026-10-02

## Why this exists

The project owner treats 2,000 GitHub Actions minutes per month as the hard operating budget. The repository must therefore prefer useful automation over repeated CI churn.

Live audit on 2026-10-02 found 522 workflow runs since 2026-10-01 00:00 UTC:

- pull_request: 345
- push: 144
- workflow_run: 25
- schedule: 7
- other/manual: 1

The dominant cost is development churn, not the low-frequency production schedules.

## Required development mode

1. Build the branch first. Do **not** open a PR while routine implementation commits are still being added.
2. Batch related file changes before opening the PR.
3. Open the PR only when the branch is ready for CI review.
4. After the PR is open, push again only to fix a real review/CI finding or a necessary rebase.
5. Prefer one broad, evidence-backed PR over many tiny PRs when the changes form one safe unit.
6. Keep path filters narrow. A QA workflow should not run for unrelated documentation or generated files.
7. PR/read-only QA should use `concurrency.cancel-in-progress: true` so a newer revision supersedes an older one.
8. Main/scheduled workflows that mutate official data may keep `cancel-in-progress: false` when interruption could leave a partially completed write boundary.

## Steady-state schedules retained

These schedules are intentional safety baselines and should not be removed merely to save minutes:

- Public Monitoring Feed: every 6 hours
- Ops Task Freshness Watchdog: every 6 hours
- Public Uptime Sentinel: daily
- Question Shards: daily
- MOEX Social Worker Exam Sync: weekly
- Full Corpus Question QA: monthly

Changing these cadences requires evidence that freshness/SLO requirements are still met.

## Workflow-run fan-out rule

A completed upstream workflow should have one clear downstream owner for each responsibility. Avoid two upstream events that cause the same expensive downstream workflow to rebuild the same state twice. Scheduled fallback is preferred over duplicate immediate fan-out when the second trigger provides no distinct data dependency.

## Budget guardrails

Project operating targets (not GitHub billing claims):

- target steady state: <= 500 minutes/month
- review threshold: 1,000 minutes/month
- conservation mode: >= 1,500 minutes/month used — defer nonessential CI and combine changes
- hard budget assumption: 2,000 minutes/month

The authoritative remaining balance is the GitHub account Billing/Usage page; repository APIs do not expose the owner's account billing balance through the current connector.

## Current optimization patch

This patch adds cancellation for superseded read-only QA runs in:

- Essay Enrichment Overlay QA
- Essay Enrichment Supabase Sync QA
- Exam Scheme Versioning QA
- Full Corpus Question QA

It deliberately does **not** enable cancellation for MOEX official-data sync.

## Future follow-up

- Remove redundant immediate `workflow_run` fan-out where one upstream completion already leads to another downstream workflow and a scheduled fallback exists.
- Audit workflows with `push` triggers that are not restricted to `main`; if a PR equivalent exists, feature-branch push duplication should normally be removed.
- Track run counts by event monthly; do not create another scheduled workflow merely to measure Actions usage unless the measurement cost is justified.
