# SWSI AI 解析 Recovery Handoff — 2026-10-02

> 這份文件是 2026-10-02 production recovery 的即時交接。接手前仍必須重新讀 main、Supabase production、open PR/Issue 與最新 Actions，不要假設本文中的計數永遠最新。

## READ FIRST

1. **不要再處理 Cloudflare/Qwen 3.8 migration 本身。** 這輪已完成 production 上線與 live parity。
2. **不要把所有 review 一次重設 pending。** 現在有另一條受權 recovery 流程同時處理 backlog；先讀 live DB 與 `net._http_response`，避免重複 requeue / claim。
3. 目前只允許自動 recovery 的範圍：`analysis_status='review'`、`grading_mode='standard'`、單一答案、舊 `HTTP 405` 基礎設施錯誤。
4. **multi-answer、special grading、真正內容/格式失敗不要混入 infra recovery。**
5. Analyzer DB claim 保護仍存在：每次最多 1 題，且 24h 完成數上限 25；不要繞過。

## Cloudflare / AI production 已完成

- PR #247 已合併：Cloudflare production sync + legacy AI compatibility。
- PR #248 已合併：Cloudflare production verification closure + canonical monthly runtime rebuild。
- main 已知基線：`10ca3815cf3f9032c7b0dcd84be074301eff358f`（接手時重新確認）。
- live question dataset revision：`5c4acad4299dbae1caee`。
- live 題庫：4,800 MCQ / 24 shards。
- `115-2` live shard：200 題，`accepted_answers` contract 正常。
- production Worker current model：`qwen/qwen3.8-27b`。
- cached legacy client `qwen/qwen3.6-27b` 會由 Worker alias 到 3.8；不得重新把 3.6 當 upstream model。
- live Production Artifact QA 已成功，Public Uptime Sentinel #89 已由 production QA 自動觸發並 success。
- `cdn/monthly_patch.js` 已由 38 個 `monthly_patch_parts/*.part` canonical source 重建，artifact smoke 已 PASS。

## Supabase analyzer production

- project：`Swsi` / ref `yumjtrdctaxyczpspuyo`。
- `analyze-pending-questions` production 已知為 v11 ACTIVE；接手時重新讀 live function。
- v11 draft model：Qwen 3.8；audit model：`openai/gpt-oss-120b`。
- Edge Function custom auth：`x-job-key` 對 `ai_analysis_job_config.job_key`；**不要讀出或記錄明文 key**。
- pg_cron job id 3：`*/30 * * * *`，每次 body `{"limit":1}`。
- `claim_pending_ai_questions()` 仍硬性每次最多 1 題，24h `analysis_completed_at` >= 25 時停止 claim。

## 已驗證的 recovery 行為

以下舊題已從失敗狀態實際 recovery 成 `ready`，證明 production 完整鏈可工作：

- `HBSE-115-2-027`
- `DS-115-2-008`
- `DS-115-2-039`（第一次 JSON array 格式錯，第二次成功）
- `SW-115-2-040`（第一次 `exp_others 空白`，第二次成功）
- `R-115-2-004`
- `R-115-2-010`（第一次 `exp_others 空白`，第二次成功）
- `R-115-2-023`（第一次 JSON array 格式錯，第二次成功）

結論：舊 405 基礎設施問題已解除；Qwen 3.8 偶爾仍有輸出格式波動，但目前正常 retry 可吸收，不能因此把整條 pipeline 判成失敗。

## 2026-10-02 約 12:10 Asia/Taipei 的 live recovery 狀態

最後一次人工盤點時：

- `ready`：4,683
- `review`：104
- `pending`：13
- 24h 完成數在稍早盤點為 14/25；**此數會持續變動，接手要重查**。

13 個 pending 中，人工剛 requeue 的 standard 405 共 11 題：

- `DS-104-2-04`
- `SP107-1-04`
- `SW-109-1-05`
- `SP107-2-05`
- `SW-105-2-06`
- `SP105-1-08`
- `SP107-2-08`
- `DS-104-2-09`
- `HBSE-107-2-010`
- `DS-104-2-10`
- `SP113-1-11`

另有另一條受權流程同時加入/處理：

- `SP112-2-03`：pending / attempts 0（最後看到時）
- `SW-105-2-03`：pending / attempts 1 / `exp_others 空白`（最後看到時）

`net._http_response` 657–661 顯示另一條受權流程在 12:08–12:10（Asia/Taipei）持續成功處理題目；因此接手者**不要再大量 requeue 或手動搶 claim**。

## review queue 分類原則

在 recovery 前的交叉盤點曾看到：

- standard + HTTP 405：主要可 recovery 群。
- multi-answer：獨立處理，不要和 standard 405 混跑。
- special grading：封住，需專門規則/人工確認。
- standard 的真正內容/格式失敗至少包含：`AI 回傳找不到 JSON array`、`exp_others 空白`；若已達 attempts 3 / review，要當模型輸出品質問題分析，不要標成 infra 405。

## 接手建議順序

1. 重新查 `analysis_status` counts、24h completed count、pending 清單、review error × grading_mode 分布。
2. 查最近 `net._http_response`，確認是否仍有其他受權 recovery 正在跑。
3. 若已有 active recovery，**不要再 requeue**；只做觀察與真異常分析。
4. 若 recovery 停止且 24h 上限有空間，只從 standard/single-answer/old-405 中小批次 requeue。
5. 格式錯誤先允許既有 retry；重複 3 次後才分析 prompt/validator，不要直接放寬 structural QA。
6. multi-answer / special grading 另開工作流，不要為了衝 ready 數而降低 precision。

## 禁止事項

- 不可為清 backlog 修改官方題目、選項、答案或特殊給分。
- 不可把 `ready` 宣稱為逐題人工 verified。
- 不可暴露 `job_key`、service role 或任何 production credential。
- 不可為了速度移除 25/day 安全閥、單題 claim、fail-closed validator。
- 不可因 Qwen 偶發格式錯誤就放寬欄位完整性、ASCII/數字 guard 或答案一致性規則。
