# SWSI AI Council Relay — Target Architecture

> Status: target architecture / Phase 0 contract. This document defines the desired low-touch multi-AI operating model. It does **not** mean the full relay is already implemented.

## 1. Why this exists

SWSI should not require the owner to become a human router between ChatGPT, Gemini, Claude, Grok, or future AI systems.

The target experience is:

- the owner can submit work from a phone, tablet, or any computer;
- the private GitHub repository is the durable coordination and evidence layer;
- the owner's Windows laptop acts as a lightweight relay when it is online;
- AI providers are called sequentially through adapters;
- Council members analyse independently before seeing one another's conclusions;
- one Coordinator reconciles evidence and disagreements;
- only one Implementer writes the work branch;
- independent reviewers verify the actual diff and tests afterward;
- the owner does not have to copy/paste model outputs between chats;
- high-risk merge, production deploy, secrets expansion, and paid services remain explicit owner boundaries.

This infrastructure must **not** block SWSI product release or student-facing data closeout.

## 2. Core topology

```text
Phone / tablet / any computer
          |
ChatGPT / Claude / Gemini / other connected AI
          |
          v
Private GitHub repository
Council task queue + durable evidence + state
          |
          v
Owner Windows laptop
SWSI Council Relay (background, auto-start, low-resource)
          |
          +--> Gemini / Antigravity adapter
          +--> Claude adapter (disabled until verified)
          +--> Codex / ChatGPT-compatible adapter (disabled until verified)
          +--> Grok / other adapters (disabled until verified)
          |
          v
Independent proposals
          |
Coordinator synthesis
          |
Single Implementer
          |
Local/static tests -> branch -> PR-last
          |
Verification Council
          |
GitHub result / evidence / next action
```

## 3. Operating principles

### 3.1 GitHub is the durable control plane

GitHub stores task state, related Issue/PR references, evidence pointers, review results, and completion state.

A laptop shutdown must not lose a queued task. When the laptop returns online, the relay resumes from durable state.

### 3.2 The laptop is a relay, not an inference server

The owner's older Windows laptop should only handle:

- private repo clone;
- Git / GitHub CLI;
- lightweight Python / Node orchestration;
- AI provider CLI adapters;
- local/static tests;
- checkpoint state.

Do not require local 30B/70B inference, Ollama, heavy Docker, or multiple always-on agents.

### 3.3 Sequential execution by default

To protect laptop resources and reduce provider/quota collisions, run one main agent at a time. Council members may be logically independent while still executing sequentially.

### 3.4 One writer

Only the designated Implementer may modify the work branch. Reviewers are read-only by default.

### 3.5 Council is evidence reconciliation, not voting

A 3-to-1 or 4-to-0 model vote does not establish truth.

Coordinator decisions must prefer:

1. official source / existing contract where applicable;
2. live production evidence;
3. current GitHub remote / exact deployment evidence;
4. current source/data files;
5. tests and reproducible outputs;
6. documentation snapshots;
7. AI inference.

## 4. Task classes

### Normal

Use one Implementer and zero or one Reviewer.

Typical examples:

- narrow documentation change;
- cosmetic fix with regression coverage;
- small deterministic script correction.

### Important

Use 2–3 independent proposals, Coordinator synthesis, one Implementer, then 1–2 independent verifiers.

Typical examples:

- data-pipeline change;
- workflow change;
- new long-lived automation;
- non-trivial schema-adjacent change.

### High Risk

Use 2–4 independent reviewers plus evidence reconciliation and post-implementation Verification Council.

Typical examples:

- Official Core;
- grading / accepted answers;
- database migration;
- auth / RLS / security;
- historical-law trust decisions;
- release-critical infrastructure;
- cloud/provider migration.

Unknown or unverifiable states fail closed.

## 5. Council roles

### Council Member

