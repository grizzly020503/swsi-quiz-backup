# SWSI 社工師國考平台 — 專案交接／續聊清單

最後更新：2026-08-25 17:46（公開前 QA：官方答案 4,800/4,800、法規 mapping、MOEX 更正答案、防濫用與 production source 對齊）

> 下一個 ChatGPT 對話先讀本檔，再接著做：
>
> **「請先讀 GitHub 私人 repo `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，再依『現在真正的下一步』繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。」**

---

## 0. 平台核心初衷（最重要）

SWSI 的成立原因是：社工師國考準備已經很困難，網路上很多題庫、解析、練習平台又被訂閱制／付費牆鎖住。

平台要做成：

- **免費**
- **公開**
- **低門檻**
- **真的能幫考生準備社工師國考**

核心功能不應被 paywall 鎖住。理想上學生不用註冊即可開始刷題。AI 是輔助功能，不應讓 API 成本拖垮整個免費平台。

產品決策北極星：

> **「這個改動，有沒有讓考生更容易免費準備社工師國考？」**

---

## 1. 專案位置

### GitHub
- 私人 repo：`grizzly020503/swsi-quiz-backup`
- `main` 為目前 source of truth
- 重要交接：`PROJECT_HANDOFF.md`
- 公開前 QA：`PRELAUNCH_QA.md`
- 月更施工圖：`MONTHLY_PATCH_PLAN.md`
- 歷屆答案 audit：`audit/historical_answer_audit.md`

### Netlify
- 正式站：`https://swsi-quiznetlify.netlify.app`
- **使用者明確決定：學生端每月集中更新，不要現在一直部署前端。**
- 現在後端／GitHub 可以修；`index.html / sw.js / manifest.json` 等學生端仍留到月底同一包。

### Supabase
- project：`Swsi`
- project id：`yumjtrdctaxyczpspuyo`
- region：`ap-southeast-1`

### Cloudflare Worker
- Worker：`wandering-wave-4418`
- URL：`https://wandering-wave-4418.c022050333.workers.dev`
- GitHub 程式：`cloudflare/wandering-wave-4418/worker.js`
- Wrangler：`wrangler.jsonc`

### Cloudflare D1
- database：`swsi-ai-quota`
- binding：`AI_QUOTA_DB`
- tables：`ai_daily_client_usage`、`ai_daily_global_usage`

---

## 2. 目前學生端核心功能

核心不是功能數量，而是這條學習循環：

> 做題 → 發現不會 → 看考點／解析 → 錯題 → 1/3/7/14/30 間隔複習 → 弱點 → 申論 → AI 回饋

已有：

- 智慧刷題／指定歷屆刷題
- 最近 10 年題庫與歷史題庫
- 錯題本
- 1→3→7→14→30 天間隔複習
- 模擬考
- 弱點分析／進度
- 申論拆題／骨架
- 申論草稿本機儲存／TXT 匯出
- 申論 AI 文字批改
- 手寫照片 AI 辨識＋批改
- 申論時事雷達
- 法規異動監測
- PWA／Service Worker／IndexedDB 離線備援

---

## 3. 題庫與官方答案狀態

### Supabase 選擇題
- 總數：**4,800 題**
- 5 科 × 960 題
- ROC 104–115、每年 2 次、每科 40 題
- 無空白題幹、缺選項、非法答案、同考次同科重複題號

### 2026-08-25 歷屆官方答案最終稽核

Historical MOEX Answer Audit 已改成讀取 `accepted_answers`，逐題核對 24 個考次／4,800 題：

- 官方考次：**24**
- 官方題數：**4,800**
- Supabase 題數：**4,800**
- 非完全一致：**0**

結論：

> **Supabase 官方答案集合目前 4,800 / 4,800 與考選部最終答案一致。**

不要再把「答案資料庫可能大量錯誤」當目前問題。

### 官方多答案
- `accepted_answers` 已加入 `questions`
- 正式多答案題：**24 題**
- DB constraint：accepted answers 僅 A/B/C/D，主 `answer` 必須包含於集合
- 24 題目前故意 `analysis_status='review'`
- 原因：**前端尚未支援 accepted_answers 判題**
- 這是月底 Netlify patch 的 P0，不是 DB 答案錯

### 一律給分
- 共 **16 題**
- 目前故意 `analysis_status='review'`
- 原因：analyzer 尚未明確建模「A-D 都計分，但不代表四個選項在學理上都正確」
- 學生端既有 `answer='一律給分'` 判定仍可正常處理送分

### 最新考試
- 115 年第 2 次：200 選擇題＋10 申論題
- 10 題申論結構正確、5 科各 2 題、各 20 分
- `E-115-2-R-1` 題目仍有 PDF 私用字元 `  `，留到月底前端／auto payload 同包清理，避免單獨觸發 Netlify

### 歷屆申論
- 約 230 題骨架
- 49 組考點叢集
- 35 個理論
- 18 部法規

