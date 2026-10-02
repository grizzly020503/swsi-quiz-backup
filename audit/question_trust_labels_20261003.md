# 2026-10-03 Question Trust Labels — Issue #307 P1-4

## Goal

Make the student-facing quiz explanation clearly distinguish official exam content from SWSI-added learning content without adding another trust database or overstating QA status.

## Reused contracts

- Official question identity already exists through `source_exam_code` + HTTPS `source_url` and the existing official/non-official boundary used by feedback context.
- `analysis_status` already distinguishes `ready`, `pending` / `analyzing`, and `review`.
- `legal_status` already uses `not_applicable`, `unreviewed`, `verified_current`, and `changed`.
- Law cards already distinguish `官方來源已逐卡核對` vs `已連結官方來源・摘要待逐卡複核`.
- Theory cards already distinguish `理論內容已逐卡核對` vs `平台整理・待逐卡複核`.

No new verification state is invented by this patch.

## Student wording

The compact quiz explanation now exposes one expandable `資料可信度` row.

For a normal official historical question it separates:

- `官方題目／答案`
- `平台解析・QA 已通過` when `analysis_status=ready`

The detail explicitly states that `ready` means the platform explanation passed the current automated / structural QA, **not** per-question human verification and **not** an official MOEX explanation.

For legal content, existing `legal_status` becomes:

- `verified_current` → `法規・現行來源已核對`
- `changed` → `法規・已偵測變動`
- `unreviewed` → `法規・待逐題複核`
- `not_applicable` → no legal badge

`verified_current` deliberately includes a historical-law caveat: current-source verification does not prove what law text was effective on the historical exam date. P1-5 remains the owner of historical-law comparison.

## Safety / scope

- Official Core is not changed.
- `analysis_status` / `legal_status` values are not changed.
- No DB, Auth, storage, AI call, or production deploy is added.
- Source links are rendered only when HTTPS and use `noopener noreferrer`.
- Existing law/theory trust UIs remain authoritative for their own cards.
- The trust row stays compact so P1-3 progressive disclosure is not undone.

## Remaining P1-4 work

This closes the student-facing trust-label slice, not the entire P1-4 work package. Still verify before marking P1-4 complete:

1. high-risk question sample across law/date/number/negative/multi-answer cases;
2. whether student feedback is durably reflected in QA/review priority rather than only accepted as a report;
3. any additional source-checked / historical-law status that should be surfaced only after its existing contract proves the claim.
