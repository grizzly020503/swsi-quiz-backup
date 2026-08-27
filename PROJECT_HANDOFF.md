# SWSI 社工師國考平台 — 專案交接／續聊清單

最後更新：2026-08-25（官方 grading mode 已完成 DB → parser → importer → health → audit → CDN 全鏈路驗收；月底前端施工規格已同步）

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
- 歷屆答案＋給分模式 audit：`audit/historical_answer_audit.md`

### Netlify
- 正式站：`https://swsi-quiznetlify.netlify.app`
- **學生端採每月集中更新，不要現在一直部署前端。**
- `index.html / sw.js / manifest.json / essay_guides.js / auto/questions_auto.json / auto/essays_auto.json` 等真正學生端檔案留到月底同一包。
- `netlify.toml` 已設定只有真正影響學生端網站的檔案變更才觸發 production deploy；audit／workflow／migration／一般監測資料不應因此部署學生端。

#### 2026-08-25 一次性 schema-backfill 注意
MOEX v2 第一次執行時，舊 `incoming` 題目缺 `grading_mode`、新 parser 對普通題補 `standard`，比較器一度把純 schema backfill 當成「官方內容變更」，bot commit `16814f00440dca72f44893dc83f81d6fa243fc7e` 因而改到 `auto/questions_auto.json`。

- 這次 commit **可能**符合 Netlify deploy trigger；目前手上的 GitHub 工具無法確認 Netlify 是否真的部署，因此不要聲稱已部署或未部署。
- 即使有部署，舊前端不讀 `grading_mode`，該欄位本身不改既有作答行為。
- workflow 已修正：普通 legacy row 缺 mode 在「變更比較」時視同 `standard`；特殊給分缺 mode 不猜、仍視為實質差異。
- 修正後實測 115030／115100 都顯示 `unchanged official content`，115100 也正確 `skip Supabase import`。
- 後續 MOEX bot commit 只改 `auto/health.json` 與法規監測檔，**沒有再改 `auto/questions_auto.json`**。

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

## 3. 題庫／官方答案／官方給分模式：已完成，不要重查

### Supabase 選擇題
- 總數：**4,800 題**
- 5 科 × 960 題
- ROC 104–115、24 個考次、每科每考次 40 題
- 無空白題幹、缺選項、非法答案、同考次同科重複題號

### Historical MOEX Answer + Grading Mode Audit
`historical_answer_audit_v4.py` 已逐題核對 24 個考次／4,800 題考選部最終 PDF：

- 官方考次：24
- 官方題數：4,800
- Supabase 題數：4,800
- answer findings：**0**
- grading-mode mismatches：**0**

Production grading mode 精確分布：

| `grading_mode` | 題數 | 未作答是否得分 |
|---|---:|---|
| `standard` | **4,784** | 否 |
| `all_credit` | **12** | **是** |
| `any_answer` | **4** | 否 |

結論：

> **Supabase 4,800 / 4,800 官方答案集合與考選部最終答案一致；官方「空白是否得分」語意也 4,800 / 4,800 一致。**

不要再把「答案資料庫可能大量錯誤」或「16 題都是同一種一律給分」當目前問題。

### 官方多答案
- `questions.accepted_answers` 已完成
- 正式多答案題：**24 題**
- DB constraint 已限制 A/B/C/D 且主 `answer` 必須包含於集合
- 24 題目前故意 `analysis_status='review'`
- 原因：**學生端尚未支援 accepted_answers 判題**
- 這是月底前端 P0，不是 DB 錯誤

### 官方特殊給分：16 題，但分成兩種
16 題仍故意 `analysis_status='review'`，避免 AI 把官方計分規則誤寫成「四個選項學理上都正確」。

#### `all_credit`：12 題
- 官方「一律給分」
- A/B/C/D 任一作答都得分
- **空白未作答也得分**

#### `any_answer`：4 題
官方文字是「除未作答者不給分外，其餘均給分」：

- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

這 4 題：
- A/B/C/D 任一作答都得分
- **未作答不得分**

### DB grading-mode migration
Production 已套：

`20260825110853_preserve_official_grading_mode`