- receives the same frozen task brief and evidence scope;
- first-round analysis should not include other members' conclusions;
- records evidence source and freshness;
- separates facts, findings, risks, and suggestions.

### Coordinator

- compares independent analyses;
- identifies shared findings, disagreements, stale assumptions, and evidence gaps;
- resolves conflicts with evidence rather than model reputation;
- defines the implementation contract;
- appoints one Implementer.

### Implementer

- works only inside allowed scope;
- writes one branch;
- does not silently broaden requirements;
- runs local/static checks before PR;
- follows PR-last / Actions budget policy.

### Verification Council

- reads the exact diff and actual test evidence;
- does not accept the Implementer's summary as proof;
- returns PASS, FINDING, BLOCKED, or EVIDENCE_MISSING;
- repair loops must be bounded.

### Owner

Owner approval remains required where existing SWSI policy requires it, especially for:

- production release / merge boundaries;
- irreversible data operations;
- new paid services or subscriptions;
- wider secret / credential permissions;
- major product-direction changes.

## 6. Council Task contract

The first implementation should keep the task contract small, structured, and provider-neutral.

Minimum fields:

```yaml
task_id: council-YYYYMMDD-NNN
source: owner|chatgpt|claude|gemini|other
mode: normal|important|high_risk
requested_at: ISO-8601
requested_by: owner
related_issue: optional
base_ref: main
base_sha: exact intake SHA
status: queued|claimed|reviewing|synthesizing|implementing|verifying|blocked|done|failed
allowed_write_scope: []
forbidden_operations: []
budget_policy: docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md
```

Recommended additional runtime fields:

```yaml
claimed_by: relay-instance-id
claim_started_at: ISO-8601
attempt: integer
checkpoint: string
result_ref: optional GitHub comment / artifact / file reference
error_class: optional
next_retry_at: optional ISO-8601
```

## 7. State machine

```text
queued
  -> claimed
  -> reviewing
  -> synthesizing
  -> implementing
  -> verifying
  -> done

Any active state may become:
  -> blocked
  -> failed
```

Rules:

- claiming must be atomic enough to avoid duplicate workers;
- every transition must be idempotent;
- restart must resume from the last durable checkpoint;
- a finished adapter call must not be re-posted blindly after reboot;
- branch/PR creation must be deduplicated by task identity;
- bounded retries only.

## 8. Evidence Freshness Rule

Every material claim about current state should carry, when available:

- `evidence_timestamp`;
- `evidence_source`;
- exact SHA / run ID / deployment ID / production query target;
- `freshness`: live | current_remote | snapshot | historical.

Example:

```yaml
evidence_timestamp: 2026-10-02T21:00:00+08:00
evidence_source: github_origin_main
sha: abcdef1234
freshness: current_remote
```

Do not let a model present a stale handoff count as live production truth.

## 9. Provider adapter contract

Council core must not depend on one vendor's CLI shape.

Conceptual adapter interface:

```text
capabilities() -> provider capability record
review(task, evidence_bundle) -> structured proposal
implement(task, synthesis, workspace) -> structured implementation result
verify(task, diff, test_evidence) -> structured verification
```

Provider-specific login, CLI invocation, timeout handling, and output parsing stay inside the adapter.

If a provider changes or disappears, replace the adapter without redesigning Council state.

## 10. Capability registry

Each adapter should advertise capabilities rather than being assumed usable.

Example:

```yaml
provider: gemini-antigravity
enabled: true
authenticated: true
supports_repo_read: true
supports_shell: true
supports_write: true
supports_structured_output: partial
cost_mode: existing_account
last_verified_at: ISO-8601
```

Unverified adapters remain disabled by default.

## 11. Windows background relay requirements

### Startup

- auto-start after Windows login using a lightweight supported mechanism such as Task Scheduler;
- no terminal window required for normal use;
- no GUI required for normal use;
- failures must still be inspectable through local log + GitHub task state.

### Polling

