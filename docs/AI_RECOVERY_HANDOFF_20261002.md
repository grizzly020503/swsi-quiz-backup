# SWSI AI 解析 Recovery Handoff — 2026-10-02

> 這份文件是 2026-10-02 production recovery 的即時交接。接手前仍必須重新讀 main、Supabase production、open PR/Issue 與最新 Actions，不要假設本文中的 SHA、計數或狀態永遠最新。

## READ FIRST

1. **Cloudflare / Qwen 3.8 migration 已完成，不要重做。** Production Worker current model 為 `qwen/qwen3.8-27b`；legacy `qwen/qwen3.6-27b` 由 Worker alias 到 3.8。
2. **AI queue fairness 已正式上 production。** PR #256 已 merge，migration `ai_queue_fair_retry_rotation` 已套用；Issue #254 暫時保持 open，只因驗收規則要求觀察至少兩個自然 cron cycle。
3. **Analyzer v12 已正式上 production。** `analyze-pending-questions` 現為 v12 ACTIVE，`verify_jwt=false` 沿用既有 custom `x-job-key` auth；live source parity 已確認。3 題指定 behavioral probes 尚未重跑。
4. **不要把所有 review 一次重設 pending。** Recovery 仍受每次 1 題、每 30 分鐘、rolling 24h 最多完成 25 題保護。
5. **multi-answer、special grading、真正內容／格式失敗不要混入舊 405 infra recovery。**

## GitHub / main

- 最新已知 main（v12 deploy 前）：`82ecf2d67f812eab5475f51a0ad27b214a28c3c1`，接手仍要重查。
- PR #250：Analyzer v12 reliability hardening，已 merge。
- PR #252：pg_net transport timeout 延長到 120,000 ms，已 merge且 production cron parity 已驗證。
- PR #256：AI queue retry fairness，已 merge；Disaster Recovery Restore Drill #60 全綠後才合併。
- PR #257：fairness live handoff，已 merge。
- Issue #254：fairness production observation，保持 open，待至少第二個自然 cron cycle 驗證後才可關閉。

## Cloudflare / 題庫 runtime

- live question dataset revision：`5c4acad4299dbae1caee`。
- live 題庫：4,800 MCQ / 24 shards。
- `115-2` live shard：200 題，`accepted_answers` contract 正常。
- live Production Artifact QA 已成功，Public Uptime Sentinel 曾由 production QA 自動觸發並 success。
- `cdn/monthly_patch.js` 已由 canonical `monthly_patch_parts` 重建並通過 artifact smoke。

## Supabase analyzer production — v12 LIVE

- project：`Swsi` / ref `yumjtrdctaxyczpspuyo`。
- `analyze-pending-questions` production：**v12 / ACTIVE / verify_jwt=false**。
- function id：`4e7f9587-e2a3-4816-9a66-0e5dbd29723c`。
- deployed bundle SHA-256：`06b242a734749ade75a3c2fd32c4a71ae99d089053bf85f1fa11978c7c3e44de`。
- Exact GitHub `main` source blob used for deployment：`bc9bd36109d467e0f6fe01d2a5509321b39615df`。
- v12 draft model：Qwen 3.8；audit model：`openai/gpt-oss-120b`。
- `verify_jwt=false` 是沿用 v11，不是新的 auth relaxation；function body 仍以 `x-job-key` 對 `ai_analysis_job_config.job_key` 做 custom auth。
- 官方 Supabase Edge Function connector 已成功部署 exact main source；沒有讀取、暴露、猜測或 commit credential。
- 部署後重新 `get_edge_function` 驗證 live source，確認已包含：
  - malformed / missing JSON-array 的單次 format retry（`formatRetries`）；
  - strict validator 首次 rejection 後的 repair audit（`auditRepairPrompt` + 最多兩次 audit validation）。
- strict validator、model choice、Official Core、quota 均未放寬或修改。

### v12 behavioral probes 尚待執行

指定 3 題：

- `SP-115-2-006`：先前 `AI 回傳找不到 JSON array`
- `SP-115-2-009`：先前 `exp_others 空白`
- `SP-115-2-037`：先前 `AI 回傳找不到 JSON array`

目前只完成 **version/source parity**，尚未宣稱這 3 題已通過 v12 behavioral validation。

先完成 Issue #254 第二個自然 post-fairness cron observation；之後再只 requeue 這 3 題做 dedicated bounded validation，不和 60 題 old-405、25 題 multi-answer、16 題 special grading 混跑。

## Scheduler / safety controls

