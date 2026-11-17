# Learning-flow correction review

Status: candidate for Owner review; no merge or deployment. Base: aa9bdc76.

## Reproduced problems and changes

- Essay: opening the reference outline rebuilt the app and discarded visible AI feedback. `showGuide` and the five-step disclosure now retain the existing AI section DOM, including buttons and the target of an in-flight request. No extra AI request is made. This covers same-question study-aid expansion, not feedback persistence across navigation or reload.
- Progress: history did not store whether an answer was selected. New entries store a boolean `answered`; progress accuracy, coverage, recent performance and weak-subject/topic suggestions use only explicit answered entries. Unanswered and legacy counts are separately disclosed. Old history is retained, not guessed or rewritten. Existing exam grading and review scheduling are unchanged; pending review can still include blanks.
- Law practice: matching the profession name or multiple generic keywords admitted research-method questions. Practice now requires the complete law title in the question or options, not generated tags or shortened profession names. Across the committed 4,800-question fixture, Social Worker Act candidates number 44 and the observed salary-survey question is excluded. This is conservative title matching, not verified legal-source attribution; questions using only abbreviations can be omitted.

## Validation

Passed locally:

- `node scripts/learning_flow_regression.js`: both root and Cloudflare implementations; live result-node identity across guide/dissection expansion; pending-result target retained; answered metadata; 1 answered + 19 blanks + legacy records; no-answer empty state; positive and negative law cases and full-bank candidate check.
- `node scripts/learning_loop_action_smoke.js`: 7 topics / 14 handlers and 5 escaped question-ID cases.
- `python scripts/monthly_frontend_smoke.py --site _site`: production-shaped static build.
- `python scripts/cloudflare_release_artifact_smoke.py`: canonical parts/artifact parity and content-hash URL.
- `python scripts/maintainability_smoke.py`: no new override layer.
- Inline JavaScript syntax for both HTML files, patch syntax, `git diff --check`.

Not passed / still required:

- Browser grading smoke could not launch. Packaged Playwright browser was absent; system Chromium exited with `socket() failed: Operation not permitted`. A browser download attempt failed with a truncated archive. No weakening of tests or production settings was made.
- Actual revised-page acceptance at 390 / 768 / 1024 / 1440, pending/completed AI UI, keyboard navigation, and existing browser regression suites remain required before release. Deterministic DOM fixtures are not browser acceptance.
- No real AI provider call, login, offline or handwriting acceptance was performed on this branch.

## Delivery boundaries

No official questions/answers/grading tuples, production DB, credentials or deployed sites changed. Root and tracked Cloudflare source are kept aligned. The existing no-store/network-first mutable asset policy remains; the Cloudflare patch URL content hash changes, so a service-worker cache schema bump is unnecessary. The existing Monthly Frontend QA includes the new offline regression; no additional workflow was created. Older draft design PR #604 remains separate.
