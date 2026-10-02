# 2026-10-03 Progressive Explanation — Issue #307 P1-3

## Goal

Reduce post-answer reading load on mobile without deleting SWSI depth or creating a second explanation system.

## Existing foundation retained

- `zzzz_product_v1_lock.part` already inserts the official/canonical answer line and collapses distractor analysis, exam traps and `.extra` material behind `看完整解析`.
- `70.learning-loop.part` already asks a wrong-answer student `這題你為什麼會錯？` and stores the selected cause locally.
- Official question text, official answers, grading rules and explanation source data are untouched.

## This patch

Layer 1 stays visible:

1. question topic / exam point;
2. answer line;
3. one deterministic concise reason derived from the existing explanation text;
4. platform-provided `mistake` warning when present;
5. the student's own wrong-cause reflection when the answer is wrong.

Layer 2 (`看完整解析`) contains the full explanation sections, including:

- full `為什麼對` or raw explanation;
- why other options are wrong;
- exam traps;
- mnemonic;
- law/source detail already rendered as `.extra`.

The concise reason is not AI-regenerated and does not invent facts: it is the first sentence (or a bounded prefix when no sentence boundary exists) of the already-rendered explanation.

## Deliberate boundary

This patch does **not** add current-affairs links or fuzzy theory/law/history matching from the active quiz. Those links need an evidence-safe relation and a safe return-to-quiz path. Current-affairs contextual surfacing belongs to #307 P1-6; historical-law semantics remain shared with #261 P1-B / P1-5.

No new DB, recommendation engine, explanation store, grading path, Auth behavior or production deploy is introduced.