---

## 4. 考選部同步／答案更正

### MOEX 自動同步
狀態：**正常**。

流程：

> 考選部 → GitHub Actions → parser / health check → Supabase → AI 解析 → 前端

`moex_sync.py` 已補正式答案更正邏輯：

- 先嘗試 `t=M` 更正答案
- 沒有 M 才退回 `t=S` 標準答案
- 支援單一更正
- 支援一律給分
- 支援多答案 → 寫入 `accepted_answers`
- M 格式無法安全解析 → **fail closed，不碰 Supabase**

2026-08-25 workflow 實測：
- 115030 五科：S、multi=0
- 115100 五科：S、multi=0
- `incoming/115030.json`、`incoming/115100.json` 官方內容 unchanged
- Supabase remote health：questions=4800、essays=10

Supabase importer：
- `import-moex-social-worker`
- production **version 3 / ACTIVE**
- 會驗證 `accepted_answers`
- GitHub source 已對齊 production v3

---

## 5. 法規監測

狀態：**正常，且 mapping 已補強。**

### Official watch
- 逐條查 `law.moj.gov.tw`
- 最近 workflow：**52/52 found、0 missing、0 changed**

### Mapping
以前主要只看 AI `law` 欄位，最新 pending 題可能漏掛法規。

現在 canonical mapping 改成：

> **官方題幹 + A/B/C/D 四選項 + AI law**

結果：
- 4,800 題已全部 backfill
- 約 **647 題**掛有正式法規 mapping
- 題面直接出現 52 部監測法規名稱但未掛 mapping：**0**

Trigger：`questions_sync_legal_canonical_names`

### 真正法規異動
`sync-legal-watch` production **version 2 / ACTIVE**：
- 真偵測到修法 → `legal_status='changed'`
- 建立 `legal_watch_hits`
- 不修改考選部官方題目／答案
- GitHub source 已對齊 production v2

---

## 6. AI 題解 queue／品質

### Queue
- 約每 30 分鐘
- 24 小時最多完成 25 題
- `claim_pending_ai_questions()` 已改為：

> `source_exam_code → qno → subject → id`

所以最新考次會跨五科較平均消化，不再一科做完才換下一科。

### Edge Function
- `analyze-pending-questions`
- production **version 7 / ACTIVE**
- 會用既有 `job_key` 作內部 Cloudflare 驗證
- 已支援 `accepted_answers` 多答案 prompt
- GitHub source 已對齊 production v7

### AI 解析安全／品質
早期 legacy 解析曾殘留：
- 「題庫答案標錯」
- 「官方答案有瑕疵」
- 「答案待查」
- 「建議查官方答案」

2026-08-25 已：
- 清掉非送分 legacy meta 解析並重新排 queue
- 16 一律給分題隔離 review
- 新增 DB trigger `trg_reject_ai_answer_meta_commentary`
- `ready` 狀態若含這類答案 meta/editorial 話術 → DB 直接拒絕
- 驗收：`ready` 中 meta 污染 **0**

最近 QA 快照（數字會隨排程變動）：
- ready：**4512**
- pending：**248**
- review：**40**
- analyzing：**0**

40 review 的組成：
- 24 官方多答案
- 16 一律給分

這是刻意隔離，不是 queue 故障。

### pg_net
- AI 雙階段解析 timeout 已由 5 秒改為 **30 秒**
- 已實測 Edge Function 可成功完成 pending → ready

---

## 7. Supabase 公開安全

`questions` / `essays`：
- anon：SELECT only
- authenticated：SELECT only
- 公開 INSERT / UPDATE / DELETE / TRUNCATE 已移除

RLS：
- questions：公開 SELECT policy
- essays：公開 SELECT policy
- 原 permissive authenticated ALL 已刪
- 原假的 `only admin can write = true` 已刪

敏感 SECURITY DEFINER helper：PUBLIC / anon / authenticated EXECUTE 已撤銷，只保留必要內部權限。

### Production migration 備援
2026-08-25 production 比 GitHub migration 目錄多出的 QA 變更，已整理成：

`supabase/migrations/20260825094110_production_qa_consolidation.sql`

此檔是 **recovery/source-of-truth consolidation**，不是叫下一個對話再套一次 production。

涵蓋：
- queue 公平排序
- accepted_answers 欄位／constraint／trigger
- 24 題多答案資料
- accepted_answers 變更重置 AI
- 法規 mapping 題幹＋選項
- 一律給分隔離
- AI answer-meta DB 品質閥門

---

## 8. Cloudflare AI Proxy / D1

### Origin / request guard
正式 Worker：
- 只允許 `https://swsi-quiznetlify.netlify.app`
- 無 Origin → 403
- 假 Origin → 403
- CORS 不再 `*`
- POST / OPTIONS only
- request 約 4 MB 上限
- 公開照片最多 **3 張**
- 公開 image URL 只接受前端實際產生的 JPEG data URL
- messages 格式驗證
- 公開模型固定 `qwen/qwen3.6-27b`
- internal backend 可用 Qwen + GPT-OSS
- Groq 錯誤不直接洩漏內部細節

