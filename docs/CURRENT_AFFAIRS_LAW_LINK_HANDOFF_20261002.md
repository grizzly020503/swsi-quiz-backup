# Current-affairs law-link handoff — 2026-10-02

Issue context: #261 / PROJECT_HANDOFF P1 `時事 ↔ 法規 ↔ 歷屆題`.

## Goal

Close one concrete semantic gap without inflating coverage: obvious institutional events such as minimum-wage review and employer childcare subsidies should not publish `related_laws=[]` merely because a press-release title/summary omits the statute name.

## Safety boundary

- Deterministic rules are high-precision and evidence-bearing.
- A related statute means the event materially belongs to that statutory framework; it does **not** mean the statute was amended.
- Subsidy programmes / policy measures remain separate from statutes.
- Every automatic rule has positive + negative regression examples.
- Unknown cases remain unresolved rather than receiving a guessed law.
- No production DB write, deploy, answer change, question mutation, or secret is part of this work package.

## First accepted rules

1. Minimum-wage review/adjustment -> `最低工資法`.
2. Employer/enterprise childcare facilities, measures or subsidies -> `性別平等工作法` (Article 23).
3. Enterprise childcare subsidy stays separately represented as a subsidy programme.
4. Expanded elderly-living-alone outreach and residential-service-user subsidies are represented as policy instruments only until a sufficiently precise statutory rule is reviewed.

## Pipeline

`current_affairs.json -> base exam-signal analyzer -> deterministic law/policy linkage -> historical relation recompute when a law is newly added -> signals -> events -> trends`

A temporary PR-only artifact workflow rebuilds all three derived snapshots from the exact PR head, runs existing current-affairs smoke tests, and uploads the generated JSON for review. It has `contents: read`, no secrets, no deploy step, no production write, and should be deleted before final merge after the rebuilt snapshots are committed.

## Acceptance

Do not merge until:

- rule self-test passes;
- exact PR-head snapshot build passes;
- minimum-wage item contains `最低工資法` in signals and trends;
- enterprise-childcare item contains `性別平等工作法` in signals and trends;
- existing current-affairs signal/event/public-monitoring smokes pass;
- rebuilt `auto/` and `cdn/auto/` snapshot pairs are identical;
- temporary artifact workflow is removed before final merge.