已完成：
- `questions.grading_mode`
- 僅允許 `standard / all_credit / any_answer`
- 4,784 / 12 / 4 backfill
- official-change AI reset trigger 已納入 `grading_mode`
- migration 後 16 特殊給分題仍維持 `review`，沒有誤送 AI queue

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

## 4. 考選部同步：grading mode 全鏈路已驗收

流程：

> 考選部 → GitHub Actions → parser / health check → Supabase → AI 解析 → CDN → 前端

### Parser
保留成熟 `moex_sync.py` 底層 PDF／題號／選項解析；grading metadata 由薄 wrapper：

- `scripts/moex_sync_v2.py`
- `scripts/test_moex_grading_modes.py`

可區分：
- `standard`
- `all_credit`
- `any_answer`

M 格式不能安全解析仍 **fail closed，不碰 Supabase**。

### Importer
Supabase Edge Function：
- `import-moex-social-worker`
- production **version 4 / ACTIVE**
- 驗證 `accepted_answers`
- fail-closed 驗證 `grading_mode`
- GitHub source 已對齊 production v4

### Health check
新增：

`scripts/health_check_v2.py`

它沿用既有 `health_check.py` 的題數／結構／申論驗證，只加 grading-mode fail-closed：

- 普通 legacy row 缺 mode可視 `standard`
- `answer='一律給分'` 卻缺 mode → fail closed，不猜
- `standard + answer='一律給分'` → fail
- `all_credit/any_answer` 但 answer 不是 `一律給分` → fail
- remote 三態總和必須 = 4,800
- 特殊給分數與 answer 語意必須一致

2026-08-25 GitHub runner 實測：

```text
LOCAL GRADING HEALTH OK: all_credit=0, any_answer=0, standard=400
REMOTE HEALTH OK: Supabase questions=4800, essays=10,
grading_modes={'all_credit': 12, 'any_answer': 4, 'standard': 4784}
```

### MOEX workflow 防 schema-only 假變更
`.github/workflows/moex-social-worker-sync.yml` 已：

- 先跑 grading-mode unit test
- 用 `moex_sync_v2.py`
- local / remote 改跑 `health_check_v2.py`
- 普通 legacy 缺 mode 在比較時視同 `standard`
- 特殊給分缺 mode 不猜
- push 遇 main 併發更新時 `fetch → rebase → push`，最多重試 3 次

最新完整 run：**success**。

實測：
- 115030 → `unchanged official content`
- 115100 → `unchanged official content`
- 115100 → `No official changes ... skip Supabase import`
- concurrent main advance → rebase + push 成功

---

## 5. 法規監測：正常

### Official watch
- 逐條查 `law.moj.gov.tw`
- 最近 workflow：**52/52 found、0 missing、0 changed**

### Mapping
canonical mapping：

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
- 24 多答案隔離 `review`
- 16 特殊給分隔離 `review`（12 `all_credit` + 4 `any_answer`）
- DB trigger：`trg_reject_ai_answer_meta_commentary`
- official-change trigger 已納入 `grading_mode`
- `ready` 含「題庫答案標錯／官方答案有瑕疵／答案待查／建議查答案」等 meta 話術會被 DB 拒絕
- `ready` meta 污染驗收：**0**

最近 QA 快照（會隨排程變動）：
- ready：約 4512
- pending：約 248
- review：40（24 多答案 + 16 特殊給分）
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
- revision：**`e721d6293d4c6acdddee`**
- 約 6.84 MB 未壓縮總量
- 單 shard 約 193–301 KB
- 24 多答案完整保留
- `grading_mode` 完整保留：4,784 standard / 12 all_credit / 4 any_answer

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

## 9. Historical audit 自動化：已全綠

`.github/workflows/historical-answer-audit.yml` 現在跑：

`scripts/historical_answer_audit_v4.py`

同一輪驗：
- 4,800 題官方 accepted-answer set
- 4,800 題 official grading mode

最新 runner 結果：

```text
official_questions = 4800
answer_findings = 0
grading_mode_mismatches = 0
standard = 4784
all_credit = 12
any_answer = 4
```

報告已成功寫回：
- `audit/historical_answer_audit.json`
- `audit/historical_answer_audit.md`

