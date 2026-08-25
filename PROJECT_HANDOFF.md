# SWSI 社工師國考平台 — 專案交接／續聊清單

最後更新：2026-08-25（Cloudflare 題庫 CDN、AI 公開照片 guard runtime 驗收完成；前端月底施工稽核完成）

> 下一個 ChatGPT 對話先讀本檔，再接著做：
>
> **「請先讀 GitHub 私人 repo `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，再依『現在真正的下一步』繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。」**

---

## 0. 平台核心初衷

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

## 1. 專案位置／source of truth

### GitHub
- 私人 repo：`grizzly020503/swsi-quiz-backup`
- `main` = source of truth
- 本交接：`PROJECT_HANDOFF.md`
- 公開前 QA：`PRELAUNCH_QA.md`
- 月更施工圖：`MONTHLY_PATCH_PLAN.md`
- CDN 前端施工設計：`CDN_FRONTEND_MIGRATION_DESIGN.md`
- 前端判題／override audit：`FRONTEND_MONTHLY_AUDIT.md`
- Stored XSS audit：`FRONTEND_XSS_AUDIT.md`
- 指定歷屆 scope audit：`FRONTEND_SCOPE_AUDIT.md`
- 歷屆答案 audit：`audit/historical_answer_audit.md`

### Netlify
- 正式站：`https://swsi-quiznetlify.netlify.app`
- **學生端採每月集中更新，不要現在一直部署前端。**
- `index.html / sw.js / manifest.json / essay_guides.js / auto/...` 等學生端檔案留到月底同一包。
- `netlify.toml` 已設定只有真正學生端檔案變動才觸發 production deploy；純 audit／workflow／migration／後端檔案不會因此部署學生端。

### Supabase
- project：`Swsi`
- project id：`yumjtrdctaxyczpspuyo`
- region：`ap-southeast-1`

### Cloudflare Worker
- Worker：`wandering-wave-4418`
- URL：`https://wandering-wave-4418.c022050333.workers.dev`
- GitHub source：`cloudflare/wandering-wave-4418/worker.js`
- Wrangler：`wrangler.jsonc`
- Static Assets root：`cdn/`
- 題庫 CDN：`/question-shards/*.json`

### Cloudflare D1
- database：`swsi-ai-quota`
- binding：`AI_QUOTA_DB`
- tables：`ai_daily_client_usage`、`ai_daily_global_usage`

---

## 2. 學生端核心學習循環

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

## 3. 題庫／官方答案：已完成，不要重查

### Supabase 選擇題
- 總數：**4,800 題**
- 5 科 × 960 題
- ROC 104–115、每年 2 次、每科 40 題
- 無空白題幹、缺選項、非法答案、同考次同科重複題號

### Historical MOEX Answer Audit
已逐題核對 24 個考次／4,800 題，並正確讀取 `accepted_answers`：

- 官方考次：24
- 官方題數：4,800
- Supabase 題數：4,800
- 非完全一致：**0**

結論：

> **Supabase 官方答案集合 4,800 / 4,800 與考選部最終答案一致。**

不要再把「答案資料庫可能大量錯誤」當目前問題。

### 官方多答案
- `questions.accepted_answers` 已完成
- 正式多答案題：**24 題**
- DB constraint 已限制 A/B/C/D 且主 `answer` 必須包含於集合
- 24 題目前故意 `analysis_status='review'`
- 原因：**學生端尚未支援 accepted_answers 判題**
- 這是月底前端 P0，不是 DB 錯誤

### 一律給分
- 共 **16 題**
- 故意隔離 `analysis_status='review'`
- 原因：不能把「A-D 都計分」誤解成「四個選項學理上都正確」
- 現行學生端送分判定可運作；月底 UI 要保留正確語意

### 最新考試
- 115 年第 2 次：200 選擇題＋10 申論題
- 10 題申論結構正確、5 科各 2 題、各 20 分
- `E-115-2-R-1` 還有 PDF 私用字元 `  `，月底同包改成穩定 `(一)(二)(三)` 等字元

### 歷屆申論
- 約 230 題骨架
- 49 組考點叢集
- 35 個理論
- 18 部法規

---

## 4. 考選部同步：正常

流程：

> 考選部 → GitHub Actions → parser / health check → Supabase → AI 解析 → 前端

