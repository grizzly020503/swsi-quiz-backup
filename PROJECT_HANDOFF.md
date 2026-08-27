# SWSI 社工師國考平台 — 專案交接／續聊清單

## 2026-08-27 Round 8 code-health 最新接續狀態（本節優先）

> 本節晚於下方歷史內容；若衝突，以本節與 `PROJECT_HANDOFF_ROUND8_DELTA.md` 為準。

- branch：`fix/code-health-p0-20260826`
- 已驗證的 runtime code HEAD：`08279ab72659c5ba06f09cf77de5402a5d30146a`
- handoff closeout：包含本節的 commit 即目前 branch HEAD；接手時仍須先重新讀遠端 ref，禁止假設這個 SHA 永遠是最新。
- compare snapshot（`08279ab7`）：`main@0712b258`，branch ahead 136 / behind 0。
- 未 merge main、未 force push、未部署 Netlify production、未修改 production secrets、未做不可逆 production 操作。

### 已完成 ownership consolidation

- `renderHome` 收斂至 `20.product-philosophy.part` canonical owner。
- `normalize` 與 grading helpers 收斂至 `00.part`。
- mock answer record policy 移回 MK subsystem。
- AI feedback text/photo owner 收斂至 `99z.essay-trust-layer.part`。
- AI stable client ID / timeout utility 收斂至 `99_p0_mobile_ai_guardrails.part`。
- `85.escape-helper.part` 已刪除，escape helper 私有化至 `86.law-trust-ui.part`。
- `87.new-resident-law-status-ui.part` 已合併至 `86.law-trust-ui.part`。
- obsolete AI copy / final runtime / stable client shims 已移除。
- essay metadata labels 已改為 idempotent MutationObserver enhancer，不再接管 global `render()`。
- essay navigation 已於 `47dfca19` 收斂至 `zzz_fix_essay_navigation.part`：保留 slow/cache reload、tab state、state reset 與 render retry；`50.home-spacing-essay-entry.part` 與 `zzzz_product_v1_lock.part` 不再覆寫 `swsiOpenEssay`。
- Runtime Owner QA 已鎖住上述 ownership 與保留的 fail-closed edge guards。
- `08279ab7` 修正 Runtime Owner QA 對 async `swsiStartEssayNow` 的假陰性；現已正確鎖定唯一 deliberate owner `zzzzz_quick_essay_scope_fix.part`，未修改產品 runtime。

### 明確保留的 deliberate owners

- `70.learning-loop.part` 的 `renderReview`。
- `91.feedback-context.part`。
- `zzz_fix_essay_navigation.part`。
- `zzzzz_quick_essay_scope_fix.part`。
- `zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part` 的 invalid `acceptedAnswers()` 與 invalid-question `renderQuiz()` fail-closed guards。
- `99_p0_mobile_ai_guardrails.part` 的 mobile / draft / timeout / cache / busy utilities。
- `99z.essay-trust-layer.part` 的 AI trust/privacy/error boundary。
- `86.law-trust-ui.part` 與 `88.theory-trust-ui.part` 的 law/theory trust presentation wrappers：它們有獨立產品責任，不為降低 owner 數量而拆除。

### 最新 regression

`34c22f3` essay metadata enhancer：
- Runtime Owner QA #19：success
- Cloudflare Frontend Preview #113：success
- Monthly Frontend QA #134：success；`interaction-qa` 真正安裝並執行 Playwright Chromium
- Storage Durability QA #44：success
- Knowledge Runtime Snapshot QA #36：success

`47dfca19` essay navigation consolidation：
- Runtime Owner QA #22：success
- Cloudflare Frontend Preview #114：success
- Monthly Frontend QA #135：success；static + Chromium interaction 全綠
- Storage Durability QA #45：success
- Knowledge Runtime Snapshot QA #37：success
- Cloudflare Workers Builds：success
- P0 preflight、Service Worker / Worker / Supabase contracts、question shard integrity、knowledge catalog、production-shaped static smoke 均由 Monthly static job驗證成功。

`08279ab7` async quick-essay owner matcher：
- Runtime Owner QA run `33057724634`：success。
- log：`RUNTIME OWNER SMOKE OK`；`swsiStartEssayNow: zzzzz_quick_essay_scope_fix.part`。
- Cloudflare Workers Build：success。
- 本批僅修改 QA matcher/smoke，未改產品 runtime，因此未重跑與行為無關的完整 Chromium/Storage/Knowledge 套件。