workflow 的 report push 也已改為 `fetch → rebase → push` 重試，避免長時間 audit 過程中 main 被其他 bot 推進而出現「資料比對成功但 workflow 假紅燈」。最新 run 整體 **success**。

---

## 10. 最新前端 code audit：非常重要

**以下仍只是 audit／施工設計；尚未故意修改 `index.html`、尚未進行約定的月底學生端 patch。**

### 10.1 `index.html` 是「原始函式 + 後置 override」
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
- 自訂指定歷屆有 round value regression

目前底部 `renderReview()` 仍：

```js
ids.map(id => ALL.find(q => q.id===id)).filter(Boolean)
```

CDN partial-bank 後若不加 full-bank gate，舊錯題可能暫時消失。

### 10.2 已確認現行 bug：指定歷屆 round value regression
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

### 10.3 `normalize()` 必須同時帶兩種 metadata
月底必補：

```js
accepted_answers: Array.isArray(r.accepted_answers)
  ? r.accepted_answers.filter(x=>['A','B','C','D'].includes(x))
  : null,
grading_mode: ['standard','all_credit','any_answer'].includes(r.grading_mode)
  ? r.grading_mode
  : (r.answer==='一律給分' ? 'unknown' : 'standard'),
```

原則：
- 普通 legacy row 缺 mode可視 `standard`
- 特殊給分缺 mode **不能猜**
- 正常 CDN / Supabase production 已提供正式 mode，不應走 `unknown`

### 10.4 判題邏輯要收斂成 item-based helper
月底統一：