最新 Worker commit：`0a952a3`
Cloudflare Git integration：**production build success**
Version ID：`a84f3bab-72b2-4798-908d-0abdf4ec73f5`

注意：目前環境無法直接 POST `workers.dev`，所以這一版「3 張／JPEG 拒絕」有 production build success，但仍缺最後 runtime 行為 smoke test；不要把 build success 說成每條 runtime 規則都已實測。

### Secrets
Cloudflare Runtime Secrets：
- `GROQ_KEY`
- `SWSI_INTERNAL_KEY`

**只記名稱，secret 值永遠不可寫進 GitHub／聊天。**

### Rate Limiter
- `AI_RATE_LIMIT`：namespace 1001，3 / 60 秒
- `AI_IP_LIMIT`：namespace 1002，30 / 60 秒

### D1 quota
`swsi-ai-quota`：
- `ai_daily_client_usage`
- `ai_daily_global_usage`

政策：
- 每 client 文字 AI：約 10 次／日
- 每 client 照片 AI：約 3 次／日
- 全站另有每日總閥門
- invalid request 不扣 quota
- Groq 失敗會 refund
- internal backend 不吃學生 D1 quota

前面已實測正式 SWSI Origin 的文字 AI 會正確增加 D1 client/global usage。

### 尚可優化
Cloudflare 支援 **Build Watch Paths**。目前 repo 的任何 push 都可能讓 Worker 白白 build。

建議 Dashboard include paths：
- `cloudflare/**`
- `wrangler.jsonc`
- 未來若題庫 CDN 靜態資料放 repo，再加對應 `data/**`

不要為 README／audit／Supabase migration 改動重建 Worker。

---

## 9. 公開前真正 P0／月底 Netlify patch

### P0-1：Cloudflare 題庫 CDN / shard
目前學生端仍會直接從 Supabase 拉整套題庫，公開大流量會讓 egress 與冷啟動成本不必要地放大。

已規劃：
- 將題庫做成靜態 shard（之前規劃 24 shard）
- Cloudflare CDN 快取
- Supabase 留作後台 source of truth
- 前端讀 CDN，而不是每位學生都打 Supabase 下載整包

這是目前**公開大量使用前最大的基礎設施 P0**。

### P0-2：多答案前端
前端判題／錯題／模擬考／解析 UI 都需理解 `accepted_answers`。

規則：
- 有 `accepted_answers` → 使用集合判定
- 無 → 沿用 `answer`
- 一律給分仍為全部給分

### P0-3：stored XSS escape
`renderQuiz()` 等動態資料進 `innerHTML` 前統一 escape。

### P0-4：匿名 `X-SWSI-Client-ID`
目前 Worker 支援但舊 Netlify 前端尚未送，仍 fallback IP+UA。

### 其他月底 patch
- 模擬考未作答也進錯題／各科分母
- AI 429/每日額度顯示 Worker 真實友善訊息
- 搜尋理論／法規 deep-link 自動展開
- localStorage 寫入失敗提示
- 申論 AI 過度承諾文案收斂
- 照片隱私說明
- 前端照片明確最多 3 張
- `E-115-2-R-1` 私用字元改成正常 `(一)(二)(三)` 或可跨字型符號
- 首頁第一屏標明「免費社工師國考學習平台」
- SEO / OG
- 無障礙 keyboard / aria
- Service Worker cache version bump

詳細施工圖：`MONTHLY_PATCH_PLAN.md`

---

## 10. 不要重做／不要誤判

- **不要改 Netlify，除非使用者明確要求或到約定月更施工。**
- 不要再把專案當資料救援階段。
- 不要重新查「4,800 題是不是大量答案錯」；official audit 已是 0 mismatch。
- 不要把 24 多答案 review 當錯題；DB 已正確，等前端。
- 不要把 16 一律給分 review 當 AI 故障；是刻意隔離。
- 不要重建 D1／usage tables／rate limit bindings。
- 不要把 Rate Limiter 當精準每日 quota。
- 不要再開 authenticated 題庫寫入。
- 不要把 Supabase anon key 當 secret。
- 不要把 Groq key / internal key 寫進 GitHub。
- 不要讓 AI 修改考選部官方題幹／選項／答案。
- 不要拿 GitHub 舊版 Edge Function 覆蓋 production；目前三支主要 source 已重新對齊 production。
- 前台做減法，後台自動化。

---

## 11. 每次重大修改後必做

更新：`PROJECT_HANDOFF.md`

至少記：
- 已完成事項
- 現在卡點
- 下一步
- function / migration / binding 名稱
- 測試結果
- 只記非秘密設定

---

## 12. 下一個對話最短啟動指令

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「公開前真正 P0／月底 Netlify patch」繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。**