### 安全與收尾

- `main...branch` 77 個 changed files；64 個仍存在的文字檔已做高信心 secret scan。
- 未發現 private key、GitHub/OpenAI/AWS token、JWT 或 production service-role literal。
- 唯一字串命中是 `scripts/cloudflare_worker_smoke.js` 的明確測試 fixture：`internal-secret` / `groq-secret`。
- `build-netlify-package.yml` 與 `verify-netlify-production.yml` 為手動 workflow；package job 只允許 `refs/heads/main`。
- Cloudflare preview publish/wait 只允許 `refs/heads/main`；本 branch 僅 build 驗證。
- 目前仍有 5 個本輪暫存 refs：`tmp-ai-client-owner-20260827-v2`、`tmp-ai-client-owner-20260827`、`tmp-law-status-consolidation-20260827-v2`、`tmp-law-status-consolidation-20260827`、`tmp-swsi-context-owner-20260827`。目前可用 GitHub 連接器未提供 delete-ref；不可用 force/move-ref 代替刪除。取得 delete-ref 權限後可安全移除，這不影響 runtime 或 merge correctness。

### Round 8 結論

**第八輪可結束。**

最新 owner evidence：
- single owner：`normalize`、grading helpers、`swsiOpenEssay`、`swsiStartEssayNow`、`dissectHTML`、global `render`。
- deliberate chains：`renderHome 00→20`、`renderReview 00→70`、AI feedback/photo `00→99z`。
- independent product wrappers：law `80→86`、theory `80→88`。

目前沒有尚未處理、且收益高於風險的 P0/P1 runtime override、dead shim 或重複 module。繼續縮 owner 數量只會進入 cosmetic cleanup、跨模組大改或破壞獨立產品責任，應停止。不要 merge main；Netlify production deploy 仍需使用者另行明確授權。


最後更新：2026-08-27（官方 grading contract regression + Unified QA 特殊給分 self-test 已補並全綠）

> 下一個 ChatGPT 對話先讀本檔，再接著做：
>
> **「請先讀 GitHub 私人 repo `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，再依『目前真正的下一步』繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。」**

---

## 0. 平台核心初衷

SWSI 的成立目的：讓準備台灣社工師國考的人有一個 **免費、公開、低門檻、真的能用** 的學習平台，不用再被題庫／解析訂閱牆卡住。

北極星：

> **「這個改動，有沒有讓考生更容易免費準備社工師國考？」**

學生端核心只抓：

> 做題 → 看解析 → 錯題／間隔複習 → 弱點 → 申論 → AI 回饋

前台做減法，後台自動化。核心刷題／複習／申論不應因 AI 額度不足而失效。

---

## 1. Source of truth / 專案位置

### GitHub
- private repo：`grizzly020503/swsi-quiz-backup`
- `main` = source of truth
- 本檔：`PROJECT_HANDOFF.md`

重要文件：
- `PRELAUNCH_QA.md`
- `MONTHLY_PATCH_PLAN.md`
- `CDN_FRONTEND_MIGRATION_DESIGN.md`
- `FRONTEND_MONTHLY_AUDIT.md`
- `FRONTEND_XSS_AUDIT.md`
- `FRONTEND_SCOPE_AUDIT.md`
- `audit/historical_answer_audit.md`

### Netlify
- production：`https://swsi-quiznetlify.netlify.app`
- **學生端採集中月更。現在不要改 `index.html / sw.js / manifest.json` 等正式前端，除非使用者明確說開始月底學生端 patch。**
- `netlify.toml` 用 `scripts/netlify_ignore.py`：只有學生端相關檔案變更才需要 build。
- README、audit、workflow、後台 test 等變更會 skip Netlify。

### Supabase
- project：`Swsi`
- project id：`yumjtrdctaxyczpspuyo`
- region：`ap-southeast-1`

### Cloudflare
- Worker：`wandering-wave-4418`
- URL：`https://wandering-wave-4418.c022050333.workers.dev`
- source：`cloudflare/wandering-wave-4418/worker.js`
- Wrangler：`wrangler.jsonc`
- Static Assets root：`cdn/`
- question CDN：`/question-shards/*.json`

D1：
- database：`swsi-ai-quota`
- binding：`AI_QUOTA_DB`
- tables：`ai_daily_client_usage`、`ai_daily_global_usage`

秘密只記名稱，不記值：
- `GROQ_KEY`
- `SWSI_INTERNAL_KEY`