- pg_cron job id 3：`*/30 * * * *`，每次 body `{"limit":1}`。
- live `cron.job.command` 使用 `timeout_milliseconds := 120000`。
- `claim_pending_ai_questions(integer)` 每次最多 1 題。
- rolling 24h `analysis_completed_at >= now()-24h` 達 25 題停止 claim。
- queue claim RPC ACL：`anon=false`、`authenticated=false`、`service_role=true`。

## Queue fairness 已上 production

PR #256 / migration `20261002045108_ai_queue_fair_retry_rotation.sql`：

- 新增 `questions.analysis_last_attempt_at timestamptz`。
- claim 排序：never-attempted first → oldest attempted → 原本 deterministic fields 作 tie-breaker。
- 每次 claim 寫入 `analysis_last_attempt_at = now()`。
- Official Core fresh reset 會清掉 `analysis_last_attempt_at`。
- stale `analyzing > 15 minutes` recovery 保留。
- live function 已重新讀取確認仍保留 `max 1` 與 `25/24h` 安全閥。

### 第一個自然 post-migration cron cycle 已驗證

2026-10-02 13:00 Asia/Taipei：

- cron runid 623 / jobid 3，scheduler submission `succeeded`。
- `SP112-2-03` 在 `2026-10-02 05:00:02.024626+00` 被正式 cron claim。
- 該題寫入 `analysis_last_attempt_at`，並成功完成為 `ready`，無 analysis error。
- 沒有人工 claim / requeue。
- #254 尚需第二個自然 cycle；不要為了驗收人工製造 queue 行為。

## 最新已知 queue snapshot

第一個自然 fairness cycle 後：

- pending：11
- analyzing：0
- ready：4,684
- review：105
- completed previous rolling 24h：15 / 25

接手務必重查。

## 既有 recovery 已驗證行為

曾從失敗狀態實際 recovery 成 `ready`：

- `HBSE-115-2-027`
- `DS-115-2-008`
- `DS-115-2-039`（第一次 JSON array 格式錯，第二次成功）
- `SW-115-2-040`（第一次 `exp_others 空白`，第二次成功）
- `R-115-2-004`
- `R-115-2-010`（第一次 `exp_others 空白`，第二次成功）
- `R-115-2-023`（第一次 JSON array 格式錯，第二次成功）

舊 HTTP 405 基礎設施問題已解除；Qwen 3.8 偶爾格式波動不能作為放寬 structural QA 的理由。

## SW-105-2-03 quarantine

- 舊 fairness 修正前，12:30 cycle 曾再次 claim `SW-105-2-03`，遇到 transient `Qwen 3.8 HTTP 502 / AI service temporarily unavailable`。
- 當時為避免 deterministic starvation，已可逆 quarantine：`pending → review`，保留 attempts=1，註明先前 `exp_others 空白` + transient 502。
- Fairness 與 v12 現在都已部署，但先不要把它混入 3 題 deterministic v12 probes。

## review queue 分流（105）

最後一次完整分類：

- standard + effectively single-answer + old HTTP 405：60 題。
- standard multi-answer：25 題（24 題兩答案、1 題三答案）；grading contract 已支援 `accepted_answers`，但 recovery 要獨立 probe / batch。
- special grading：12 題 `all_credit` + 4 題 `any_answer`，共 16 題；繼續隔離。
- v12 deterministic probes：3 題（上列）。
- queue quarantine：`SW-105-2-03` 1 題。

60 題舊 405 科目分布：

- 社會政策與社會立法：32
- 社會工作直接服務：12
- 社會工作：7
- 社會工作研究方法：5
- 人類行為與社會環境：4

## 接手建議順序

1. 重讀 main、open PR/Issue、最新 Actions、Supabase live Edge Function version/source。
2. 重查 queue counts、rolling 24h completed、pending 清單與 review 分流。
3. 看 #254 是否已完成第二個自然 post-migration cron observation；未完成就只觀察，不人工 requeue 來製造結果。
4. 第二個自然 cycle 若正常，補證據並關閉 #254。
5. 接著只 requeue `SP-115-2-006`、`SP-115-2-009`、`SP-115-2-037` 做 v12 dedicated probes；不得改 Official Core。
6. 3 題 probe 若通過，再更新 deployment closure 文件與 handoff，之後才恢復 bounded old-405 recovery。
7. standard multi-answer 另開 probe/batch；special grading 繼續隔離。

## 禁止事項

- 不可為清 backlog 修改官方題目、選項、答案、`accepted_answers` 或 `grading_mode`。
- 不可把 `ready` 宣稱為逐題人工 verified。
- 不可暴露 `job_key`、service role 或任何 production credential。
- 不可為速度移除 25/day 安全閥、單題 claim、30 分鐘 cadence 或 fail-closed validator。
- 不可因 Qwen 偶發格式錯誤就放寬欄位完整性、ASCII/數字 guard 或答案一致性規則。