`moex_sync.py` 已：
- 先嘗試 `t=M` 更正答案
- 沒有 M 才退回 `t=S`
- 支援單一更正
- 支援一律給分
- 支援多答案 → `accepted_answers`
- M 格式不能安全解析 → **fail closed，不碰 Supabase**

115030／115100 workflow 已實測正常。

Supabase importer：
- `import-moex-social-worker`
- production **version 3 / ACTIVE**
- 會驗證 `accepted_answers`
- GitHub source 已對齊 production v3

---

## 5. 法規監測：正常

### Official watch
- 逐條查 `law.moj.gov.tw`
- 最近 workflow：**52/52 found、0 missing、0 changed**

### Mapping
canonical mapping 已改為：

> **官方題幹 + A/B/C/D 四選項 + AI law**

目前：
- 4,800 題已 backfill
- 約 646 題掛正式法規 mapping（數字可能隨 legacy AI `law` 清理略變）
- 題面直接出現 52 部監測法規名稱但未掛 mapping：**0**

Trigger：`questions_sync_legal_canonical_names`

`sync-legal-watch`：
- production **version 2 / ACTIVE**
- 真修法 → `legal_status='changed'` + `legal_watch_hits`
- 不修改官方題目／答案
- GitHub source 已對齊 production v2

---

## 6. AI 題解 queue／品質：正常

### Queue
- 約每 30 分鐘
- 24 小時最多完成 25 題
- `claim_pending_ai_questions()` 排序：

> `source_exam_code → qno → subject → id`

最新考次會跨五科較平均消化。

### Edge Function
- `analyze-pending-questions`
- production **version 7 / ACTIVE**
- 既有 `job_key` 驗證
- 支援 `accepted_answers` prompt
- GitHub source 已對齊 production v7

### 品質閥門
已完成：
- 清掉非送分 legacy 答案 meta 評論並重排 queue
- 16 一律給分隔離 review
- 24 多答案隔離 review
- DB trigger：`trg_reject_ai_answer_meta_commentary`
- `ready` 含「題庫答案標錯／官方答案有瑕疵／答案待查／建議查答案」等 meta 話術會被 DB 拒絕
- `ready` meta 污染驗收：**0**

最近 QA 快照（會隨排程變動）：
- ready：約 4512
- pending：約 248
- review：40（24 多答案 + 16 一律給分）
- analyzing：0

### pg_net
- 雙階段解析 timeout：5 秒 → **30 秒**
- 已實測 pending → ready 可成功完成

---

## 7. Supabase 公開安全：已收斂

`questions` / `essays`：
- anon：SELECT only
- authenticated：SELECT only
- 公開 INSERT / UPDATE / DELETE / TRUNCATE 已移除

RLS：
- questions：公開 SELECT
- essays：公開 SELECT
- 原 permissive authenticated ALL 已刪
- 原假的 `only admin can write = true` 已刪

敏感 SECURITY DEFINER helper 的 PUBLIC / anon / authenticated EXECUTE 已撤銷，只保留必要內部權限。

Production recovery/source-of-truth migration：

`supabase/migrations/20260825094110_production_qa_consolidation.sql`

這是備援整理，**不是叫下一個對話再套一次 production**。

---

## 8. Cloudflare AI Proxy / D1 / 題庫 CDN

### AI request guard
正式 Worker：
- 公開只允許 `https://swsi-quiznetlify.netlify.app`
- 無 Origin → 403
- 假 Origin → 403
- AI CORS 不使用 `*`
- POST / OPTIONS only
- request 約 4 MB 上限
- 公開照片最多 **3 張**
- 公開 image URL 只接受 `data:image/jpeg;base64,...`
- messages 格式驗證
- 公開模型固定 `qwen/qwen3.6-27b`
- internal backend 可用 Qwen + GPT-OSS
- Groq 錯誤不洩漏內部細節

### 2026-08-25 production runtime smoke（已完成）
GitHub Actions `Publish Question Shards to Repo` 已在正式 production 實際驗證：

- AI no-Origin POST → **403**
- 正式 SWSI Origin + 非 JPEG `data:image/png` → **400**
- error message：`公開照片只接受 JPEG 上傳內容。`
- 正式 SWSI Origin + 4 張 JPEG → **400**
- error message：`最多一次上傳 3 張照片。`
- 兩個公開錯誤回應皆帶正確 `Access-Control-Allow-Origin: https://swsi-quiznetlify.netlify.app`
- invalid image request 在 D1 quota / Groq 之前拒絕