---

## 2. 官方題庫／答案／給分模式 — 已完成，不要重查

Supabase 選擇題：
- **4,800 題**
- ROC 104–115
- 24 個考次
- 5 科 × 每考次每科 40 題

最新 115 年第 2 次：
- 200 選擇題
- 10 申論題

Historical MOEX Answer + Grading Mode Audit 已逐題核對官方最終資料：
- official questions：4,800
- Supabase questions：4,800
- answer findings：**0**
- grading-mode mismatches：**0**

### 多答案
- `questions.accepted_answers`
- 正式多答案：**24 題**
- 24 題仍故意 `analysis_status='review'`，避免舊前端／AI 解釋誤導；不是 DB 答案錯。

### grading_mode
Production 固定歷史基準：

| mode | 104–115 題數 | A-D | 未作答 |
|---|---:|---|---|
| `standard` | **4,784** | 依單／多答案集合 | incorrect |
| `all_credit` | **12** | correct | **correct** |
| `any_answer` | **4** | correct | incorrect |

4 題 `any_answer`：
- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

**重要：不得再從 `answer='一律給分'` 猜給分語意。**

12 `all_credit` + 4 `any_answer` 共 16 題仍刻意 `review`，因「官方特殊給分」不代表四個選項在學理上都正確。

Production migration：
- `20260825110853_preserve_official_grading_mode`

---

## 3. MOEX 自動同步 — grading mode 全鏈路已驗收

流程：

> 考選部 → GitHub Actions parser / health → Supabase → AI enrichment → CDN → 前端

Parser：
- `scripts/moex_sync_v2.py`
- 底層沿用成熟 `moex_sync.py`
- 可分 `standard / all_credit / any_answer`
- 多答案寫 `accepted_answers`
- M 更正格式無法安全解析 → **fail closed，不碰 Supabase**

Importer：
- `import-moex-social-worker`
- production v4 / ACTIVE
- fail-closed 驗證 `accepted_answers + grading_mode`

Health：
- `scripts/health_check_v2.py`
- local / remote grading mode 都驗
- 特殊給分缺 mode 不猜
- remote 104–115 grading baseline = 4784 / 12 / 4

Workflow：
- `.github/workflows/moex-social-worker-sync.yml`
- schema-only `standard` backfill 不再被當成官方內容變更
- main 併發更新時會 fetch/rebase/push retry
- 最近完整 run 已 success

不要回到舊「所有一律給分都一種模式」的 parser。

---

## 4. Cloudflare 題庫 CDN — 後端已完成，不要重做

架構：

> Supabase = source of truth  
> `scripts/build_question_shards.py` = build  
> GitHub Actions = verify / publish  
> Cloudflare Static Assets = CDN  
> Netlify = 月底改成按需載入

目前：
- baseline 24 shards：104-1 ～ 115-2
- 每 shard 200 題
- 4,800 題
- `accepted_answers`、`grading_mode` 都完整保留
- manifest / shard production HTTP 200
- `CF-Cache-Status: HIT`
- CORS 單一 `Access-Control-Allow-Origin: *`
- cache-control / nosniff 已驗
- AI root no-Origin POST 仍 403，Static Assets 沒吃掉 AI API route

Builder：
- 歷史 104–115 必須完整
- 新考次不滿 200 題 → fail closed，不發布半套
- 完整 116、117…會自動新增 shard
- 116-1 synthetic：**5,000 題 / 25 shards / `116-1.json`** 已 pass

### revision 注意
`dataset_revision` 與總 bytes **不是固定 contract**，因 shard 還包含 AI 解析／法規等會持續更新的欄位。

不要拿 handoff 裡某個舊 revision 當成「資料漂移」證據；最新 build/publish/smoke CI 才是 runtime source。

---

## 5. 2026-08-27 新增 grading regression — 已全綠

### Question Shards Build Check
commit：`778ee7f`

`.github/workflows/question-shards-build.yml` 現在除了 shard 結構，還鎖定 **104–115 immutable official grading baseline**：

- baseline questions = 4,800
- multi-answer rows = 24
- `standard` = 4,784
- `all_credit` = 12
- `any_answer` = 4
- 4 題 `any_answer` ID 必須精確一致
- special modes 必須 `answer='一律給分'` 且不可帶 `accepted_answers`

並有 executable frontend grading contract：
- `standard` blank → false
- accepted answers → true
- `all_credit` blank → **true**
- `any_answer` blank → **false**
- A-D 對兩種特殊模式都得分

