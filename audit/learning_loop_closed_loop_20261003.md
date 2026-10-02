# P1-8 learning loop closed loop — 2026-10-03

Scope: Issue #307 P1-8. This change turns an existing wrong-topic statistic into one explainable next-step loop without adding a recommendation backend or AI decision layer.

## Existing foundation reused

- Wrong answers already enter the spaced-review system.
- Students can already mark why they were wrong; that state remains local to the device.
- Progress already counts wrong topics and weak subjects.
- `80.knowledge-path.part` already owns `swsiKnowledgeSearch(topic)` and the law/theory/history search experience.
- `swsiPracticeTopic(topic, n)` already owns same-topic practice.

## Closed loop

When there is no due spaced review and the same topic has accumulated at least 2 wrong answers:

1. Progress explains the evidence: `這個考點已累計錯 N 次`.
2. Student may choose `先看相關教材`, which reuses the existing Knowledge Path search.
3. Student may choose `練 5 題確認`, which reuses same-topic quiz practice with a bounded five-question set.

The recommendation is optional. It is explicitly described as coming from the student's wrong-answer history, not a black-box AI recommendation.

## Priority and session safety

- Due spaced review remains the first recommendation when review items are due.
- The new material link appears on the progress surface, not inside an active in-memory quiz. It therefore does not create a fake resume contract or silently abandon an unfinished quiz session.
- If no repeated topic exists, the existing weak-subject and generic-practice fallbacks remain.

## Safety boundary

No Official Core, answer/grading logic, question metadata, DB/Auth/RLS, AI/model call, production deploy, or new recommendation datastore is introduced.

The learning loop remains a local, deterministic UI rule based on existing learning history.
