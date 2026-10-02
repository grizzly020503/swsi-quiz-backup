# 2026-10-03 Student Learning Scenarios — Issue #307 P1-2

## Goal

Turn common student intentions into plain-language entries while reusing SWSI's existing runtime owners. This is an IA/copy mapping layer, not a parallel recommendation or learning system.

## Mappings

| Student intent | Existing owner | What happens next |
| --- | --- | --- |
| 我只有 10 分鐘 | `swsiStartNow()` | Starts the canonical 10-question smart practice. |
| 我要補最弱科 | `go('progress')` | Existing progress page computes subject accuracy, identifies the weakest subject, and offers a 20-question subject practice action. |
| 我要做完整考卷 | `MK.open()` | Opens the existing timed mock-exam flow. |
| 我要練申論 | `swsiOpenEssay()` / `go('essay')` | Opens the existing essay practice flow and local drafts. |
| 我要複習錯題 | `go('review')` | Opens the existing spaced-review / wrong-answer flow. |

## Product boundaries

- No new student database, recommender, quiz engine, essay engine, or mock-exam engine.
- No Official Core, grading, answer, Auth, DB, or production deployment changes.
- The homepage remains intentionally sparse; these five choices live inside the existing Learning Center rather than becoming five new homepage buttons.
- `繼續上次` remains prohibited until a durable unfinished-quiz session contract exists.
- Weak-subject guidance reuses `70.learning-loop.part`; the scenario entry does not duplicate weakness calculations.

## Return paths

- Quiz/review/progress/essay continue using the existing bottom navigation and existing end/return controls.
- Mock exam uses the existing mock modal/flow and its existing close/submit path.
- No scenario introduces a new navigation stack.

## Acceptance evidence

`python scripts/student_learning_scenarios_contract.py` must fail closed if:

- any of the five scenario entries disappears or is renamed without updating the contract;
- an entry is remapped away from its existing runtime owner;
- the 10-minute entry stops using the canonical 10-question action;
- the weak-subject entry stops routing through the existing progress/weakness computation;
- a fake `繼續上次` promise appears before durable session support exists.