相關 commit：`686f66595e16ecb0349fff5e20947ffa8d0e7687`

`.github/workflows/question-shards-publish.yml` 現在每天 runtime smoke 同時驗：
- manifest
- 115-2 shard
- CDN headers/cache
- AI no-Origin guard
- 非 JPEG guard
- 第 4 張照片 guard

### Secrets
只記名稱：
- `GROQ_KEY`
- `SWSI_INTERNAL_KEY`

**secret 值永遠不可寫進 GitHub／聊天。**

### Rate Limiter
- `AI_RATE_LIMIT`：namespace 1001，3 / 60 秒
- `AI_IP_LIMIT`：namespace 1002，30 / 60 秒

### D1 quota
政策：
- 每 client 文字 AI：約 10 次／日
- 每 client 照片 AI：約 3 次／日
- 全站另有每日總閥門
- invalid request 不扣 quota
- Groq 失敗 refund
- internal backend 不吃學生 D1 quota

### Cloudflare 題庫 Static Assets / CDN — **已完成，不要重做**
正式路徑：
- `/question-shards/manifest.json`
- `/question-shards/104-1.json` … `/question-shards/115-2.json`

production dataset：
- 4,800 題
- 24 shards（每考次 200 題）
- revision：`8dafaf049f5200b54cd8`
- 約 6.84 MB 未壓縮總量
- 單 shard 約 193–301 KB
- 24 多答案完整保留
- 16 一律給分完整保留

Runtime：
- manifest：HTTP 200
- 115-2 shard：HTTP 200／200 題
- `CF-Cache-Status: HIT`
- `Access-Control-Allow-Origin: *`
- `Cache-Control: public, max-age=300, must-revalidate`
- `X-Content-Type-Options: nosniff`

自動化：
- `scripts/build_question_shards.py`
- `.github/workflows/question-shards-build.yml`
- `.github/workflows/question-shards-publish.yml`
- 每天台灣時間約 11:10
- dataset/header 不變 → 不 commit
- dataset 變 → 更新 `cdn/question-shards/` → Cloudflare Git deploy → runtime smoke
- incomplete 新考次 → fail closed
- 完整 116、117…考次會自動新增 shard
- 模擬 116-1 已成功：5,000 題 / 25 shards

不要另開 R2，不要另建第三個 Worker。

---

## 9. 最新前端 code audit：非常重要

**目前所有以下內容都只是 audit／施工設計；尚未改 `index.html`、尚未部署 Netlify。**

### 9.1 `index.html` 是「原始函式 + 後置 override」
檔案底部 `swsi-uiux-v1-script` 會再次覆寫：
- `renderHome=function(){...}`
- `renderReview=function(){...}`
- `applyFocusedTabbar` 被 wrapper

另外時事雷達會 hook：
- `NL.open`
- `NL.filter`

因此月底不能只修前半段原始函式。

目前底部 `renderHome()` 仍：
- 用 `ALL.length` 顯示題數
- 直接 `onclick="MK.open()"`
- 自訂指定歷屆有 round value regression（見下一節）

目前底部 `renderReview()` 仍：

```js
ids.map(id => ALL.find(q => q.id===id)).filter(Boolean)
```

CDN partial-bank 後若不加 full-bank gate，舊錯題可能暫時消失。

### 9.2 已確認現行 bug：指定歷屆 round value regression
核心 `focusedQuizFilter()` 預期：

```text
homeQuizRound = "1" / "2" / "all"
```

但底部 UIUX V1 override 的 `<option>` value 改成：

```text
"第一次" / "第二次"
```

所以：

```text
canonicalRound(q.round) === "1"
homeQuizRound === "第一次"
```

永遠不相等。

使用者影響：

> 自訂範圍 → 指定歷屆 → 選某年份 → 第一次／第二次

可能得到「這個條件目前沒有題目」。

這是 **UI override regression**，不是 DB／CDN 缺題。

月底第一刀：
- 內部 round 一律 `"1" / "2" / "all"`
- UI label 才顯示第一次／第二次
- `setHomeQuizRound()` 再 canonicalize 做防呆
- CDN shard matcher 也用同一 canonicalRound

### 9.3 `normalize()` 尚未帶 `accepted_answers`
現行 normalized question object 只有單一 `answer`。

