# 社工師國考免費學習平台（SWSI）

重建日期：2026-08-24  
文件更新：2026-08-27

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

下一個對話先讀 `PROJECT_HANDOFF.md`，再依「目前真正的下一步」繼續；不要重新猜架構，也不要重做已完成的後端。