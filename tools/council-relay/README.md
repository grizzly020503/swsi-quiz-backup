# SWSI Council Relay — Phase 1 read-only MVP

This folder contains the first local relay implementation for Issue #290.

**Phase 1 is deliberately read-only.** It can review a queued GitHub Council Task with Gemini / Antigravity and post the structured result back to GitHub. It cannot implement code, create branches, push, merge, deploy, or activate paid services.

## Requirements

On the owner Windows account:

- Node.js
- Git
- GitHub CLI (`gh`) authenticated to the private repository
- Antigravity CLI (`agy`) authenticated once interactively

Antigravity headless mode is used; normal relay runs do not open the Antigravity TUI.

## Task issue format

Create an open GitHub issue whose title begins with:

```text
[Council Task]
```

The human-readable body describes what should be reviewed. The same body must contain this machine marker:

```html
<!-- swsi-council-task
{
  "schema_version": 1,
  "task_id": "council-20261002-001",
  "mode": "important",
  "action": "review",
  "related_issue": 290,
  "base_ref": "main",
  "base_sha": "62a184a484d28852a728bb0a147b4e431bc99e6b"
}
-->
```

Phase 1 accepts `action=review` only.

## Dedicated workspace

The relay uses a separate local clone (default under `%LOCALAPPDATA%\SWSI\CouncilRelay\workspace`) instead of switching the owner's normal working clone between branches.

Before every review it:

1. refuses a dirty relay workspace;
2. fetches `origin`;
3. records whether the task's intake `base_sha` has drifted from the current requested remote ref;
4. for Phase 1 read-only review, detaches to the **current** remote ref and exposes any intake/current drift in the evidence metadata;
5. invokes Antigravity in `--mode=plan` headless mode.

Because Phase 1 is read-only, a task queued while the laptop is offline is allowed to review the freshest remote state when the machine returns. The original intake SHA is retained as audit evidence and drift is disclosed. Future write/implementation mode must use a stricter stale-base gate before modifying a branch.

## Antigravity execution

The adapter uses the official headless stream protocol:

```text
agy --input-format stream-json \
    --output-format stream-json \
    --mode=plan \
    --json-schema <review-result.schema.json> \
    --print-timeout 15m \
    --cwd <workspace>
```

The prompt goes over stdin, avoiding Windows command-line prompt-length limits. The terminal `result` event must be `SUCCESS` and contain `structured_output`.

## Idempotency

The relay posts hidden machine markers in GitHub comments:

- `swsi-council-claim`
- `swsi-council-result`

A completed `task_id + adapter` result is not posted twice. A local lock file also prevents two relay processes from running simultaneously on the same Windows account. If Windows loses power and leaves a stale lock file behind, the next relay start checks the recorded PID and removes the stale lock before continuing.

The MVP assumes one owner relay machine. Multi-machine atomic claiming is a later phase.

## Manual smoke test

After installing config, run once:

```powershell
node .\tools\council-relay\relay.mjs --once --config "$env:LOCALAPPDATA\SWSI\CouncilRelay\config.json"
```

For normal use, Task Scheduler runs the relay in watch mode after Windows login.

## Install Windows logon task

Run once from PowerShell while logged into the same Windows account that already authenticated `gh` and `agy`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\council-relay\windows\install-relay.ps1
```

This does **not** change the global PowerShell execution policy.

The scheduled task is named:

```text
SWSI Council Relay
```

Logs are written to:

```text
%LOCALAPPDATA%\SWSI\CouncilRelay\relay.log
```

## What the MVP intentionally does not do

- no implementation/write mode;
- no Coordinator multi-model synthesis yet;
- no Claude/Grok adapters yet;
- no automatic PR or deploy;
- no GitHub Actions orchestrator;
- no local LLM;
- no paid API fallback.

## Local deterministic checks

```powershell
cd tools\council-relay
npm.cmd run check
npm.cmd test
```

Tracking: Issue #290.
