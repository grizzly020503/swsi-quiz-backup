# SWSI 跨對話未完成工作總帳

最後整理：2026-08-27

> 目的：記錄曾經在 ChatGPT / Work / 其他 AI 對話中「開始做、只做一半、停在本地、只完成 audit、或尚未有可驗證 commit」的工作，避免下一個 AI 把口頭進度誤當成已完成。
>
> 核心原則：**沒有可驗證的 repo diff / commit / CI / production evidence，就不能標記 DONE。**

## 狀態定義

- `DONE`：已有可驗證 commit / production evidence，且必要測試完成。
- `IN_PROGRESS`：已有部分程式或測試，但尚未完成驗收。
- `LOCAL_ONLY`：AI/Work 曾宣稱本地完成，但尚未 push/commit；視同未完成，直到成果持久化。
- `AUDIT_ONLY`：只完成盤點/設計，尚未實作。
- `PENDING_VERIFY`：可能已做，但目前缺足夠證據，需要重新核對 repo/CI。
- `BACKLOG`：明確尚未開始或只留下 placeholder。
- `SUPERSEDED`：舊工作已被較新的架構/方案取代，不應再照舊方案施工。

---

## A. 2026-08-26 P0/P1 code-health 修復

主要 branch：`fix/code-health-p0-20260826`

### A1. Work 88 分鐘工作階段
狀態：`LOCAL_ONLY / PENDING_VERIFY`

Work 停止前曾回報本地核心 regression 已通過，範圍包含：
- grading
- 計時模擬考
- Service Worker
- Cloudflare Worker
- Supabase contract
- MOEX parser
- Unified QA
- essay builder
- production-shaped static smoke

但停止前自己的下一步仍是：
1. 完整 diff
2. 敏感字串 / secret scan
3. 將變更整理成 atomic commit 寫入 `fix/code-health-p0-20260826`
4. 追 GitHub Actions
5. Chromium/browser smoke

因此這一批 **不能因 Work 說「regression green」就視為 DONE**。Work 當時因使用額度耗盡停止，GitHub branch 沒有出現對應的新施工 commit。

後續原則：若 Work session 還保留工作區，第一優先先保存已驗證成果；若工作區已遺失，必須以 GitHub 現況重新判定，不可照口頭摘要假設已完成。

### A2. 特殊給分 fail-closed
狀態：`IN_PROGRESS / PENDING_VERIFY`

已知要求：
- `grading_mode` 缺失的特殊給分不得從 legacy ID / `answer='一律給分'` 猜模式。
- `all_credit`：未作答仍得分。
- `any_answer`：A-D 任一作答得分，但未作答不得分。
- loader / validation / quiz / simulation 必須共用同一 grading contract。

需重新以 branch 最終 runtime + browser smoke 驗收，不能只看前段 legacy function。

### A3. 計時模擬考 grading contract
狀態：`IN_PROGRESS / PENDING_VERIFY`

曾修方向：
- accepted_answers 多答案
- all_credit 空白得分
- any_answer 空白不得分
- standard 空白不得分
- 每題進分母
- incorrect 才進錯題/複習

需確認最後生效 `window.MK`、結果頁、history/review side effects 與 Chromium smoke。

### A4. shard SHA-256 真實驗證
狀態：`IN_PROGRESS / PENDING_VERIFY`

舊問題：manifest 有 SHA，但前端曾只是把 expected hash 寫進 IndexedDB，未對下載 bytes 真正計算比對。

曾加入 runtime 驗證方案；需確認最後 branch 實際下載流程、cache fallback、hash mismatch fail behavior 與 smoke。

### A5. Service Worker / cache 更新
狀態：`IN_PROGRESS / PENDING_VERIFY`

舊問題：mutable assets cache-first + cache version 長期不變，可能讓學生持續使用舊 JS。

曾升級 v6 並調整 `monthly_patch.js` / `essay_guides.js` / manifest 更新策略；也曾發生 smoke/workflow 還寫死 v5 的測試落後問題。

需確認：
- 最終 `sw.js` VERSION
- mutable asset strategy
- 舊 cache 清除
- PWA update behavior
- workflow/smoke 不再期待 v5

### A6. essay guide duplicate key
狀態：`IN_PROGRESS / PENDING_VERIFY`

已確認 `社會工作-107-1-申論2` 曾有 duplicate key；官方題幹要求「認知行為學派＋社會支持理論＋優勢觀點」並以同一案例整合。

曾建立正規化 builder / duplicate gate 的方向；需確認部署產物是否真正唯一 key、CI 是否會阻擋新增 duplicate、verified guide 是否進 production-shaped build。

### A7. CI / release gate
狀態：`IN_PROGRESS`

