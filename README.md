# 社工師國考免費學習平台（SWSI）

重建日期：2026-08-24  
文件更新：2026-08-27

## 🤖 AI / 新工作階段：請先看這裡

> **任何 AI、Codex、ChatGPT Work 或新接手者，在修改程式、部署、重構或新增功能以前，都必須先讀這一節。不要先猜架構。**

Repo：`grizzly020503/swsi-quiz-backup`

### 固定接手流程

1. 先讀 `PROJECT_HANDOFF.md`（目前進度與 source of truth）。
2. 再讀 `ADMIN_MONITORING_PLAN.md`（下一階段管理後台／監測 roadmap）。
3. 依任務需要再讀 `PRELAUNCH_QA.md`、`MONTHLY_PATCH_PLAN.md`、`CDN_FRONTEND_MIGRATION_DESIGN.md`、相關 audit 與 `.github/workflows/`。
4. 重新確認遠端 `main`、工作 branch、最新 HEAD、compare 與最新 Actions；**不要假設聊天紀錄中的 SHA 仍是最新**。
5. 開始工作前先簡短確認：目前做到哪裡、哪些已完成不可重做、真正下一步、部署／安全限制。

### 給任何 AI 的萬用接手指令

```text
請先讀 GitHub 私人 repo grizzly020503/swsi-quiz-backup 的 README.md、PROJECT_HANDOFF.md 與 ADMIN_MONITORING_PLAN.md，再開始任何工作。

先重新確認目前 main、工作 branch、最新 HEAD、branch compare、最新 Actions 與 release 狀態，不要假設聊天裡的 SHA 還是最新。

先用自己的話簡短整理：
1. 目前平台做到哪裡。
2. 已完成哪些功能。
3. 哪些東西明確不能重做。
4. 現在真正下一步是什麼。
5. 有哪些安全／部署限制。

讀完以前不要猜架構、不要重新設計、不要做 cosmetic refactor、不要修改 production。
如果文件內容互相衝突，以最新 PROJECT_HANDOFF.md、遠端實際狀態與最新 commit 為準。
之後再依我這次交代的任務繼續。
```

### 不同任務追加一句

- 管理後台／監測：`這次依 ADMIN_MONITORING_PLAN.md 規劃或實作 SWSI Admin & Monitoring v1；不要把管理功能塞進學生主介面。`
- 修 bug：`這次只處理我指定的 bug；先找 root cause，不要順手做無關重構。`
- Release／部署：`這次只做 release / deployment；不要新增功能或 code-health cleanup，優先使用已驗證 artifact，不手工重建封版包。`
- Audit：`這次只做 audit；沒有證據充分的 P0/P1 就不要產生 runtime commit。`

### 絕對不要做

- 不要把 service-role key、Groq key、Cloudflare token、Netlify token、internal key、密碼或其他 production secret 寫進 GitHub。
- 不要 force push 或改寫已驗證 release 歷史，除非有明確、必要且經授權的理由。
- 不要為了減少檔案數、讓程式「看起來漂亮」而破壞 deliberate runtime owners。
- 不要手工改 workflow 已驗證的 production ZIP 後再宣稱是同一封版 artifact。
- 不要讓 AI 故障拖垮刷題、錯題與非 AI 申論核心功能。

## 🛠️ 下一階段：SWSI Admin & Monitoring v1

管理者不是工程師，因此後台的成功標準是：**30 秒內能看懂網站是否正常、哪裡需要處理、下一步該做什麼。** 詳細規格以 `ADMIN_MONITORING_PLAN.md` 為準。

預定管理中心只保留簡單入口：

- **總覽**：網站／題庫／Supabase／AI／Service Worker 健康狀態、目前版本、最近部署。
- **使用者回報**：讀取 `swsi_feedback_reports`，顯示待處理／處理中／已完成、題目或頁面 context、管理備註。
- **系統監測**：使用量、刷題量、申論／AI 次數、AI 429／timeout、API／shard／storage／SW 異常。
- **安全狀態**：異常流量、spam、rate-limit 觸發與簡化警示。
- **緊急保護模式（未來）**：必要時可暫停 AI／照片／匿名回報，但盡量保留刷題、錯題、法規／理論與非 AI 申論。
- **外部 uptime monitoring**：必須獨立於 `/admin`；整站掛掉時仍能通知管理者。

