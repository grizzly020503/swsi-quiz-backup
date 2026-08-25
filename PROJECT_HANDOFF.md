# SWSI 社工師國考平台 — 專案交接／續聊清單

最後更新：2026-08-25（D1 binding 完成後）

> 用途：這份檔案是給「下一個 ChatGPT 對話」接手用的。若換新對話，先叫 ChatGPT：
>
> **「請先讀 GitHub 私人 repo `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，再接著目前進度做，不要重新猜架構。」**

---

## 0. 平台核心初衷（最重要，不可搞錯）

這個平台的成立原因是：

- 社工師國考準備已經很困難。
- 網路上很多刷題／解析／題庫平台被訂閱制、付費牆鎖住。
- 此平台要做成 **免費、公開、低門檻、真的能幫考生準備社工師國考** 的替代方案。
- 核心學習功能不應被 paywall 鎖住。
- 理想上學生不需註冊即可開始刷題。
- AI 是輔助資源，不是讓平台被 API 成本拖垮的無限制功能。

產品決策的北極星：

> **「這個改動，有沒有讓考生更容易免費準備社工師國考？」**

---

## 1. 專案位置

### GitHub
- 私人 repo：`grizzly020503/swsi-quiz-backup`
- **目前 GitHub `main` 是最新真實版本（source of truth）**。

### Supabase
- project id：`yumjtrdctaxyczpspuyo`
- project name：`Swsi`
- region：`ap-southeast-1`

### Netlify
- 正式站：`https://swsi-quiznetlify.netlify.app`
- **重要：使用者決定 Netlify 每月再集中更新一次。**
- 因此 GitHub 最新版可能暫時領先正式 Netlify。
- 不要因為 Netlify 還是舊 UI 就以為 GitHub 修正失敗。

### Cloudflare Worker（申論 AI Proxy）
- Worker：`wandering-wave-4418`
- URL：`https://wandering-wave-4418.c022050333.workers.dev`
- GitHub 安全版備份：`cloudflare/wandering-wave-4418/worker.js`

### Cloudflare D1（AI 每日額度）
- database：`swsi-ai-quota`
- Worker binding：`AI_QUOTA_DB`
- 狀態：**已建立並成功綁定到 `wandering-wave-4418`**
- 目前尚未建每日 usage table。

---

## 2. 目前學生端核心功能

產品核心只有三件事：

1. **刷選擇題**
2. **錯題複習**
3. **申論練習**

主要學習循環：

> 做題 → 發現不會 → 看考點／解析 → 錯題 → 1/3/7/14/30 間隔複習 → 弱點 → 申論 → AI 回饋

重要既有功能：

- 智慧刷題
- 指定歷屆刷題
- 最近 10 年主題庫／更早歷史題庫
- 錯題本
- 1→3→7→14→30 天間隔複習
- 模擬考
- 弱點分析／進度
- 申論拆題五步
- 申論骨架
- 申論草稿本機儲存／TXT 匯出
- 申論 AI 文字批改
- 手寫照片 AI 辨識＋批改
- 申論時事雷達
- 法規異動監測
- PWA／Service Worker／IndexedDB 題庫離線備援

---

## 3. 題庫目前狀態

### 正式 Supabase 選擇題
- 總數：**4,800 題**
- 5 科 × 960 題
- 年度約 ROC 104–115
- 每年 2 次考試 × 每科 40 題

已驗證過：
- 0 空白題幹
- 0 缺 A/B/C/D
- 0 非法答案
- 0 同科＋年度＋考次＋題號重複

### 最新考試
- 115 年第 2 次：200 選擇題＋10 申論題

### 歷屆申論
- 約 230 題／份骨架
- 49 組考點叢集
- 35 個理論
- 18 部法規

### 申論資料清洗
已依考選部官方原卷修正一批歷史資料：
- 第一批：17 題、19 個欄位（截斷、OCR、解析污染、特殊分數等）
- 後續再補 6 題漏掉官方分數尾碼
- 106-2 人行官方特殊配分 26／24 保留，不自行平均成 25／25
- 官方核對紀錄：`data/essay_official_corrections_20260825.json`
- 永久 `scripts/health_check.py` 已加入申論污染／完整性檢查，避免日後復發

---

## 4. 自動監測／同步功能目前狀態

### A. 考選部新考題同步
狀態：**正常**

流程：

> 考選部 → GitHub Actions → parser／health check → Supabase → AI 解析 → 前端

會檢查：
- 五科
- 題數
- 選項
- 正解
- 重複 ID
- 最新考次 200 選擇＋10 申論

AI 不得改考選部官方題幹／選項／答案。

### B. 申論時事雷達
狀態：**正常**

