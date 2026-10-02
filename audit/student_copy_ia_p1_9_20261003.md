# P1-9 student copy / information architecture closeout — 2026-10-03

Scope: Issue #307 P1-9. This is a student-facing language and IA audit, not a redesign and not a backend rename.

## Principle

Students should not need to understand repository, pipeline, runtime, manifest, schema, Official Core, QA stage, model/provider, or other engineering vocabulary to decide what to do next.

The underlying engineering terms remain valid inside code, contracts, audits and maintainer documentation. This closeout only governs student-visible copy.

## Main student surfaces

### Home
- Primary action: 10-question practice.
- Secondary actions: wrong-question review and full mock exam.
- Law / theory / current-affairs depth stays in the secondary tool layer.
- No fake “continue unfinished quiz” entry exists because unfinished quiz session durability is not yet implemented.

### Learning center / progress
- Uses student intents rather than internal module names: short practice, weakest subject, full exam, essay practice, wrong-question review.
- Weak-topic next steps are explained from local wrong-answer history and are not presented as black-box AI recommendations.

### Quiz answer / explanation
- Layer 1 stays concise: official answer, one core reason, personal error reflection.
- Layer 2 contains full explanation and supporting material.
- Trust wording distinguishes official exam data from SWSI-added explanation without exposing `Official Core` or `QA` as student-facing labels.

### Law / theory
- Existing checked / pending trust states remain.
- “Checked” is not redefined as official exam commentary.
- Historical-law evidence remains separately scoped to verified exam-time metadata.

### Current affairs
- Student view is capped to three focused exam-relevant items per filter.
- It is not presented as a news portal and does not promise exam prediction.
- Single-source / one-off events remain clearly separated from evidence-backed trend signals.

## Naming cleanup in this slice

Student-facing trust copy should prefer plain language:
- `平台解析・已通過基本檢查` instead of `平台解析・QA 已通過`.
- `已通過目前的自動與結構檢查` instead of exposing the abbreviation `QA`.
- `題目、選項、官方答案與特殊給分以考選部資料為準` instead of the engineering label `Official Core`.

Internal code and maintainer documentation may continue using `analysis_status`, `Official Core`, QA, runtime, manifest and similar implementation terms.

## Remaining non-repo evidence

P1-7 still requires real-device evidence. Automated Chromium/WebKit viewport smoke is useful but must not be described as a human iPhone + Android usability test.

This audit therefore does not claim the whole #307 issue is closed.