The MVP should prefer lightweight polling of the GitHub task queue over hosting a public webhook receiver on the home laptop.

A small polling interval is acceptable because no AI process should be launched while no task exists.

### Resource limits

- one provider process at a time;
- explicit process timeout;
- no unbounded child processes;
- low idle CPU / memory;
- configurable quiet hours if later needed.

### Repo safety

Before each task:

1. verify expected repo path;
2. fetch origin;
3. record local HEAD and `origin/main`;
4. refuse stale implementation work until base state is reconciled;
5. ensure clean worktree before switching tasks;
6. never write main directly.

## 12. Cross-device intake

The durable intake target is GitHub.

An AI can submit directly only if that AI has a supported GitHub connector / tool / authenticated local adapter. Do not pretend every mobile AI application can already write to the private repo.

The target user experience is nevertheless uniform:

> "把這個任務交給 SWSI Council。"

If the current AI can create the GitHub task, it does so. If it cannot, that provider is not yet a full intake endpoint and should remain marked as such in the capability registry.

The long-term system should avoid asking the owner to copy full reviewer outputs between systems.

## 13. Security boundaries

Never persist in GitHub tasks, issues, logs, or prompts:

- OAuth authorization codes;
- API keys;
- PATs;
- Supabase service-role secrets;
- backup encryption keys;
- raw private backup contents.

Use official login flows and OS/provider credential storage where possible.

Reviewer permissions should be read-only where the provider supports permission separation.

## 14. Cost boundaries

- GitHub Actions 2,000 min/month remains a hard budget.
- Do not run the relay itself as an always-on GitHub Actions workflow.
- Use local deterministic checks before CI.
- Council size should scale with task risk, not enthusiasm.
- Never switch to a paid API automatically when free/existing quota is unavailable.

## 15. Implementation roadmap

### Phase 0 — Contract

- target architecture document;
- collaboration protocol updated;
- local workstation document updated;
- task schema / state machine / evidence freshness contract.

### Phase 1 — Read-only Relay MVP

Single provider first: Gemini / Antigravity.

Acceptance flow:

```text
GitHub queued review task
-> Windows relay notices it
-> repo freshness check
-> Antigravity reviewer runs read-only
-> structured result written back to GitHub
-> task marked done
```

Owner must not need to open PowerShell or copy/paste the model's response.

### Phase 2 — Coordinator + Implementer

- structured proposals;
- synthesis;
- single-writer lock;
- branch creation;
- local/static validation;
- PR-last;
- owner safety gates.

### Phase 3 — Verification Council

- exact diff review;
- real test evidence;
- bounded repair loop;
- durable final verdict.

### Phase 4 — Additional providers

Add only after the core flow is stable. Each provider must pass a capability/auth/read-only test first.

### Phase 5 — Mature intake / portability

- multiple safe intake providers;
- provider replacement tests;
- adapter health checks;
- exportable task history;
- low-human maintenance documentation.

## 16. MVP acceptance criteria

The first meaningful milestone is complete only when all are true:

1. owner can cause a Council review task to exist from a mobile conversation / GitHub-capable AI;
2. the Windows laptop may be offline at submission time;
3. task remains queued durably;
4. on next Windows login, relay auto-starts without manual terminal work;
5. relay synchronizes the private repo;
6. Antigravity performs the read-only review;
7. result returns to GitHub automatically;
8. reboot does not duplicate the result;
9. no unnecessary GitHub Actions run;
10. no new paid service is required.

## 17. Non-goals

- calling four models for every task;
- local large-model hosting;
- replacing deterministic tests with model agreement;
- replacing official evidence with Council consensus;
- making this infrastructure a blocker for SWSI student release;
- keeping every provider always online.

## 18. Tracking

Primary tracking Issue: **#290**.

Long-term SWSI autonomy remains tracked by **#262**. Council Relay is one maintenance capability under that broader goal, not the entire SWSI roadmap.
