# SWSI AI 解析 Recovery Handoff — 2026-10-02

> 這份文件是 2026-10-02 production recovery 的即時交接。接手前仍必須重新讀 main、Supabase production、open PR/Issue 與最新 Actions，不要假設本文中的 SHA、計數或狀態永遠最新。

## READ FIRST

1. **Cloudflare / Qwen 3.8 migration 已完成，不要重做。** Production Worker current model 為 `qwen/qwen3.8-27b`；legacy `qwen/qwen3.6-27b` 由 Worker alias 到 3.8。
2. **AI queue fairness 已正式上 production。** PR #256 已 merge，migration `ai_queue_fair_retry_rotation` 已套用；Issue #254 暫時保持 open，只因驗收規則要求觀察至少兩個自然 cron cycle。
3. **不要把所有 review 一次重設 pending。** 目前 recovery 仍受每次 1 題、每 30 分鐘、rolling 24h 最多完成 25 題保護。
4. **multi-answer、special grading、真正內容／格式失敗不要混入舊 405 infra recovery。**
5. **Analyzer v12 source 已 merge，但 Supabase production Edge Function 仍是 v11。** Direct connector deploy 曾被 safety layer 在部署前阻擋；不可用 credential obfuscation、改 auth model、猜 secret name 等方式繞過。

## GitHub / main

- 最新已知 main（2026-10-02 約 13:00 Asia/Taipei）：`94bfae55b4cdeb2cc6766f311cccd46b92adeda9`，接手仍要重查。
- PR #250：Analyzer v12 reliability hardening，已 merge。
- PR #252：pg_net transport timeout 延長到 120,000 ms，已 merge且 production cron parity 已驗證。
- PR #256：AI queue retry fairness，已 merge；Disaster Recovery Restore Drill #60 全綠後才合併。
- Issue #254：fairness production observation，保持 open，待至少第二個自然 cron cycle 驗證後才可關閉。

## Cloudflare / 題庫 runtime

- live question dataset revision：`5c4acad4299dbae1caee`。
- live 題庫：4,800 MCQ / 24 shards。
- `115-2` live shard：200 題，`accepted_answers` contract 正常。
- live Production Artifact QA 已成功，Public Uptime Sentinel 曾由 production QA 自動觸發並 success。
- `cdn/monthly_patch.js` 已由 canonical `monthly_patch_parts` 重建並通過 artifact smoke。

## Supabase analyzer production

- project：`Swsi` / ref `yumjtrdctaxyczpspuyo`。
- `analyze-pending-questions` production 目前仍為 **v11 ACTIVE**；接手要重新讀 live function version/source。
- v11 draft model：Qwen 3.8；audit model：`openai/gpt-oss-120b`。
- Edge Function custom auth：`x-job-key` 對 `ai_analysis_job_config.job_key`；**不要讀出或記錄明文 key**。
- pg_cron job id 3：`*/30 * * * *`，每次 body `{"limit":1}`。
- live `cron.job.command` 已確認使用 `timeout_milliseconds := 120000`。
- `claim_pending_ai_questions(integer)` 仍硬性每次最多 1 題；rolling 24h `analysis_completed_at >= now()-24h` 達 25 題就停止 claim。

### Queue fairness 已上 production

PR #256 / migration `20261002045108_ai_queue_fair_retry_rotation.sql` 已完成：

- 新增 operational 欄位 `questions.analysis_last_attempt_at timestamptz`。
- claim 排序改成：
  1. `analysis_last_attempt_at NULLS FIRST`（從未嘗試先跑）；
  2. 之後 oldest-attempted 先跑；
  3. 原本 `source_exam_code / qno / subject / id` 只作 tie-breaker。
- 每次 claim 會寫入 `analysis_last_attempt_at = now()`。
- Official Core 變更造成 fresh analysis reset 時，會把 `analysis_last_attempt_at` 清回 null。
- stale `analyzing > 15 minutes` recovery 保留。
- ACL live 驗證：`anon=false`、`authenticated=false`、`service_role=true` for `claim_pending_ai_questions(integer)`。
- live function 已重新讀取確認仍保留 `max 1` 與 `25/24h` 安全閥。

### 第一個自然 post-migration cron cycle 已驗證

2026-10-02 13:00 Asia/Taipei：

- cron runid 623 / jobid 3，scheduler submission `succeeded`。
- `SP112-2-03` 在 `2026-10-02 05:00:02.024626+00` 被正式 cron claim。
- 該題寫入新的 `analysis_last_attempt_at`，並成功完成為 `ready`，無 analysis error。
- 這次沒有人工 claim / requeue，因此可視為第一個有效 production fairness observation。
- Issue #254 規則要求至少兩個自然 cycle；**在第二個 cycle 前不要為了驗收而人工製造 queue 行為。**