- Supabase 原始候選數可能大於公開卡片數。
- 原因：同主題會聚合。
- 例如資料庫 6 筆、公開 3 主題，不代表漏資料。

### C. 法規異動監測
狀態：**正常（2026-08-25 修復）**

原問題：
- GitHub Actions 無法穩定連 `sendlaw.moj.gov.tw` bulk XML。

已改：
- 直接逐條查 `law.moj.gov.tw` 官方頁。

最新驗證：
- **52/52 法規全部找到**
- 0 missing
- baseline 全部正常
- 第一次 baseline 沒有 `legal_watch_hits` 是正常的，因為沒有前後版本可比較。

另已校正法規正式名稱：
- 舊錯名：`社會工作師執業登記及繼續教育辦法`
- 正式名稱：`社會工作師接受繼續教育及執業執照更新辦法`
- parser、題目、watchlist 已一起校正，舊名保留 alias 邏輯（若程式有需要）。

### D. AI 新題解析排程
狀態：**正常**

最後人工驗證快照：
- 約 4,621 ready
- 約 179 pending

pending 不是故障：
- 排程約每 30 分鐘跑
- 24 小時有免費額度上限（約 25 題）
- 目的是避免免費 AI 額度被一次燒完

> 注意：ready/pending 數字會持續變動，新的對話應重新查現況，不要死記 4,621/179。

---

## 5. Supabase 公開安全狀態（已修）

### 已完成

`questions`／`essays`：
- anon：SELECT only
- authenticated：SELECT only
- INSERT / UPDATE / DELETE / TRUNCATE：已移除

公開網站寫入正式題庫：**不允許**。

寫入只應由：
- service_role
- Edge Functions
- GitHub Actions
- Supabase 後台

### RLS
- `questions`：單一公開 SELECT policy
- `essays`：單一公開 SELECT policy
- 原本 permissive `authenticated ALL` 已刪
- 原本假的 `only admin can write = true` 已刪

### SECURITY DEFINER / RPC
已撤銷 public / anon / authenticated EXECUTE：
- `auto_enable_ai_for_pending_question()`
- `auto_stop_ai_when_queue_drains()`
- `reset_ai_analysis_on_official_change()`
- 以及內部 trigger/helper 的不必要公開執行權限

`service_role` 保留內部需要的 EXECUTE。

### Supabase security advisor
已消失的重大警告：
- public-callable SECURITY DEFINER
- mutable search_path（已處理的函式）
- permissive authenticated write policies

目前仍看到的主要提示：
- 一些內部表 RLS enabled but no policy：**刻意 server-only，不需為消警告而加 public policy**
- Auth leaked-password protection disabled：學生端登入已移除，目前不是公開阻塞項

---

## 6. 公開前端安全整理（GitHub 最新版已完成）

GitHub 最新 `index.html` 已移除：
- ⚙ 管理入口
- Supabase Auth 管理登入
- Email／密碼登入 UI
- CSV 題庫匯入
- browser-side `upsert`
- PapaParse 管理用途
- `renderAdmin()` 等管理死碼

保留：
- `parseExp()`，因為正常題解載入仍使用。

公開頁已加入：
- 免費公開平台文案
- AI 批改個資提醒：不要輸入／上傳可識別個案資料
- 時事雷達文字改成「此類事件常見的申論思考方向」以避免誤導成逐篇 AI 分析
- 舊 `essays_2.js` 錯誤提示已移除

**注意：Netlify 正式站尚未更新到這批 GitHub 最新版，因使用者決定每月集中部署。**

---

## 7. Cloudflare AI Proxy 防濫用 — 已完成部分

### Worker 原本問題
原本：
- `Access-Control-Allow-Origin: *`
- 任意網站、無 Origin 都能打 Worker
- 幾乎原封不動把 body 轉給 Groq

2026-08-25 已實測：
- 無 Origin 原本可打
- `https://evil.example` 也可打

### 現在已部署的安全版
正式 Worker 已改成：
- allowlist Origin：`https://swsi-quiznetlify.netlify.app`
- 無 Origin → 403
- 外站 Origin → 403
- 正式 SWSI Origin → 通過
- CORS 不再 `*`
- 只允許 POST / OPTIONS
- 指定模型：`qwen/qwen3.6-27b`
- 最大 request 約 4 MB
- 最多 4 張圖片
- messages 格式驗證
- max_tokens 上限 1200
- temperature 上限 0.7
- Groq 內部錯誤不把細節直接洩漏前端

GitHub 備份：
- `cloudflare/wandering-wave-4418/worker.js`

### Cloudflare Rate Limiter bindings
已建立並部署：