後台文字優先顯示「正常／注意／異常」與可執行建議；HTTP status、SHA、JSON、runtime owner 等工程資訊預設藏在進階區。

**這是 Round 8 之後的新 roadmap。不得為了 Admin v1 修改或重建已封版的 Round 8 production artifact。**

## 平台核心初衷

SWSI 的目標不是做另一個付費題庫，而是提供：

- **免費**
- **公開**
- **低門檻**
- **真的能幫考生準備社工師國考**

核心功能不應被訂閱制或付費牆鎖住。產品決策先問：

> **這個改動，有沒有讓考生更容易免費準備社工師國考？**

## 學生端核心範圍

目前只把三件事當成學生端核心：

1. **刷選擇題**：智慧推薦、指定年份／考次／科目、歷屆題庫。
2. **錯題複習**：錯題本＋1→3→7→14→30 天間隔複習。
3. **申論練習**：歷屆申論、拆題骨架、草稿與 AI 練習回饋。

新增功能前先問：它是否直接幫助「刷題、複習、申論」其中一件事？若不是，優先不放進主介面；維護與監測功能留在後台。

## 維護原則

- **前台做減法，後台做自動化。**
- 題庫可以持續增加，但首頁與主要導覽不跟著增加。
- 最近 10 個考試年度作為日常主題庫；更早題目保留為歷史題庫，不刪除官方資料。
- 法規較舊不等於答案一定失效；只有確認法規異動後才進入重新核對流程。
- AI 不得修改考選部官方題目、選項、答案或官方給分模式，只能補解析與分類。
- 優先使用免費方案；不要新增會自動產生帳單的服務或金鑰。
- 學生端採集中月更；未到施工時不要為了小改動反覆觸發 Netlify production deploy。

## 目前正式資料流

```text
考選部官方試題／答案
  ↓
GitHub Actions parser + health check
  ↓
Supabase questions / essays（後台 source of truth）
  ↓
GitHub Actions question-shard builder
  ↓
Cloudflare Worker Static Assets /question-shards/*.json（CDN）
  ↓
Netlify 學生端（月底切換為按需讀 shard）
  ↓
IndexedDB 離線備援
```

AI 申論則走另一條路：

```text
Netlify 學生端
  ↓
Cloudflare Worker（Origin / rate limit / D1 daily quota）
  ↓
Groq
```

後台 AI analyzer 以內部驗證方式呼叫同一 Worker，不吃學生公開 quota。

## 題庫現況

### 正式 Supabase 選擇題

- 總數：**4,800 題**
- ROC 104–115
- 24 個考次
- 5 科
- 每科每考次 40 題
- 115 年第 2 次另有 **10 題申論題**

Historical MOEX Answer + Grading Mode Audit 已逐題核對：

- 官方題數：4,800
- Supabase 題數：4,800
- answer findings：**0**
- grading-mode mismatches：**0**

### 官方多答案與特殊給分

- `accepted_answers` 多答案題：**24 題**
- `grading_mode='standard'`：**4,784 題**
- `grading_mode='all_credit'`：**12 題**
  - A/B/C/D 任一作答得分
  - **未作答也得分**
- `grading_mode='any_answer'`：**4 題**
  - A/B/C/D 任一作答得分
  - **未作答不得分**

因此不能再只看 `answer='一律給分'` 猜計分規則。學生端月底 patch 必須統一使用 `accepted_answers + grading_mode`。

## Cloudflare 題庫 CDN

後端已完成並通過 production runtime smoke：

- 目前 baseline：24 shards（104-1 ～ 115-2）
- 每 shard 200 題
- manifest 與 shard 可正常由 Cloudflare Static Assets 提供
- production 已確認 cache hit、CORS、cache-control 與 `nosniff`
- AI Worker root 的 no-Origin POST 仍會 403，Static Assets 沒有吃掉 AI API route
- builder 可在未來 116、117…完整考次出現時自動新增 shard
- 116-1 模擬已驗證可由 4,800 題／24 shard 自動擴成 5,000 題／25 shard