月底必補：

```js
accepted_answers: Array.isArray(r.accepted_answers)
  ? r.accepted_answers.filter(x=>['A','B','C','D'].includes(x))
  : null
```

不要在前端自己猜多答案。

### 9.4 判題邏輯要收斂成 item-based helper
現行：

```js
ansCorrect(p,a)
```

只懂單答案。

月底統一：

```js
acceptedAnswers(item)
isCorrectAnswer(item,picked)
answerLabel(item)
```

所有入口都走同一套：
- 一般刷題 option class
- 一般刷題 submit
- history
- review schedule
- weak topics
- 正確率
- `MK.grade()`
- 模擬考結果頁

不要只修 `ansCorrect()`，因為 `MK.grade()` 現在有自己的第二套判定。

### 9.5 模擬考未作答 bug
現行 `MK.grade()`：
- 未作答會進 `wrong[]`
- 但 `record()` / `bySubj` 只在 `picked != null` 執行

月底同一輪處理：
- 未作答 = incorrect
- 進各科分母
- 進 history / review schedule
- UI 仍顯示「未作答」

### 9.6 Stored XSS
不能只做「全域 esc() 多補兩個 replace」就算完成。

P0 需處理：
- question
- opt A-D
- exp why/others/trap/raw
- mnemonic
- law
- topic / major / mistake
- subject/year/round meta
- summary weak topics
- topics/progress/review 中由 DB/localStorage 聚合的字串
- source URL scheme allowlist
- 不可信字串不要直接進 inline JS attribute

原則：
- 純文字 → `escText()`
- 換行 → escape 後再 `<br>`
- URL → 預設只允許 `https:`
- 動態 onclick 優先改 index/stable id 或 DOM listener

### 9.7 Search deep-link
現行：

```js
openTheory(name){ theoryQ=name; theoryOpen=name; ... }
openLawCard(name){ lawQ=name; lawOpen=name; ... }
```

但 render 端以 `THEORIES.indexOf(t)` / `LAWS.indexOf(l)` 的數字 index 判 `open`，所以 name 不會命中。

月底要 name → index，不能直接把 name 塞進 index state。

### 9.8 照片 AI 前端仍允許 4 張
現行 `gradePhoto()`：

```js
if(files.length>4){ files=files.slice(0,4); }
```

而 Worker production 已明確最多 3 張。

月底：
- `files.length > 3` → 直接提示「一次最多 3 張」
- 不要默默截掉第 4 張

### 9.9 AI client ID / 真實錯誤訊息
Worker 已支援 `X-SWSI-Client-ID`，舊學生端尚未送。

月底：
- localStorage UUID helper
- 文字／照片 fetch 都送 `X-SWSI-Client-ID`
- 非 2xx 優先讀 Worker JSON `error.message`
- daily quota 不顯示「立即重試」
- 413／502／503 分別友善處理

---

## 10. CDN 前端切換設計：已完成，月底只實作

推薦架構：

> **Manifest-first + Scope-on-demand + `ALL` 相容橋**

不是把 Supabase URL 直接換成 CDN URL。

### 開站

```text
Cloudflare manifest
  → validate
  → IndexedDB 存 manifest
  → 立即 render 首頁
```

首頁不再等 4,800 題。

### Shard loader 優先序

```text
1. memory
2. Cloudflare shard
3. IndexedDB shard
4. Supabase scoped fallback
5. 明確錯誤
```

### Scope
- specific + round → 1 shard
- specific + all rounds → 2 shards
- recent3 → 6 shards
- recent5 → 10 shards
- smart → 最近 10 年所需 shards
- all → 全 shards

### 第一版主動進功能時可 full-bank gate
為降低公開前風險，以下可以先 `ensureAllQuestionsLoaded()`：
- search
- topics
- review
- progress（若依賴 ALL）
- `MK.open()`
- `startDueReview()`

### `reviewSummary()` partial-bank 注意
若 `QB.allComplete === false`，不能拿部分 `ALL` 去判舊錯題「不存在」。

### `auto/questions_auto.json`
正常 CDN 路徑不要再無條件 merge auto MCQ；CDN 已直接從 production Supabase build。

`auto/essays_auto.json` 與選擇題 loader 無關，可維持。

### IndexedDB
現有：
- DB：`swsi-quiz-offline`
- version：1
- store：`cache`
- legacy key：`questions`

