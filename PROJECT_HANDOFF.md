# SWSI 社工師國考平台 — 專案交接／續聊清單

最後更新：2026-08-25（Cloudflare AI 防濫用 + D1 每日配額 + Supabase 後台相容性已驗收）

> 下一個 ChatGPT 對話先讀本檔，再接著做：
>
> **「請先讀 GitHub 私人 repo `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，再接著目前進度做，不要重新猜架構，也不要重做已完成項目。」**

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
- `main` 為目前最新 source of truth

### Netlify
- 正式站：`https://swsi-quiznetlify.netlify.app`
- 使用者明確決定：**Netlify 每月集中更新，不要現在一直部署前端**

### Supabase
- project：`Swsi`
- project id：`yumjtrdctaxyczpspuyo`
- region：`ap-southeast-1`

### Cloudflare Worker
- Worker：`wandering-wave-4418`
- URL：`https://wandering-wave-4418.c022050333.workers.dev`
- GitHub 程式：`cloudflare/wandering-wave-4418/worker.js`
- Wrangler 設定：`wrangler.jsonc`

### Cloudflare D1
- database：`swsi-ai-quota`
- binding：`AI_QUOTA_DB`

---

## 2. 目前學生端核心功能

產品核心：

1. 刷選擇題
2. 錯題複習
3. 申論練習

學習循環：

> 做題 → 發現不會 → 看考點／解析 → 錯題 → 1/3/7/14/30 間隔複習 → 弱點 → 申論 → AI 回饋

重要功能：

- 智慧刷題
- 指定歷屆刷題
- 最近 10 年主題庫／更早歷史題庫
- 錯題本
- 1→3→7→14→30 天間隔複習
- 模擬考
- 弱點分析／進度
- 申論拆題五步／骨架
- 申論草稿本機儲存／TXT 匯出
- 申論 AI 文字批改
- 手寫照片 AI 辨識＋批改
- 申論時事雷達
- 法規異動監測
- PWA／Service Worker／IndexedDB 離線備援

---

## 3. 題庫狀態

### Supabase 選擇題
- 總數：**4,800 題**
- 5 科 × 960 題
- ROC 104–115、每年 2 次、每科 40 題
- 已驗證無空白題幹、缺選項、非法答案、同科同考次重複題號

### 最新考試
- 115 年第 2 次：200 選擇題＋10 申論題

### 歷屆申論
- 約 230 題／份骨架
- 49 組考點叢集
- 35 個理論
- 18 部法規

---

## 4. 自動監測／同步

### 考選部新題同步
狀態：**正常**

流程：考選部 → GitHub Actions → parser / health check → Supabase → AI 解析 → 前端。

### 申論時事雷達
狀態：**正常**。同主題會聚合，所以 DB 筆數可能多於公開卡片數。

### 法規異動監測
狀態：**正常**。
- 已改成逐條查 `law.moj.gov.tw`
- 最近驗證：52/52 法規找到、0 missing

### AI 新題解析排程
狀態：**正常**。
- 約每 30 分鐘跑
- 24 小時最多完成 25 題
- 2026-08-25 最終測試時已達 25/25
- 快照：ready 4625、pending 175、review 0（數字會變，下一個對話應重新查）

Supabase Edge Function：
- `analyze-pending-questions`
- 2026-08-25 已升級到 **version 6 / ACTIVE**
- 會用既有 `job_key` 作內部驗證呼叫 Cloudflare Worker

pg_net：
- 原本預設 timeout 5000ms，AI 雙階段解析會超時
- 已改成 **30000ms**
- 並同步修改重新啟用排程的函式，避免未來退回 5 秒

實測：
- request 44 → HTTP 200、無 timeout
- `HBSE-115-2-025` 成功 pending → ready

---

## 5. Supabase 公開安全狀態

`questions` / `essays`：
- anon：SELECT only
- authenticated：SELECT only
- 公開 INSERT / UPDATE / DELETE / TRUNCATE 已移除

RLS：
- questions：單一公開 SELECT policy
- essays：單一公開 SELECT policy
- 原 permissive authenticated ALL 已刪
- 原假的 `only admin can write = true` 已刪

PUBLIC 可呼叫的敏感 SECURITY DEFINER helper 已撤銷 public / anon / authenticated EXECUTE，只保留必要內部權限。

---

## 6. Cloudflare AI Proxy 防濫用 — 已完成並驗收

