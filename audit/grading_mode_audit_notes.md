# MOEX 特殊給分模式稽核筆記

建立：2026-08-25

## 為什麼需要 `grading_mode`

考選部更正答案存在兩種不同語意，不能只用 `answer = 一律給分` 表示：

- `all_credit`：官方「一律給分」，包含未作答也得分。
- `any_answer`：官方「除未作答者不給分外，其餘均給分」，A–D 任一作答得分，但空白不得分。
- `standard`：依 `answer` / `accepted_answers` 判分。

舊 parser 與 historical audit 只比較 A–D 可接受答案集合，因此曾把前兩者都壓成同一種 `{A,B,C,D}`；這不影響已作答選項，但會讓模擬考的空白題計分失真。

## Production 分類

目前 4,800 題：

- `standard`：4,784 題
- `all_credit`：12 題
- `any_answer`：4 題

`any_answer` 四題：

- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

其餘 12 題原 `answer = 一律給分` 為真正 `all_credit`。

## 已完成 production 變更

- migration：`20260825110853_preserve_official_grading_mode`
- `questions.grading_mode` 三態 constraint / consistency constraint
- `trg_reset_ai_on_official_change` 已納入 `grading_mode`
- `import-moex-social-worker` production v4 會 fail-closed 驗證 grading mode
- Cloudflare shard builder 已保留／驗證 `grading_mode`
- production CDN revision：`e721d6293d4c6acdddee`
- builder 驗收：4,800 題、25 multi-answer、12 all_credit、4 any_answer
- 2026-09-15 read-only historical reaudit：4,800/4,800 官方最終答案 finding=0、grading-mode mismatch=0；115-2 `DS-115-2-040` 由考選部更正答案新增 `accepted_answers = [B, D]`，因此 immutable multi-answer baseline 經重新稽核後由 24 更新為 25

## 上游／audit

- `scripts/moex_sync_v2.py`：只覆寫更正規則與 grading metadata，底層既有 PDF parser 不重寫
- `scripts/test_moex_grading_modes.py`：最小語意測試
- `scripts/historical_answer_audit_v4.py`：除了 4,800 題 accepted-answer audit，再逐題比較 grading mode

## 月底前端規則

前端 `normalize()` 必須同時保留：

- `accepted_answers`
- `grading_mode`

判題語意：

- `all_credit`：即使 `picked == null` 仍 correct
- `any_answer`：只有 A/B/C/D 任一作答 correct；`picked == null` incorrect
- `standard`：依 accepted answer set

因此「模擬考未作答一律算錯」不能套用到 `all_credit`。