2026-08-27 run：**success**。
實際 log：
- 4,800 questions
- 24 shards
- 24 multi-answer
- 4784 / 12 / 4
- `frontend_grading_contract: pass`
- 116-1 auto expansion 5,000 / 25 pass

### Unified Question QA self-test
commit：`e968e1a`

`scripts/unified_question_qa_selftest.py` 新增：
- 缺特殊 `grading_mode` → blocked
- 合法 `all_credit` → passed
- 合法 `any_answer` → passed
- 特殊 mode 與 answer／accepted_answers 自相矛盾 → blocked + human queue

Unified Question QA workflow run：**success**。
- synthetic invariants pass
- 115-2 snapshot pass
- compact admin dashboard invariants pass

不要再新增第三套 grading 判定；前端月底直接對齊這個 contract。

---

## 6. Unified Question QA / 法規 — 正常

Unified QA：
- `scripts/unified_question_qa.py`
- `scripts/unified_question_qa_selftest.py`
- `scripts/build_question_qa_dashboard.py`
- `.github/workflows/unified-question-qa.yml`

設計原則：
- Official Core 和 AI enrichment 分開
- AI 解析 pending 是 generation backlog，不等於 human review
- grading metadata 不完整 → Official Core fail closed

法規監測：
- 官方逐條查 `law.moj.gov.tw`
- 最近狀態：52/52 found、0 missing、0 changed
- canonical mapping 來源：題幹 + A/B/C/D + AI law
- 約 646 題有 canonical mapping（數字可隨 legacy AI law 清理略變）
- 題面直接出現 monitored law 但漏 mapping：0
- `sync-legal-watch` production v2 / ACTIVE

不要把「法規年代舊」自動當成「官方答案錯」。

---

## 7. AI analyzer / Cloudflare quota / 公開安全 — 已完成主要 P0

### Supabase AI analyzer
- `analyze-pending-questions`
- production v7 / ACTIVE
- scheduler job key 先驗證，再用同一值當 backend internal Cloudflare auth
- draft：Qwen
- audit：GPT-OSS
- internal path 不吃學生 D1 quota
- pg_net timeout 已 30 秒
- 24 小時完成上限 25 題
- queue 排序已讓最新考次跨科較平均

Queue 數字會變，不要把舊 ready/pending 快照當固定值。

### Worker public guard
- public Origin 只允許正式 Netlify SWSI site
- no Origin → 403
- fake Origin → 403
- POST / OPTIONS only
- request 約 4 MB 上限
- public model固定 Qwen
- internal backend 可 Qwen + GPT-OSS
- Groq error 不洩漏內部細節

### Public image guard
production runtime 已測：
- 正式 Origin + 非 JPEG data URL → 400
- 第 4 張 JPEG → 400
- 公開 image URL 只接受 JPEG data URL
- invalid image request 在 quota/Groq 前拒絕

### Rate / D1 quota
- `AI_RATE_LIMIT`：3 / 60 sec
- `AI_IP_LIMIT`：30 / 60 sec
- client daily text：約 10
- client daily photo：約 3
- 全站另有保守 daily gate
- Groq failure refund
- internal backend不吃學生 quota

### Supabase public security
`questions / essays`：
- anon SELECT only
- authenticated SELECT only
- 公開寫入已撤
- 危險 SECURITY DEFINER execute 已收斂

不要把 anon key 當 secret；service-role / Groq / internal key 才是秘密。

---

## 8. 現在真正還沒做的是「月底學生端 patch」

**目前正式 Netlify 舊前端仍沒有套以下修正。不要誤認 audit = production 已修。**

### 8.1 `index.html` 有後置 UIUX override
底部 script 會再次覆寫部分 function，至少包括：
- `renderHome`
- `renderReview`

所以月底不能只改前面同名 function；要看最後實際生效版本，或保守收斂重複邏輯。

### 8.2 已確認 round regression
見：`FRONTEND_SCOPE_AUDIT.md`

目前核心 filter 期待：
- `homeQuizRound='1' / '2' / 'all'`

但 UIUX V1 override 會傳：
- `第一次 / 第二次`

造成首頁指定單一考次可能顯示「沒有題目」。

月底先把內部 round canonical 統一成 `1 / 2 / all`。

### 8.3 多答案／特殊給分前端尚未支援
見：`FRONTEND_MONTHLY_AUDIT.md`