## 最新 live queue snapshot

約 2026-10-02 13:00 Asia/Taipei：

- pending：11
- analyzing：0
- ready：4,684
- review：105
- completed previous rolling 24h：15 / 25

此數會變動；接手務必重查。

## 既有 recovery 已驗證行為

以下舊題曾從失敗狀態實際 recovery 成 `ready`，證明 production 完整鏈可工作：

- `HBSE-115-2-027`
- `DS-115-2-008`
- `DS-115-2-039`（第一次 JSON array 格式錯，第二次成功）
- `SW-115-2-040`（第一次 `exp_others 空白`，第二次成功）
- `R-115-2-004`
- `R-115-2-010`（第一次 `exp_others 空白`，第二次成功）
- `R-115-2-023`（第一次 JSON array 格式錯，第二次成功）

結論：舊 HTTP 405 基礎設施問題已解除；Qwen 3.8 偶爾仍有輸出格式波動，但不能因此放寬 structural QA。

## SW-105-2-03 quarantine 歷史

- 12:30 cycle 曾再次 claim `SW-105-2-03`，遇到 transient `Qwen 3.8 HTTP 502 / AI service temporarily unavailable`。
- 因舊 claim function 沒有 retry fairness，該題排序靠前，會反覆霸占 queue。
- 為避免 starvation，當時已做可逆 quarantine：`pending → review`，保留 attempts=1，註明先前 `exp_others 空白` + transient 502。
- 現在 queue fairness 已正式上 production，但 **不要立刻把這題丟回 pending**；先完成 #254 第二個自然 cycle 驗收，再決定 v12 後是否重試。

## review queue 分流（105）

最後一次完整分類：

- standard + effectively single-answer + old HTTP 405：60 題，可作後續 bounded infra recovery。
- standard multi-answer：25 題（24 題兩答案、1 題三答案）；grading contract 已支援 `accepted_answers`，但 recovery 要獨立 probe / batch。
- special grading：12 題 `all_credit` + 4 題 `any_answer`，共 16 題；繼續隔離。
- genuine format/content review：3 題。
  - `SP-115-2-006`：`AI 回傳找不到 JSON array`
  - `SP-115-2-009`：`exp_others 空白`
  - `SP-115-2-037`：`AI 回傳找不到 JSON array`
- queue quarantine：`SW-105-2-03` 1 題。

60 題舊 405 的科目分布：

- 社會政策與社會立法：32
- 社會工作直接服務：12
- 社會工作：7
- 社會工作研究方法：5
- 人類行為與社會環境：4

## Analyzer v12 部署邊界

- PR #250 已 merge；source hardening 包含：
  - malformed model JSON-array output retry；
  - strict validator 首次 rejection 後的 repair audit。
- production Supabase `analyze-pending-questions` 仍是 **v11**。
- direct connector deploy 曾被 platform safety layer 在 deployment 前阻擋；沒有 partial deployment。
- 不可繞過 safety block，不可暴露或改造 credentials，不可為了 deploy 改 auth model。
- 正式 v12 部署後，優先用以下 3 題做 deterministic production validation：
  - `SP-115-2-006`
  - `SP-115-2-009`
  - `SP-115-2-037`
- 另見 `docs/AI_ANALYZER_V12_DEPLOY_BLOCKER_20261002.md`。

## 接手建議順序

1. 重讀 main、open PR/Issue、最新 Actions、Supabase live Edge Function version/source。
2. 重查 queue counts、24h completed count、pending 清單與 review 分流。
3. 先看 #254 是否已完成第二個自然 post-migration cron observation；未完成就只觀察，不人工 requeue 來製造結果。
4. 第二個自然 cycle 若正常，再關閉 #254，並更新本 handoff / PROJECT_HANDOFF。
5. Analyzer v12 只能透過正式授權 Supabase deployment path 上 production；部署後先重新讀 live version/source，再跑 3 題指定 probes。
6. v12 驗收成功後，才恢復 bounded old-405 recovery；一次小批次，仍受 1 claim / 30 min / 25 per rolling 24h 保護。
7. standard multi-answer 另開 probe/batch；special grading 繼續隔離，不和 standard recovery 混跑。

## 禁止事項

- 不可為清 backlog 修改官方題目、選項、答案、`accepted_answers` 或 `grading_mode`。
- 不可把 `ready` 宣稱為逐題人工 verified。
- 不可暴露 `job_key`、service role 或任何 production credential。
- 不可為了速度移除 25/day 安全閥、單題 claim、30 分鐘 cadence 或 fail-closed validator。
- 不可因 Qwen 偶發格式錯誤就放寬欄位完整性、ASCII/數字 guard 或答案一致性規則。
- 不可在未確認 production live function/version 前宣稱 Analyzer v12 已部署。
