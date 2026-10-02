# SWSI student home IA inventory — 2026-10-03

Issue: #307  
Branch baseline: `main@356a9eb0fb1b0f678a7045a6f82447450bc05678`

## Scope

This audit covers only the student home first screen and the minimum navigation needed to start a study action. It does **not** redesign grading, the question bank, review state, essay state, AI, Supabase, or production release behavior.

The product goal from #307 is subtraction first: a student should understand the next useful action quickly without seeing the platform's internal feature depth as a feature wall.

## Current home ownership before this patch

The canonical focused-home override in `monthly_patch_parts/20.product-philosophy.part` already removed most duplicated feature cards. Before this patch the home owned:

1. dominant action: **20-question smart practice**;
2. secondary range configuration;
3. compact shortcut: wrong-answer review;
4. compact shortcut: timed mock exam;
5. one low-emphasis link listing theory / law / current affairs.

Learning Center and Essay remain bottom-navigation destinations and are intentionally not repeated as large home cards. `scripts/launch_readiness_smoke.js` already fail-closes if those duplicate large destinations return.

## Decision for this patch

Keep the existing architecture and reduce decision weight further instead of creating a new home system.

### First-screen hierarchy after patch

1. **今天練 10 題** — dominant CTA, intended as the short/default practice action.
2. **複習錯題** — compact shortcut; due count stays visible when applicable.
3. **完整模擬考** — compact shortcut for the long-form exam mode.
4. **更多學習工具** — low-emphasis route to deeper material; the home no longer lists theory/law/current-affairs terminology at the same visual level as the main actions.
5. **自己選範圍** remains secondary inside the dominant practice card so existing year/round/subject/count control is preserved without becoming another top-level destination.

This is intentionally a small IA change. No new database, recommendation engine, session store, or parallel navigation model is introduced.

## Why "繼續上次" is not implemented in this patch

#307 names "繼續上次" as a candidate core action, but the inspected frontend does not currently expose a durable unfinished-practice-session contract that is safe to reuse.

Observed boundaries:

- active practice uses runtime `queue` / `idx` / selection state;
- durable browser storage is already used for learning history, review state, essay drafts, exam date and other bounded preferences;
- no existing, versioned persistence contract for restoring an unfinished ordinary practice queue was found in the inspected frontend path.

Therefore this patch does **not** fake a "continue" button, infer a session from history, or add another storage owner. A future implementation should first define a versioned resume payload, question-ID validation against current shards, grading-contract compatibility, stale-session handling, and storage failure behavior. Until then, review is a real existing continuation path and is safer to surface.

## Acceptance locked by Launch Readiness QA

`scripts/launch_readiness_smoke.js` now requires:

- exactly one dominant home practice card;
- copy identifies **今天練 10 題** and **開始 10 題**;
- clicking the CTA produces a real `1 / 10` practice queue;
- exactly two compact quick actions remain;
- quick actions are **複習錯題** and **完整模擬考**;
- exactly one low-emphasis **更多學習工具** link remains;
- Learning Center / Essay are not duplicated as large home destinations.

## Non-goals / invariants

- Official Core unchanged.
- Grading contract unchanged.
- Question-shard loading and SHA validation unchanged.
- Review scheduling semantics unchanged.
- Mock exam behavior unchanged.
- Bottom navigation unchanged.
- No production deploy in this branch work.

## Follow-up for #307

After this first-screen subtraction is verified, the next product work should be evaluated in this order:

1. real device / viewport validation of the new hierarchy;
2. progressive disclosure inside the answer explanation screen;
3. trust-state wording for platform-added content;
4. only then consider a versioned unfinished-session resume contract if user value justifies the added state complexity.

Do not create "繼續上次" as a cosmetic button before the underlying session contract exists.
