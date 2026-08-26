# SWSI 未完成工作證據核對附錄 — 2026-08-27

本檔是 `UNFINISHED_WORK_LEDGER.md` 的 evidence reconciliation。若兩者狀態衝突，以本檔較新的 repo / diff 證據為準，直到 ledger 下次整併更新。

## 1. Branch 整體現況

`fix/code-health-p0-20260826` 與 `main` 比較：

- merge base：`9894bcfaa388c6a90a487fbb5d95a5e993dcecd8`
- branch 相對 main：ahead 26 commits / behind 1 commit
- 這不是單純 audit branch；已包含實際 runtime、Worker、SW、builder、CI、smoke 等施工檔。

主要已持久化檔案包括：
- `monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part`
- `monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part`
- `monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_final_runtime_contract.part`
- `monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_ai_quota_message.part`
- `sw.js`
- `cloudflare/wandering-wave-4418/worker.js`
- `scripts/build_essay_guides_runtime.js`
- `scripts/grading_contract_smoke.js`
- `scripts/p0_frontend_preflight.js`
- `scripts/monthly_frontend_smoke.py`
- `.github/workflows/monthly-frontend-qa.yml`
- `.github/workflows/build-netlify-package.yml`
- `.github/workflows/unified-question-qa.yml`

因此 Work 88 分鐘工作不能再概括標成「全部 LOCAL_ONLY」。應拆成：已持久化子項 + 尚未完成的整體驗收。

---

## 2. 已找到明確實作證據

### 2.1 特殊給分 fail-closed
狀態：`IMPLEMENTED / NEEDS_FINAL_CI`

證據 commit：
- `9894bcfaa388c6a90a487fbb5d95a5e993dcecd8` — `修正特殊給分 fail-closed 與題庫 shard 完整性驗證`

實作包含：
- 嚴格 `standard / all_credit / any_answer`
- 特殊答案 marker 缺 mode → `invalid`
- 普通 legacy A-D 可 fallback standard
- `all_credit` 未作答 → true
- `any_answer` 未作答 → false
- 多答案使用 `accepted_answers`
- invalid 題在 UI 暫停判分，不自行猜答案

注意：仍需以最終 production-shaped runtime / Chromium smoke 驗收，因 legacy helper 仍存在於較前載入層。

### 2.2 shard SHA-256 真實下載驗證
狀態：`IMPLEMENTED / NEEDS_FINAL_CI`

同 commit `9894bcf...` 已：
- 對實際 response clone bytes 執行 `crypto.subtle.digest('SHA-256', ...)`
- 與 manifest expected SHA 比對
- mismatch 直接 throw / 停止載入
- manifest SHA 非 64 hex 也 fail
- 舊 IndexedDB `question-shard:*` cache 在重新連線後做一次 purge migration

因此「SHA 只有寫 manifest、完全沒驗」已不再是 branch 現況；剩餘是整合 smoke / fallback 行為驗收。

### 2.3 localStorage 寫入失敗可見警告
狀態：`PARTIALLY_IMPLEMENTED`

`9894bcf...` 已覆寫：
- `saveHist`
- `saveReviewState`

寫入失敗會顯示 visible toast，而不是只 console。

仍未證明完成：
- history retention/cap
- localStorage 長期容量策略
- partial-bank review/full-bank gate

所以 A11 不可整項 DONE，只能把「可見 storage failure」子項改 DONE。

### 2.4 計時模擬考 grading contract
狀態：`IMPLEMENTED / NEEDS_FINAL_BROWSER_SMOKE`

證據 commit：
- `970e98a76133c8ed396b2c67d8b3633cfdf24477` — `統一計時模擬考與正式判題契約`

它建立新的 `window.MK` runtime，明確呼叫：
- `window.gradingMode(q)`
- `window.isCorrectAnswer(q,picked)`
- `window.answerLabel(q)`

並在指定歷屆含 invalid grading metadata 時阻擋開考。

因此「模擬考完全仍是舊 private grade()」已被 branch 後置 runtime 取代；但仍需 Chromium 行為測試確認：
- all_credit 空白
- any_answer 空白
- accepted_answers
- 每題分母
- history/review side effect

### 2.5 Service Worker v6 / mutable assets 更新策略
狀態：`IMPLEMENTED / NEEDS_FINAL_SMOKE`

branch `sw.js` 已明確：
- `VERSION = 'v6'`
- activate 刪除非目前 cache
- HTML：no-store network-first
- `auto/`：no-store network-first
- `monthly_patch.js / essay_guides.js / manifest.json`：no-store network-first
- 跨域 Cloudflare shard / Supabase / AI：SW 不攔

注意：檔中仍留一行 `Legacy preview smoke compatibility only; runtime no longer uses: const VERSION = 'v5';` 註解，這是為相容舊 preview smoke，不是 runtime v5。

剩餘：實際 update/offline smoke 與 workflow 是否還有舊 v5 expectation。

### 2.6 Essay guide 107-1 duplicate normalization
狀態：`IMPLEMENTED / NEEDS_PIPELINE_CI`

證據 commit：
- `f50819ef4263ef76b89aee4bcdfe88a438641e92` — `正規化申論 guide 並修正 107-1 重複題`

`build_essay_guides_runtime.js` 已：
- 掃 historical key duplicate
- 只暫容忍已知 legacy duplicate `社會工作-107-1-申論2` x2
- 其他 duplicate 直接 fail
- 依官方題幹重建該題 verified guide：認知行為＋社會支持＋優勢觀點＋同案整合
- 重新序列化 runtime object，輸出唯一 key
- 生成後再檢查 historical ID duplicate

剩餘：確認 production-shaped build 一定使用 builder 產物，而非 raw `essay_guides.js`。