### Origin / request guard
正式 Worker 已做到：
- 只允許 `https://swsi-quiznetlify.netlify.app`
- 無 Origin → 403
- 假 Origin → 403
- 正式 SWSI Origin → 允許
- CORS 不再 `*`
- POST / OPTIONS only
- request 最大約 4 MB
- 最多 4 張圖片
- messages 格式驗證
- 學生端模型固定 `qwen/qwen3.6-27b`
- max_tokens / temperature 有上限
- Groq 錯誤不直接洩漏內部細節

2026-08-25 最終 smoke test：
- no Origin → **403**
- `https://evil.example` → **403**
- 正式 SWSI Origin → **200**，Groq 實際回覆 `OK`

### Secrets
Cloudflare Runtime Secrets 已有：
- `GROQ_KEY`
- `SWSI_INTERNAL_KEY`

**只記名稱，不得把值寫進 GitHub。**

### Rate Limiter
1. `AI_RATE_LIMIT`
   - namespace 1001
   - 3 / 60 秒
   - client key = IP + User-Agent hash

2. `AI_IP_LIMIT`
   - namespace 1002
   - 30 / 60 秒

Cloudflare Rate Limiter 是防暴衝，不是精準每日帳本。

---

## 7. D1 每日精準配額 — 已完成並驗收

D1 database：`swsi-ai-quota`

Tables：

### `ai_daily_client_usage`
欄位用途：
- `usage_date`
- `client_key`（不可逆 hash；不存姓名、Email、原始 IP）
- `text_count`
- `photo_count`
- `updated_at`

### `ai_daily_global_usage`
欄位用途：
- `usage_date`
- `text_count`
- `photo_count`
- `updated_at`

目前政策：
- 每 client 文字 AI：約 **10 次／日**
- 每 client 照片 AI：約 **3 次／日**
- 全站另有每日總閥門
- invalid request 不應消耗 quota
- Groq 失敗會退回已扣 quota
- 後台自動題解走 internal branch，**不吃學生 D1 配額**

### 2026-08-25 最終驗收
正式 SWSI Origin 做 1 次文字 AI 後：

`ai_daily_global_usage`
- usage_date：2026-08-25
- text_count：**1**
- photo_count：**0**

`ai_daily_client_usage`
- 同日出現一筆 hashed client_key
- text_count：**1**
- photo_count：**0**

結論：**D1 每日記帳、client 記帳、正式 SWSI AI 路徑均已實際生效。**

此階段狀態：

> ✅ Cloudflare Origin 防護
> ✅ 每分鐘防暴衝
> ✅ IP 第二層限速
> ✅ D1 每 client 每日額度
> ✅ D1 全站每日額度
> ✅ Groq Key 只在 Cloudflare Secret
> ✅ Supabase 後台 internal key 相容
> ✅ 後台不吃學生 quota
> ✅ pg_net timeout 修正
> ✅ 實際 smoke test 通過

---

## 8. 現在真正的下一步

**AI 防濫用／D1 配額這一階段已結案，不要再從建 D1、建 table、加 binding 開始。**

下一步建議優先順序：

1. **回到產品本身做公開前 UX / QA**
   - 首頁 10 秒內能否知道該做什麼
   - 做題 → 解析 → 錯題 → 複習 → 進度是否順
   - 申論 AI 超額／429 顯示是否友善
   - 行動版實測
2. **做一輪完整公開前 smoke test**
   - 選擇題
   - 錯題本
   - 申論文字
   - 申論照片
   - 時事雷達
   - 法規監測狀態
3. Netlify 仍依使用者決定：**每月集中部署，不要擅自立即更新**
4. 若未來公開到大流量，再評估：
   - Turnstile / challenge
   - 動態全站 AI 總閥門
   - AI usage dashboard
   - 更強 anti-bot / device identification

---

## 9. 不要重做／不要誤判

- 不要再把專案當資料救援階段。
- 不要重建 D1；已完成。
- 不要重建兩張 usage table；已完成。
- 不要再新增 `AI_RATE_LIMIT` / `AI_IP_LIMIT`；已完成。
- 不要把 Rate Limiter 當精準每日 quota。
- 不要再開 authenticated 題庫寫入。
- 不要把 Supabase anon key 當秘密。
- 不要把 Groq key / internal key 寫進 GitHub。
- 不要因 Netlify 還是舊版就回退 GitHub 最新修正。
- 不要讓 AI 改考選部官方題幹／選項／答案。
- 前台做減法，後台自動化。

---

## 10. 每次重大修改後必做

同步更新本檔：`PROJECT_HANDOFF.md`

至少記：
- 已完成事項
- 現在卡點
- 下一步
- 新增 binding / table / function 名稱
- 重要測試結果
- **只記非秘密設定；secret 值永遠不要寫入 repo**

---

## 11. 下一個對話最短啟動指令

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「現在真正的下一步」繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。**