**目前真正尚未完成的是 Netlify 學生端 loader 切換；不要重做 CDN 後端。**

## 考選部同步與後台自動化

GitHub Actions 不只一條 workflow。現在包括考選部同步、題庫 shard build/publish、法規監測、申論時事雷達等後台自動化；實際最新清單以 `.github/workflows/` 與 `PROJECT_HANDOFF.md` 為準。

MOEX 同步目前：

- parser 可處理普通答案、多答案與官方特殊給分模式
- 解析不安全時 fail closed，不碰 Supabase
- importer 會驗證 `accepted_answers` 與 `grading_mode`
- health check 會驗證 local / remote 題數與 grading-mode 語意
- schema-only backfill 不再被誤判為官方內容變更

## 申論時事雷達原則

- 學生端只保留既有 **「時事庫」**，不要再新增第二個新聞／時事主入口。
- `scripts/current_affairs_watch.py` 每日掃描公開來源，以台灣事件優先；國際事件只有高度相關於社工、社福、人權、移民、高齡、心理健康或災害議題時才收錄。
- 自動掃描結果屬於 **「最新雷達」**，用途是發現可能的申論題材，不代表命題保證。
- `auto/current_affairs.json` 是輕量公開快照；Supabase `current_affairs` 保留後台紀錄與人工狀態。
- 只有具備持續性、制度性、跨科可考性的事件，才應升級成正式時事預測題。
- 新聞只保留標題、短摘要、來源、日期、原文連結與考點分類，不複製全文。

## 救援母檔

`data/questions_master_backup_20260824_2220.csv` 是重建當下的 **4,600 題原始救援母檔**，必須保留，但**不代表目前線上題庫總數**，也不可直接覆寫 production。

原始五科各 920 題：

```json
{
  "社會工作研究方法": 920,
  "人類行為與社會環境": 920,
  "社會工作": 920,
  "社會工作直接服務": 920,
  "社會政策與社會立法": 920
}
```

## 重要檔案

- `PROJECT_HANDOFF.md`：目前最重要 source of truth／續聊入口
- `ADMIN_MONITORING_PLAN.md`：管理後台、使用者回報、監測、安全與外部 uptime roadmap
- `PRELAUNCH_QA.md`：公開前 P0/P1 驗收清單
- `MONTHLY_PATCH_PLAN.md`：月底學生端施工順序
- `CDN_FRONTEND_MIGRATION_DESIGN.md`：前端切 CDN shard 的低風險設計
- `FRONTEND_MONTHLY_AUDIT.md`：多答案／grading mode／override audit
- `FRONTEND_XSS_AUDIT.md`：stored XSS audit
- `FRONTEND_SCOPE_AUDIT.md`：指定歷屆／round canonical audit
- `audit/historical_answer_audit.md`：官方答案與 grading mode audit
- `index.html`：網站主程式
- `essay_guides.js`：申論資料
- `supabase/functions/`：Edge Functions source
- `supabase/migrations/`：production schema/recovery source
- `cloudflare/wandering-wave-4418/worker.js`：AI proxy / quota Worker
- `scripts/build_question_shards.py`：題庫 shard builder

## 安全與部署提醒

1. `data/questions_master_backup_20260824_2220.csv` 是救援母檔，不直接覆寫 production。
2. Netlify 只發布 `_site`；私人 CSV、migration、incoming 與後端程式不能跟著公開。
3. Supabase anon key 可存在前端，但 service-role key、Groq key、internal key 絕不能寫進 GitHub 或網站。
4. 學生端對 `questions`／`essays` 僅有 SELECT 權限；更新由後台自動化／Supabase 管理端處理。
5. AI 暫時不可用時，刷題、錯題與非 AI 申論功能仍必須正常運作。
6. 不要把 Cloudflare Rate Limiter 當精準每日 quota；每日 quota 由 D1 精確記帳。
7. 不要把 `all_credit` 與 `any_answer` 混為同一種「一律給分」。
8. GitHub commit history 是版本歷史；遇到錯誤優先回復既有版本，不直接刪除資料。

下一個對話／AI 工作階段：**先從本 README 最上方「AI / 新工作階段：請先看這裡」開始，再讀 `PROJECT_HANDOFF.md`。**