```js
gradingMode(item)
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

### 10.5 模擬考未作答規則：依 grading mode，不是一律算錯

| mode | 未作答 |
|---|---|
| `standard` | incorrect |
| `all_credit` | **correct** |
| `any_answer` | incorrect |

共同規格：
- 每題都進各科分母
- 每題先用 `isCorrectAnswer(q,picked)` 算結果
- incorrect 才進錯題／間隔複習
- `all_credit` 空白不得污染錯題
- UI 可同時顯示「未作答」＋「官方一律給分，本題仍得分」

已確認現有 `record(item,picked,correct)` 不把 `picked` 寫入 history，只存 id/subject/major/mistake/correct/ts，因此 `picked=null` 技術上安全；真正重點是 `correct` 必須依 grading mode 算對。

### 10.6 特殊給分 UI 不要把四個選項都塗綠
`all_credit / any_answer` 的 A-D 都可能「依官方規則得分」，不代表四個選項都學理正確。

建議：
- 顯示「本題依官方特殊給分規則計分」
- `all_credit`：`官方一律給分（未作答也得分）`
- `any_answer`：`除未作答者不給分外，其餘均給分`
- 不把 A-D 全標成「正確答案」

### 10.7 Stored XSS
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

### 10.8 Search deep-link
現行：

```js
openTheory(name){ theoryQ=name; theoryOpen=name; ... }
openLawCard(name){ lawQ=name; lawOpen=name; ... }
```

但 render 端以 `THEORIES.indexOf(t)` / `LAWS.indexOf(l)` 的數字 index 判 `open`，所以 name 不會命中。

月底要 name → index，不能直接把 name 塞進 index state。

### 10.9 照片 AI 前端仍允許 4 張
現行 `gradePhoto()`：

```js
if(files.length>4){ files=files.slice(0,4); }
```

而 Worker production 已明確最多 3 張。

月底：
- `files.length > 3` → 直接提示「一次最多 3 張」
- 不要默默截掉第 4 張

### 10.10 AI client ID / 真實錯誤訊息
Worker 已支援 `X-SWSI-Client-ID`，舊學生端尚未送。

月底：
- localStorage UUID helper
- 文字／照片 fetch 都送 `X-SWSI-Client-ID`
- 非 2xx 優先讀 Worker JSON `error.message`
- daily quota 不顯示「立即重試」
- 413／502／503 分別友善處理

完整細節以最新 `FRONTEND_MONTHLY_AUDIT.md` 為準。

---

## 11. CDN 前端切換設計：已完成，月底只實作

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

## 12. 月底 Netlify patch — 真正施工順序

**目前不要執行，除非使用者明確說要開始學生端月更。**

建議順序：

1. 備份當下 `index.html / sw.js / manifest.json` SHA
2. **先修 round canonical regression**
3. 補 `normalize().accepted_answers + grading_mode`
4. 建立統一 `gradingMode / acceptedAnswers / isCorrectAnswer / answerLabel`
5. 同輪改一般刷題 + `MK.grade()` + grading-mode 未作答規則
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
- 12 `all_credit`：A-D 與未作答都得分
- 4 `any_answer`：A-D 得分、未作答不得分
- 普通單答案抽測至少 20 題
- 錯題／間隔複習
- 模擬考同場含：普通、多答案、all_credit 空白、any_answer 空白
- search deep-link
- 申論文字 AI
- 照片 1–3 張可走；第 4 張前端直接拒絕
- quota / rate-limit / 502 訊息
- XSS payload 只顯示字面文字
- PWA 更新後離線已下載題目可用

---

## 13. 不要重做／不要誤判

- **不要改 Netlify，除非使用者明確要求或到約定月更施工。**
- 不要把專案當資料救援階段。
- 不要再重查 4,800 題官方答案；audit 已 0 finding。
- 不要再把 16 特殊給分題當成同一種「一律給分」；必須依 12 all_credit / 4 any_answer。
- 不要從 `answer='一律給分'` 猜空白是否得分；讀 `grading_mode`。
- 不要把 24 多答案 review 當 DB 錯題。
- 不要把 16 特殊給分 review 當 queue 故障。
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

## 14. 目前真正的下一步

目前後端 P0 已收斂到：
- 4,800 官方答案 0 finding
- grading mode 0 mismatch
- parser v2 / importer v4 / health v2 / audit v4 全綠
- CDN 已帶 grading mode
- AI public photo guards 已 production runtime smoke

**若還沒到學生端月更：**
- 可繼續做 read-only frontend audit／測試設計
- 可清理仍引用舊「16 一律給分／空白一律錯」的文件
- 不要再堆重複架構文件
- 不要改 `index.html / sw.js / manifest.json`

**若使用者明確說開始月底學生端 patch：**

> 從 `FRONTEND_SCOPE_AUDIT.md` 的 round canonical regression 開始；第二步立刻補 `accepted_answers + grading_mode` 與統一判題 helper；之後才切 CDN loader。不要先從外觀／SEO 開始。

---

## 15. 下一個對話最短啟動指令

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「目前真正的下一步」繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。**

## 2026-08-27 Code Health Round 8 最終驗收

此段為本輪最新狀態；若前文仍有「待做／月底再做」的歷史敘述，以本段與 `KNOWN_ISSUES.md` 為準。

- authoritative branch head（驗收時）：`b29fbca24fab783092290229d41bc8a300898e95`
- 核心 atomic commits：`80a92eed`（grading/shard/Worker/SW/release contracts）、`d46317d0`（history/review-state schema guard）
- Monthly Frontend QA #91 `33030671962`：static-qa + Playwright Chromium interaction-qa 全綠
- Storage Durability QA #7 `33030671919`：schema/quarantine browser smoke 全綠
- Essay Guide Audit #7 `33030369777`、Unified Question QA #8 `32981787083`、MOEX Importer Integrity QA #1 `33003892890` 全綠
- 24 shard artifact SHA、tampered shard、legacy offline cache rejection、full-bank invariant 全綠
- Supabase production 僅唯讀核對；沒有 schema/data write。Recovery drift 由 `20260827031000_align_recovery_reset_with_grading_mode.sql` 對齊。
- 沒有部署 Netlify、沒有改 production secrets。Cloudflare Git integration 自動 build checks 成功；branch preview publish/wait steps 均 skipped。
- 仍保留的工程債：`index.html + monthly_patch_parts` 多層 runtime override，短期由 owner/preflight/browser regression 鎖住，長期再模組化。
- merge 建議：走一般 PR merge，保留 main-only preview artifact commit；禁止 force push 或直接覆蓋 main。Netlify production deploy/verify 留待明確 release 授權。