曾補：
- P0 frontend preflight
- grading browser smoke
- monthly frontend QA trigger
- production-shaped build
- unified QA 最新考次自動化
- release workflow 只允許 main 手動封版的安全方向

曾遇到：
- preflight 誤把已被後置 patch 覆蓋的 legacy code 當 runtime bug
- preview workflow / smoke 寫死 SW v5
- GitHub Actions token 無權限由 workflow 自我修改另一支 workflow

需逐支核對 workflow 最終版本與最近 run，不能因「曾修過」就當全綠。

### A8. Cloudflare Worker temperature=0
狀態：`PENDING_VERIFY`

舊 bug：`Number(x) || 0.4` 會把合法的 `0` 變成 `0.4`。

曾回報已修進 branch，但需以 `cloudflare/wandering-wave-4418/worker.js` 實際 source + syntax/contract test 確認。

### A9. AI 429 錯誤分類
狀態：`IN_PROGRESS / PENDING_VERIFY`

舊問題：前端把所有 429 都顯示成「等一分鐘」，混淆 rate limit、client daily quota、global quota。

曾設計由最後生效層優先顯示 Worker JSON `error.message`；需確認文字 AI、照片 AI、feedback override 都一致。

### A10. Supabase schema / recovery SQL drift
狀態：`BACKLOG / PENDING_VERIFY`

曾確認 production trigger 比 GitHub recovery SQL 新：production official-change trigger 已把 `grading_mode` 變動納入 AI reset，但 recovery consolidation 可能仍落後。

必須比較 production schema 與 `supabase/migrations/20260825094110_production_qa_consolidation.sql`；**不要為了比對而重套 migration 到 production。**

### A11. localStorage / history / review-state 完整性
狀態：`IN_PROGRESS / BACKLOG`

已知問題：
- history 可能沒有合理上限
- localStorage quota/write failure 需要真正可見警告
- review/history 寫失敗不能只 console
- partial bank 不能誤判舊錯題不存在

曾加入部分可見 storage warning；仍需驗收 history cap、review-state、quota failure、full-bank gate。

---

## B. 前端舊 audit 曾留下、可能被後續 patch 部分修掉的工作

來源：`PROJECT_HANDOFF.md` / `FRONTEND_MONTHLY_AUDIT.md` 等。

這些項目必須以「最後生效 runtime」判斷，不可直接照舊 audit 重做。

### B1. 指定歷屆 round canonical regression
狀態：`PENDING_VERIFY`

舊 bug：內部預期 `1/2/all`，UI override 曾用 `第一次/第二次` value。

### B2. accepted_answers + grading_mode normalize
狀態：`PENDING_VERIFY`

### B3. Stored XSS context-aware encoding
狀態：`PENDING_VERIFY`

曾有 audit 與部分修正；需驗證 question/options/explanations/topic/law/source URL/inline JS 等實際 sinks。

### B4. theory / law search deep-link
狀態：`PENDING_VERIFY`

舊 bug：open state 用 name，render 用 numeric index。

### B5. 照片 AI 1–3 張契約
狀態：`PENDING_VERIFY`

Worker 已限制 3 張；舊前端曾允許/截成 4 張。需確認最後 UI 是第 4 張直接拒絕，不是默默截掉。

### B6. X-SWSI-Client-ID
狀態：`PENDING_VERIFY`

需確認文字與照片 AI fetch 都送 stable local client ID。

### B7. E-115-2-R-1 私用字元
狀態：`BACKLOG / PENDING_VERIFY`

舊 handoff 記錄 PDF 私用字元 `  `，應改為穩定 `(一)(二)(三)` 類字元。

### B8. 首頁定位 / SEO / OG / keyboard / aria
狀態：`BACKLOG / PENDING_VERIFY`

屬非 P0，但曾列入月底 patch 清單；需避免在核心 code-health 尚未收斂時混入大規模 UI 重構。

---

## C. 更早期內容/資料工作留下的半成品

### C1. LAW_UPDATED placeholder
狀態：`PENDING_VERIFY / SUPERSEDED?`

較早 `index.html` 快照曾存在空的 `LAW_UPDATED` set，註記之後加入法規更正題 ID。現在平台已建立 canonical law mapping + official law watch，因此這個 placeholder 可能已被新架構取代。

處理方式：確認現行 runtime 是否仍讀 `LAW_UPDATED`。若已由 `legal_status / legal_watch_hits / canonical mapping` 取代，標 `SUPERSEDED` 並移除舊死碼；若仍使用，需明確定義資料來源。

### C2. 「參考骨架整理中」申論 placeholder
狀態：`PENDING_VERIFY`

較早快照曾對缺 guide 顯示「參考骨架整理中——陸續補上」。目前已有約 230 題歷屆申論骨架，但需掃描現行 guide coverage，確認是否仍有真正 placeholder。

