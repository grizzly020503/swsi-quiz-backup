# Current-affairs student focus — 2026-10-03

Scope: Issue #307 P1-6 student-side simplification only.

## Before

The student current-affairs surface could render up to 6 cards and presented itself as a `命題趨勢雷達`. The underlying evidence model was already conservative, but the surface still resembled a dashboard/feed more than a focused study aid.

## Change

- Keep the existing source registry, event clustering, law links, historical-question evidence, trend score and one-off fail-closed rules unchanged.
- Rank the already-built candidate list by V2 `trend_score` (or V1 `relevance_score` fallback), with recency as a deterministic tie-breaker.
- Display at most 3 cards per current filter.
- Rename the student heading to `目前 3 個國考重點` and describe the list as a small evidence-graded review set, not a prediction dashboard.
- Preserve V1 fallback, subject filtering, source links, evidence details, related historical questions and one-off safeguards.

## Trust boundary

This change does not claim that any event will appear on the exam. A single-source / single-observation event remains `單次觀察` and must not expose a trend score as if a trend had formed.

No Official Core, grading, question content, current-affairs source list, event/trend generation, DB/Auth/RLS, AI call or production deploy is changed.

## Acceptance

Existing current-affairs UI smoke must continue to prove:

- one current-affairs UI owner;
- V2 event/trend rendering and V1 fallback;
- one-off fail-closed semantics;
- escaping of dynamic content;
- subject filter reuse without refetch;
- student list cap of 3;
- focused heading replaces the dashboard-style heading.