1. `AI_RATE_LIMIT`
   - Namespace ID：`1001`
   - Limit：3
   - Period：60 秒
   - Worker 使用 IP + User-Agent hash 當軟 client key

2. `AI_IP_LIMIT`
   - Namespace ID：`1002`
   - Limit：30
   - Period：60 秒
   - 用 IP 作第二層防暴衝

### 實測結果
Origin guard：
- no Origin → **403**
- evil Origin → **403**
- SWSI Origin → 通過來源檢查

Rate limiter：
- Cloudflare 內建 Rate Limiter 是 permissive / eventually consistent，不是精準第 4 次必擋。
- 實測連打 12 個無效請求（都在 Groq 前被拒，不產生 AI 內容）：第 8、11 次出現 **429**。
- 結論：**限速確實有工作，但不能拿來當每日精準配額帳本。**

---

## 8. 【現在正在做的下一步】Cloudflare D1 每日精準額度

這是**下一個對話一定要從這裡接**。

目的：

Rate Limiter 只負責防暴衝；D1 負責精準每日配額。

目前預定政策（可在真正接 Worker 前再調）：

- 文字 AI 批改：每個 client 約 **10 次／日**
- 照片 AI 批改：每個 client 約 **3 次／日**
- 再加「全平台每日 AI 總上限」保護 Groq / Worker 免費額度
- 不要求學生登入
- 超過 AI 額度後，刷題／申論骨架／錯題等免費核心功能仍全部可用

目前已完成：

- [x] Cloudflare 建立 D1 database：`swsi-ai-quota`
- [x] 將 D1 binding 綁到 `wandering-wave-4418`：`AI_QUOTA_DB`

**目前精確卡點／下一步：**

> 進入 Cloudflare D1 `swsi-ai-quota` → Console，建立每日 client usage 與全站 usage table。現在資料庫尚未建 table。

接下來 checklist：

- [ ] 建每日 client usage table
- [ ] 建全站每日 usage table
- [ ] 將 schema 備份到 GitHub
- [ ] Worker 區分 text / photo usage
- [ ] client key 做不可逆 hash，不存原始 IP
- [ ] 精準檢查每 client 當日文字／照片次數
- [ ] 精準檢查全站每日總次數
- [ ] 只有「真正準備送 Groq 的有效請求」才扣額度，不要讓 invalid request 消耗 quota
- [ ] 回傳友善 429／quota exhausted 訊息
- [ ] 做正常／超額／換日測試
- [ ] 將 Worker 最新版備份回 GitHub

未來若正式公開到十幾萬使用者，再評估：
- [ ] Turnstile / challenge
- [ ] 更精細裝置識別與 anti-bot
- [ ] 動態每日總閥門
- [ ] AI 使用量 dashboard

---

## 9. Netlify 發布策略（使用者明確決定）

**不要現在強迫即時部署 Netlify。**

使用者明確說：
- Netlify 每月更新再改。

所以目前正確做法：
- GitHub 持續當最新版
- Supabase / Cloudflare 後端安全可即時修
- Netlify 學生 UI 集中月更

正式月更時應檢查：
- [ ] `_site` build
- [ ] index.html 新版
- [ ] sw.js cache version
- [ ] manifest/icons
- [ ] auto/questions_auto.json
- [ ] auto/essays_auto.json
- [ ] auto/current_affairs.json
- [ ] 正式站 smoke test
- [ ] iPhone PWA cache 更新

---

## 10. 不要重做／不要誤判的事情

- 不要再把專案當「資料救援階段」；現在已進入公開前 QA / 安全 / 成本控制。
- 不要再開公開 authenticated 題庫寫入。
- 不要把 Supabase anon key 當秘密；真正秘密是 service-role / Groq key / backend secrets。
- 不要為了消 Supabase `RLS enabled no policy` INFO 而給 server-only table 加 public policy。
- 不要因 Netlify 還是舊版就把 GitHub 最新修正回退。
- 不要把 Cloudflare Rate Limiter 當精準每日 quota。
- 不要讓 AI 自動修改考選部官方題目／答案。
- 不要一直加新主入口；前台做減法，後台自動化。

---

## 11. 每次重大修改後必做

新對話／未來 ChatGPT 完成重大修改後，請**同步更新本檔**：

`PROJECT_HANDOFF.md`

至少更新：
- 最後更新時間
- 已完成事項
- 現在卡點
- 下一步 checklist
- 新增的 binding / table / function 名稱
- 重要測試結果
- 不要遺失的設定值（只記非秘密設定；API key / secret 絕對不要寫進 GitHub）

---

## 12. 下一個 ChatGPT 對話的最短啟動指令

直接貼這句即可：

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「現在正在做的下一步」繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。**