### C3. 「解析生成中」
狀態：`PENDING_VERIFY`

較早前端對缺解析題顯示「解析生成中」。目前 Supabase AI queue 已有大量 ready、仍有 pending/review 是正常狀態；需確認前端是否清楚區分 pending/review/特殊給分，而不是把所有缺解析都當成無限期 placeholder。

### C4. 舊題庫 README 的 109–114 匯入待辦
狀態：`SUPERSEDED`

較早題庫工作曾只涵蓋 104–108，README 留下「匯入 109–114、完整缺題檢查、final freeze」。現 production 已是 104–115、24 考次、4,800 題且 historical audit 0 finding，因此此舊待辦已被後續工作完整取代，不應再執行。

### C5. 2026-08-24 question backup 曾見截斷/不完整 record
狀態：`SUPERSEDED / PENDING_VERIFY source only`

舊備份檔曾出現至少一筆看似不完整/截斷 record；production 4,800 題目前已有完整結構與官方 audit，因此不應把舊 backup 當 production source。保留作歷史備份問題即可。

---

## D. 內容品質／使用者資訊分級（2026-08-27 新開獨立內容 branch）

branch：`content/credibility-labels-20260827`

狀態：`BACKLOG`

目的：不干擾 `fix/code-health-p0-20260826` 的 Work/P0 修復。

待做：
- 學長姐心得把「一定／每次／必考」等過度絕對敘述改為「高頻／常見／優先準備」，保留為個人經驗而非官方事實。
- 標示資料層級：官方資料／平台查證／學長姐經驗／AI 整理／考題預測／待複核。
- 時事雷達明確標示「考試相關度/預測」不是官方命題資訊。
- 舊心得保留年份與經驗性質。
- 暫不改 grading、shard、SW、Supabase schema、Worker、release gate。

---

## E. 自動監控／內容雷達待加強

### E1. MOEX 新題監控
狀態：`DONE（需持續觀測）`

目前 parser/import/health/CDN/QA 已形成完整鏈路；未來新增考次應靠 manifest/最新考次自動化，不要再寫死 115-2。

### E2. 法規監測
狀態：`DONE（需持續觀測）`

52/52 official watch 已正常；真修法只更新 legal status/watch hits，不修改官方歷史題幹/答案。

### E3. 時事雷達來源與 relevance
狀態：`BACKLOG`

目前自動化骨架可用，但來源與 keyword classifier 仍偏窄。後續應：
- 擴充高品質官方來源
- 增加考試相關度/relevance scoring
- 區分「新聞事件」與「可能考點」
- 對應科目/理論/法規/歷屆相似題
- 高相關才推薦給學生

這是內容品質工作，不應和目前 P0 code-health 修復混在同一 commit。

---

## F. 每個 AI 接班前必做的 reconciliation

每次新 ChatGPT / Work / Claude / Gemini / Codex 接手，不可只讀本 ledger 後直接施工。必須：

1. 讀 `AGENTS.md`。
2. 讀 `PROJECT_HANDOFF.md`。
3. 讀 `KNOWN_ISSUES.md` / `DECISIONS.md` / `TESTING.md`。
4. 查看目標 branch HEAD 與最近 commits。
5. 查看 `main...branch` diff。
6. 查看最近 CI / workflow runs。
7. 對本 ledger 每個 `IN_PROGRESS / LOCAL_ONLY / PENDING_VERIFY` 項目做證據核對。
8. 只有有證據才改成 `DONE`。
9. 每完成一組工作：測試 → commit → 更新 handoff/ledger。

### 禁止事項
- 不可把「前一個 AI 說它做完」當成完成證據。
- 不可因 audit 寫著 bug 就假設現行 runtime 還有 bug。
- 不可因 legacy code 還存在就忽略最後載入 override。
- 不可讓未 commit 的 Work 本地成果成為唯一 source of truth。
- 不可在不同 AI 同時施工時共用同一 branch 而沒有協調。

---

## G. 下一輪建議處理順序

1. **先救/確認 Work 88 分鐘本地成果是否能持久化。**
2. 對 `fix/code-health-p0-20260826` 做完整 `main...branch` reconciliation。
3. 收斂 A2–A11 P0/P1，跑真正 browser/Chromium + CI。
4. 把 B 類舊 audit 項目逐一標成 DONE / STILL_BROKEN / SUPERSEDED。
5. 核對 C 類舊 placeholder，清除已被新架構取代的死待辦。
6. 核心修復穩定後，再獨立處理 D/E 內容品質與時事雷達。
7. 最後更新 `PROJECT_HANDOFF.md`，讓「現在真正下一步」與本 ledger 一致。
