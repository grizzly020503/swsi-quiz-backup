# P1-7 Mobile-first acceptance — 2026-10-03

Issue: #307 P1-7

## What this repo-level slice proves

The existing Launch Readiness suite already covers:

- Chromium mobile viewport 390×844 for launch and product flow;
- Chromium 320×568 small-phone and 844×390 landscape touch/layout checks;
- WebKit 390×844 phone and 844×390 landscape checks;
- accessibility/touch-target checks;
- slow-network, storage degradation, PWA/service-worker resilience;
- browser interaction from home → 10-question practice → wrong answer → explanation → next question → leave → review/progress;
- mobile accessibility and WebKit compatibility.

This slice adds an explicit Android-like Chromium context:

- viewport 412×915;
- `isMobile=true`, `hasTouch=true`, deviceScaleFactor 2;
- primary CTA and answer-option touch-target assertions;
- real 10-question start and `1 / 10` assertion;
- deterministic wrong answer;
- progressive explanation expansion;
- self-reported wrong-cause selection;
- next-question transition to `2 / 10`;
- leave practice and return home;
- full page reload to simulate reopening the web app surface;
- confirm the saved wrong-cause / weak-topic learning evidence is still visible after reopening;
- horizontal-overflow checks on home, question, explanation, reopened home and review.

## Important boundary: unfinished-session resume is still not implemented

The frontend still has no versioned durable contract for restoring an unfinished ordinary practice queue (`queue` / `idx`). Therefore this slice intentionally asserts that no cosmetic `繼續上次` copy appears after reload.

This is not a failure of learning-record persistence. Wrong-answer history, self-reported cause and weak-topic evidence are durable and are verified after reload. It only means the specific requirement "leave mid-quiz and resume the exact unfinished queue" remains a separate product/state feature.

A safe future resume contract would need at least:

1. versioned payload schema;
2. stable question IDs rather than copied mutable question content;
3. current shard/manifest existence validation;
4. grading contract compatibility (`grading_mode`, `accepted_answers`);
5. stale/expired-session handling;
6. bounded storage-failure behavior;
7. no conflict with review/spaced-learning state.

Until then the product must not fake a resume button.

## What this still does not prove

Headless browser/device emulation is not the same as a physical-device test. This repo-level evidence does **not** claim that a real iPhone Safari and a real Android Chrome device have both been manually exercised against the current production URL.

P1-7 therefore has two distinct layers:

- **repo/browser acceptance:** strengthened by this slice;
- **real production physical-device acceptance:** still requires recorded device/browser/release evidence under #261 P1-D.

## Safety

- Official Core unchanged.
- Grading unchanged.
- No DB/Auth/RLS/storage schema change.
- No new runtime owner or student feature.
- No production deploy.
- Existing Launch Readiness workflow is reused; no new workflow is created.
