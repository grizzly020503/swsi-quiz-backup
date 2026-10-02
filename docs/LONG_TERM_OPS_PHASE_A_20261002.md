# SWSI 長期自動維運 Phase A — 第一批實作（2026-10-02）

本文件對應 Issue #262 的第一階段可觀測性工作。開始任何後續修改前仍需重新讀取最新 main、open PR/Issue 與 Actions，不要把本文的 SHA 或狀態當成永久真相。

## 本批範圍

### 1. 全庫題庫 QA

新增 `scripts/full_corpus_qa.py` 與 `.github/workflows/full-corpus-qa.yml`。

- 以 `cdn/question-shards/manifest.json` 為 MCQ 掃描範圍，不把 4,800 或 24 shard 寫死成永久常數。
- 逐 shard 驗證檔案存在、SHA-256、question_count、session 唯一性。
- 申論不另建平行資料源；直接沿用既有 `scripts/official_exam_readonly_guard.py` 的 canonical source path：歷史題來自 `index.html` 的 `window.ESSAYS`，最新同步題來自 `auto/essays_auto.json`，以 immutable Official Core fields 偵測同 ID 衝突。
- 每一考次再交給既有 `scripts/unified_question_qa.py` 驗 MCQ + 該考次申論；先跑 `official_exam_readonly_guard.py` 確保已鎖定官方原文沒有遭修改。
- 報表分別列出 MCQ、essay 與 total；以 2026-10-02 現有 24 考次資料為基線，完整巡檢應覆蓋 4,800 MCQ + 240 essay = 5,040 official items。這是當下資料基線，不是把未來考制硬編碼成永遠固定 5,040。
- Official Core blocked、manifest 缺漏、shard hash/count 錯誤、essay session 缺漏／多出，或 aggregate item 對不上來源時會讓 workflow 失敗。
- enrichment/manual-review 訊號會列入報表，但不因尚待內容審查就把 Official Core 假裝損壞。
- 每月 1 日跑一次，也保留 `workflow_dispatch` 供首輪 bootstrap／受控重跑。
- 14 天 artifact 僅為診斷，不當作 10 年證據庫。

### 2. 維運任務 registry

新增 `data/ops_task_registry.v1.json`，先登錄：

- Public Monitoring Feed：預期每 6 小時，8 小時視為 stale。
- Public Uptime Sentinel：預期每日，30 小時視為 stale。
- MOEX Social Worker Exam Sync：預期每週，192 小時視為 stale。
- Full Corpus Question QA：預期每月，840 小時視為 stale。

Full Corpus QA 首輪允許 `workflow_dispatch` 作 bootstrap；正常月排程成功後，自然會成為較新的成功紀錄。

### 3. 任務漏跑 watchdog

新增 `scripts/ops_task_watchdog.py`、`scripts/ops_task_watchdog_selftest.py` 與 `.github/workflows/ops-task-watchdog.yml`。

- read-only 查 GitHub Actions API。
- 只把 registry 指定 event 的 success run 算成有效成功，不讓無關 push 自動掩蓋 schedule 漏跑。
- 依最後成功時間判斷 healthy / stale / missing / error。
- high / critical 任務 stale、missing、error 時 workflow 失敗。
- fixture self-test 覆蓋 healthy、stale、missing，以及「push 成功不能冒充 schedule 成功」。
- 每 6 小時檢查一次，與 Public Monitoring Feed 錯開。

## 首輪 CI 找到並修正的覆蓋缺口

PR #263 第一版雖然 24/24 sessions 綠燈，但報表只有 4,810 items。原因不是 MCQ 漏掃，而是 runner 錯把 `auto/essays_auto.json`（115-2 最新 10 題）當作全部申論來源。

此問題已在 PR 內修正，不以「CI 綠燈」掩蓋錯誤覆蓋：

- 歷史 230 題重新沿用 `index.html` / `window.ESSAYS`；
- 最新 10 題沿用 `auto/essays_auto.json`；
- `data/official_exam_readonly.lock.json` 已存在 240 essay immutable hashes；
- 第二輪驗收必須看到 240 essay 與總數 5,040 才能將本批稱為 full-corpus。

## 明確沒有完成的項目

這一批 **不代表 #262 Phase A 已全部完成**。

仍缺：

1. **獨立於 GitHub Actions 的 heartbeat。** 現在 watchdog 自己仍跑在 GitHub Actions；如果整個 Actions 停擺，它不能靠自己偵測自己。P1-6 仍需外部／不同失效域的監測來源。
2. **考制版本化。** 現有 `data/question_qa_policy_v1.json` 仍代表目前 5 科 × 40 選擇／5 科 × 2 申論的既有契約；未來 116+ 制度變更辨識要另做正式 exam-format registry 與 candidate quarantine。
3. **持久 job queue / lease / checkpoint。** 本批先建立 task freshness registry；尚未建立統一跨工作 persistent queue。
4. **長期證據庫。** Actions artifact 有保留期限；後續需把重要非敏感證據保存到版本化、可校驗的 repo/source 或其他長期位置。
5. **自動修復／自動發布。** 本批完全沒有擴大寫入、部署、權限或自動修資料能力。

## 安全邊界

- 不修改官方題幹、選項、答案、accepted_answers、grading_mode。
- 不改 Supabase production schema、RLS、Edge Functions 或 secrets。
- 不新增付費服務。
- 不讓 watchdog 自動 rerun／disable／enable workflow；它只觀察並 fail visibly。
- 不把 GitHub-internal watchdog 宣稱成 independent monitoring。

## 下一步

建議下一批依序：

1. exam-format registry + future candidate mismatch quarantine；
2. 將全庫 QA 結果轉成持久、版本化的 compact health snapshot；
3. 建立至少一條不同失效域的 heartbeat；
4. 再設計統一 job registry / lease / checkpoint，不直接跳到無限制自動修復。