### 2.7 AI 429 daily quota 訊息
狀態：`IMPLEMENTED / NEEDS_RUNTIME_SMOKE`

branch 有最後載入：
`monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_ai_quota_message.part`

它會攔 429 response JSON，讀：
- `error.message`
- `error.code`

並區分：
- `CLIENT_DAILY_QUOTA`
- `GLOBAL_DAILY_QUOTA`
- 其他 AI 使用提醒

同時 wrap：
- `runAIFeedback`
- `gradePhoto`

因此「所有 429 永遠只顯示等一分鐘」已被 branch 後置層修正；仍需 browser smoke 證明最後 override 順序正確。

### 2.8 Cloudflare Worker temperature=0
狀態：`IMPLEMENTED / NEEDS_DEPLOY_DECISION`

branch `cloudflare/wandering-wave-4418/worker.js` 已從 falsy fallback 改成：

`Number.isFinite(Number(body.temperature)) ? Number(body.temperature) : 0.4`

再 clamp 0..上限。

因此合法 `temperature: 0` 不再變成 0.4。

重要：這只證明 repo branch source 已修，不代表 production Worker 已部署；production deploy 仍需明確授權/驗收。

### 2.9 Unified Question QA
狀態：`IMPLEMENTED / PREVIOUSLY_VALIDATED`

已有連續 commits：
- `245020c6...` 設計統一 QA
- `689b2ee4...` policy v1
- `a1d7bb40...` QA engine
- `8076694d...` synthetic self-test
- `40e62859...` 非部署 CI self-test
- `fe442b7e...` 真實 115-2
- `c8acf2b3...` baseline
- `1b2a0653...` 避免「第三條路」法條誤判
- `c602a814...` legal watch 去重
- `f85aaecd...` legal watch + 第三條路 tests
- `175d37bb...` 當期 QA trust-current-legal-watch
- `214427da...` 115-2 human queue 0 baseline
- `56ac1e01...` lightweight dashboard builder
- `3dae0001...` workflow dashboard payload
- `c8bd9c44...` dashboard contract

此區不是「做到一半後消失」；核心架構已持久化。剩餘工作是把它真正納入最終 release gate 與未來考次持續觀測。

---

## 3. 仍不能標 DONE 的項目

### 3.1 整體 branch release readiness
狀態：`IN_PROGRESS`

原因：
- branch 相對 main 已 diverged（ahead 26 / behind 1）
- 尚未完成本輪最終 `main...branch` reconciliation
- 尚未確認全部 GitHub Actions / Chromium browser smoke 最終綠燈
- 尚未做敏感字串/secret scan 完整結果保存
- 尚未做 merge/rebase 策略

### 3.2 CI / release gate 完整性
狀態：`IN_PROGRESS`

雖然 branch 已修改：
- monthly frontend QA
- build Netlify package
- unified QA
- preflight
- grading smoke

但歷史上曾出現：
- preflight 誤判 legacy code
- smoke 預期 SW v5
- preview workflow 自己也有 v5 assumption
- workflow token 不允許 workflow 自我修改另一 workflow

需以「目前 branch 最新 workflow source + 最近 runs」重新驗。

### 3.3 Supabase recovery SQL drift
狀態：`STILL_OPEN`

production 曾確認 official-change trigger 包含 `grading_mode`；GitHub recovery consolidation 曾較舊。尚未在本 reconciliation 完成 production schema vs recovery SQL 的完整只讀 diff。

### 3.4 localStorage/history 長期容量
狀態：`STILL_OPEN`

visible failure warning 已做；history cap/compaction 仍無完成證據。

### 3.5 Stored XSS 全面封口
狀態：`PENDING_VERIFY`

已有多輪 XSS audit / escape patch，但尚未在本輪對最後 runtime 所有 sink 逐項重驗。不能因較早 audit 或局部 escape 就標 DONE。

### 3.6 Round canonical / theory-law deep-link / photo 1–3 / client ID
狀態：`PENDING_VERIFY`

先前對話曾回報其中多項已被最後 patch 修正，但本輪還沒把每一項綁到確切 commit + runtime smoke；維持待核對。

### 3.7 E-115-2-R-1 私用字元
狀態：`PENDING_VERIFY`

尚未找到本輪明確修正 evidence。

---

## 4. 對 Work 88 分鐘 session 的重新判定

原先：`LOCAL_ONLY / PENDING_VERIFY`

現在應改成：

`PARTIALLY_PERSISTED / FINAL_VALIDATION_INCOMPLETE`

原因：branch 已明確存在大量對應施工檔與 commits；Work 並非 88 分鐘全部白做或全部只留本地。但它停止前承諾的「完整 diff / secret scan / atomic commit / Actions / Chromium 最終追蹤」沒有完整證據，不能把整個 session 標 DONE。

未來恢復 Work 時：
1. 先讀 branch HEAD，不要把已持久化項目重寫。
2. `main...fix` reconciliation。
3. 跑最終 CI / Chromium。
4. 修真正紅燈。
5. 每一組可驗證修改立即 commit。
6. 最後更新 `PROJECT_HANDOFF.md` + ledger/reconciliation。

---

## 5. 下一輪證據核對優先序

1. GitHub Actions 最近 runs：monthly frontend QA / Cloudflare preview / unified QA / build package。
2. `final_runtime_contract.part`：round canonical 與最後 override。
3. AI client ID 與 photo limit 最後生效層。
4. XSS sinks。
5. recovery SQL drift。
6. E-115-2-R-1 私用字元。
7. 舊 `LAW_UPDATED` / placeholder 是否已 superseded。

只有完成這些後，才把 ledger 大批 `PENDING_VERIFY` 改成最終狀態。