現行舊前端仍有：
- `ansCorrect(p,a)`
- `k===item.answer`
- `picked===q.answer`
- `/一律給分|送分/`

月底必須：
1. `normalize()` 保留 `accepted_answers + grading_mode`
2. 只用共同 `gradingMode / acceptedAnswers / isCorrectAnswer / answerLabel`
3. 一般刷題、模擬考、錯題、history、review schedule、正確率都走同一 contract
4. `all_credit` 空白得分，不進錯題
5. `any_answer` 空白不得分，進錯題
6. 特殊給分 UI 不把 A-D 四個都畫成「學理正確」

### 8.4 CDN 前端 loader 尚未切
見：`CDN_FRONTEND_MIGRATION_DESIGN.md`

低風險策略：
- manifest-first
- 指定歷屆只載需要 shard
- 需要全庫的搜尋／考點／隨機模擬／review 再 `ensureAllQuestionsLoaded()`
- 保留 `ALL` 相容橋，先不要大改全部 feature
- IndexedDB 改成可保存 manifest / shard；舊完整 `questions` cache 可做 fallback
- Cloudflare shard 是跨 origin，現行 `sw.js` 不攔；**不要硬塞進 Service Worker shell cache**

### 8.5 Stored XSS
見：`FRONTEND_XSS_AUDIT.md`

`renderQuiz()` 等仍有 DB/AI 動態文字直接進 `innerHTML`；月底要 context-aware escape，URL 只允許安全 scheme。

### 8.6 其他月底一起修
- 穩定 `X-SWSI-Client-ID`
- Worker 真實 quota/error message
- 模擬考未作答各科分母/history/review 一致
- deep-link 理論／法規自動展開
- localStorage 寫入失敗提示
- 申論 AI 過度承諾文案收斂
- AI 外部處理隱私說明
- 前端照片最多 3 張
- `E-115-2-R-1` PUA 字元清理
- 首頁第一屏「免費社工師國考學習平台」
- SEO / OG
- keyboard / aria
- 色彩對比
- 最後 bump `sw.js` VERSION（目前 v4）

---

## 9. 如果使用者明確說「開始月底學生端 patch」

施工順序不要亂：

1. **先修 round canonical regression**
2. **立刻補 `accepted_answers + grading_mode` 與統一 grading helper**
3. 加 grading regression / mock 驗收
4. 再切 Cloudflare manifest/shard loader
5. 再補 XSS / Client-ID / quota message / storage / deep-link / accessibility / 文案
6. bump `sw.js` VERSION
7. build + smoke + diff review
8. Netlify production deploy **一次**
9. iPhone Safari / Android Chrome / desktop Chrome + PWA smoke

不要先從 SEO、外觀或新功能開始。

---

## 10. 目前可以繼續做（還沒得到月更開工指令時）

可以：
- read-only frontend audit
- backend/self-test/regression
- 文件一致性清理
- GitHub Actions 測試加強

不要：
- 改 `index.html`
- 改 `sw.js`
- 改 `manifest.json`
- 改會影響 production 學生端的檔案
- 為了「程式漂亮」大規模重構 override
- 再做一套新的 grading / CDN 架構

2026-08-27 本輪已做：
- README 架構對齊：commit `f92c4f2`
- shard grading contract CI：commit `778ee7f`，run success
- Unified QA special-grading self-test：commit `e968e1a`，run success
- 以上變更都不在 Netlify student-facing path，`netlify_ignore.py` 會 skip production build

---

## 11. 不要重做／不要誤判

- 不要重查 4,800 題官方答案；audit = 0 finding
- 不要把 24 多答案 review 當 DB 錯題
- 不要把 16 特殊給分混成同一種：12 all_credit / 4 any_answer
- 不要把 `answer='一律給分'` 當 grading source of truth
- 不要重建 D1 / rate limit binding
- 不要重新開公開 DB write
- 不要讓 AI 修改官方題目／答案／grading mode
- 不要拿固定 shard revision 當 invariant
- 不要開 R2 或第三個 Worker重做題庫 CDN
- 不要拿 GitHub 舊 Edge Function 覆蓋 production
- 不要改 Netlify，除非使用者明確要求開始月更施工

---

## 12. 下一個對話最短啟動指令

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「目前真正還沒做的是月底學生端 patch」與「目前可以繼續做」繼續。不要重做已完成後端，也不要改 Netlify，除非我明確要求。**