第一版不必為 shard cache 重建 DB 架構；可沿用同 store 新增 key。

### Service Worker
現行 `sw.js`：`VERSION='v4'`

Cloudflare shard 是跨 Netlify origin，現行 SW 不攔它是正確的；離線題庫由 IndexedDB 處理。

月底學生端改完後 bump VERSION，**不要把跨域 Cloudflare shards 硬塞進 shell cache**。

---

## 11. 月底 Netlify patch — 真正施工順序

**目前不要執行，除非使用者明確說要開始學生端月更。**

建議順序：

1. 備份當下 `index.html / sw.js / manifest.json` SHA
2. **先修 round canonical regression**
3. 補 `normalize().accepted_answers`
4. 建立統一 `acceptedAnswers / isCorrectAnswer / answerLabel`
5. 同輪改一般刷題 + `MK.grade()` + 模擬考未作答
6. 加 CDN manifest/shard loader + scope gate + full-bank gate
7. 修 `renderHome` / `renderReview` 最後 override，不只前段原始函式
8. Stored XSS context-aware encoding
9. `X-SWSI-Client-ID` + Worker 真實錯誤訊息
10. 照片前端最多 3 張
11. theory/law deep-link
12. localStorage 儲存失敗提示
13. 申論 AI 過度承諾文案收斂 + 外部 AI 隱私說明
14. 首頁第一屏定位：**免費社工師國考學習平台**
15. SEO / OG
16. keyboard / aria
17. `E-115-2-R-1` 私用字元清理
18. bump `sw.js` VERSION
19. 全文 grep 判題／XSS／override
20. diff review
21. Netlify production deploy **一次**
22. 手機 Safari / Android Chrome / Desktop Chrome smoke

### 月底驗收最低集合
- 首頁不先抓 4,800 題
- 115 年全部考次 = 400 pool
- 115-1 = 200 pool
- 115-2 = 200 pool
- 單一考次＋單科 = 40 pool
- 指定 115-2 Network 只需 `115-2.json`
- 再抽 104 年做同樣測試
- 24 多答案逐題 accepted option 全正確
- 16 一律給分不污染錯題
- 普通單答案抽測至少 20 題
- 錯題／間隔複習
- 模擬考含：普通、多答案、送分、未作答
- search deep-link
- 申論文字 AI
- 照片 1–3 張可走；第 4 張前端直接拒絕
- quota / rate-limit / 502 訊息
- XSS payload 只顯示字面文字
- PWA 更新後離線已下載題目可用

---

## 12. 不要重做／不要誤判

- **不要改 Netlify，除非使用者明確要求或到約定月更施工。**
- 不要把專案當資料救援階段。
- 不要再重查 4,800 題官方答案；audit 已 0 mismatch。
- 不要把 24 多答案 review 當 DB 錯題。
- 不要把 16 一律給分 review 當 queue 故障。
- 不要重建 Cloudflare 題庫 CDN。
- 不要另開 R2／第三個 Worker。
- 不要重建 D1 usage tables／rate limit bindings。
- 不要把 Rate Limiter 當精準每日 quota。
- 不要重新開 authenticated 題庫寫入。
- 不要把 Supabase anon key 當 secret。
- 不要把 Groq key / internal key 寫進 GitHub／聊天。
- 不要讓 AI 修改考選部官方題幹／選項／答案。
- 不要拿舊 GitHub Edge Function 覆蓋 production；主要 source 已重新對齊。
- 不要因單筆解析爭議批次重跑 4,800 題。
- 不要為了「程式漂亮」在公開前大規模刪除既有 UI override；先保守修正回歸風險。
- 前台做減法，後台自動化。

---

## 13. 目前真正的下一步

現在後端 P0 已大致收斂；AI 公開照片 guard 也已 production runtime 驗收。

**若還沒到學生端月更：**
- 可以繼續做 read-only frontend audit／測試設計
- 不要再堆重複架構文件
- 不要改 `index.html / sw.js / manifest.json`

**若使用者明確說開始月底學生端 patch：**

> 從 `FRONTEND_SCOPE_AUDIT.md` 的 round canonical regression 開始，接著 `accepted_answers`，再切 CDN loader；不要先從外觀／SEO 開始。

---

## 14. 下一個對話最短啟動指令

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「目前真正的下一步」繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。**
