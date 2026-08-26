# SWSI 未完成工作證據核對 — Part 5

日期：2026-08-27

本附錄延續 `UNFINISHED_WORK_LEDGER.md` 與 Part 1–4。本輪只核對兩件事：

1. 官方歷屆申論題 vs `ESSAY_GUIDES` 的實際 coverage。
2. production `analysis_status` 在學生端目前究竟如何呈現。

---

## 1. 申論題目前實際數量

狀態：`VERIFIED`

`index.html` 內嵌歷屆申論資料明確註記：

- `申論題資料 — 共 230 題`

另外 `auto/essays_auto.json` 現有 115 年第二次 10 題：

- E-115-2-HBSE-1 / 2
- E-115-2-SW-1 / 2
- E-115-2-DS-1 / 2
- E-115-2-R-1 / 2
- E-115-2-SP-1 / 2

`loadAutoEssays()` 會把 auto essays 依 logical exam key 去重後加入 `window.ESSAYS`。內嵌歷史資料只到 115-1，因此這 10 題並非舊資料 duplicate。

目前可視為：

- historical embedded essays：230
- latest auto 115-2 essays：10
- current official essay questions available at runtime：約 240

---

## 2. Essay guide coverage

狀態：`230 / 240 HAVE GUIDE; 10 LATEST ESSAYS MISSING GUIDE`

Monthly Frontend QA 在執行 `scripts/build_essay_guides_runtime.js` 時有明確成功輸出：

`ESSAY GUIDES RUNTIME OK: 230 unique guides; normalized 社會工作-107-1-申論2`

因此 historical guide runtime 目前是 230 unique guides。

另外 repo 搜尋 `essay_guides.js` 找不到任何 115-2 guide key；而 `auto/essays_auto.json` 有 10 題 115-2 官方申論。

因此目前 coverage 為：

- 230 historical essays：230 guides
- 10 latest 115-2 auto essays：0 guides
- total：230 / 240 = 95.83% 有 guide
- missing guide：10 / 240 = 4.17%

### 重要：coverage != verified

「有 guide」只代表平台有一份 SWSI-authored 骨架，不代表已逐題人工／來源查證。

目前正式 evidence-backed per-question audit registry：

`data/essay_guide_audit_batch1_20260826.json`

只標記 `verified_count = 5`。

因此前台不可把 230 題全部概括稱為：

- 已人工校過
- 校過骨架
- 已驗證正確

建議信任層級至少分：

- `平台整理`：有 guide，但尚未正式逐題 evidence audit
- `已查證`：存在 audit registry + sources + browser audit
- `整理中`：最新題尚未有 guide

---

## 3. 最新 115-2 申論目前資料成熟度

狀態：`QUESTION IMPORTED / GUIDE AND ANALYSIS PENDING`

`auto/essays_auto.json` 的 10 題 115-2：

- 官方題幹 / source URL 已匯入
- `analysis_status = pending`
- topic / major 為 null
- keywords / theories / laws 為空
- 尚無 `ESSAY_GUIDES` 對應 key

因此這 10 題目前可作為「官方新題瀏覽／自行練習」，但不應假裝已有平台完整解析或 verified skeleton。

---

## 4. Production 選擇題 analysis status 真實分布

狀態：`VERIFIED FROM PRODUCTION READ-ONLY QUERY`

Supabase `questions` 目前共 4,800 題：

- `ready`：4,537
- `pending`：221
- `review`：42

`exp_why` 缺失總數 = 263，剛好等於 221 + 42，表示目前資料狀態與解析缺失數量相符。

42 題 review 原因：

- 24：`官方多答案題：等待前端 accepted_answers 判題支援後重新解析`
- 16：`一律給分題：等待 analyzer 明確支援 A-D 全部計分後再生成解析`
- 2：`AI 回傳找不到 JSON array`

注意：前兩類 reason 是歷史 workflow 留下的 review reason。由於目前 fix branch 已實作 accepted_answers / grading_mode contract，這些題之後可能具備重新進 analyzer 的條件；但在真正重新解析前，不可直接改成 ready。

---

## 5. 學生端目前如何呈現 pending / review

狀態：`CONFIRMED STATUS FLATTENING`

### Base `index.html`

原始 `renderQuiz()` 在沒有 `item.exp` 時仍顯示：

`此題解析生成中。正確答案是 ...，先記下來，詳解之後補上。`

### 後置 `monthly_patch_parts/00.part`

安全版 `renderQuiz()` 雖已：

- 使用 `gradingMode()` / `acceptedAnswers()` / `answerLabel()`
- all_credit 顯示官方一律給分提示
- any_answer 顯示官方特殊給分提示
- explanation 使用 `swsiEscLines()`

但在沒有解析時仍顯示：

`此題解析生成中。<answerLabel>，先記下來，詳解之後補上。`

repo frontend code search 未找到 `analysis_status` 的實際 UI branch。

因此目前學生端：

- pending -> 解析生成中
- review / 多答案 -> 可能先看到可接受答案 label，但解析本身仍顯示解析生成中
- review / 一律給分 -> 先看到「官方一律給分」，再顯示解析生成中
- review / AI JSON failure -> 解析生成中

也就是 backend 有精細狀態，但 frontend 沒有把狀態原因帶給學生。

---

## 6. 這是不是 blocking bug？

狀態：`CONTENT TRUST / UX P1-P2, NOT GRADING P0`

這不是目前 grading correctness 的 P0，因為 fix branch 已把官方判題語意和解析內容分開：即使沒有解析，答案／特殊給分仍可依 grading contract 顯示。

但這是明確的內容可信度 / UX 缺口：

- 學生不知道「尚待一般解析」與「因官方特殊給分需重新生成」的差別。
- `解析生成中` 容易讓人誤以為所有 263 題只是排隊，而其實 42 題是 review。
- 2 題是真的 analyzer JSON failure，也不應永久被當成普通 pending。

建議後續建立前端 presentation status，不直接把 internal error reason 全量暴露給學生，例如：

- `解析整理中` — pending
- `特殊給分題・解析待重新整理` — review + all_credit/any_answer/multi-answer
- `解析待複核` — review 其他情況

管理端則保留完整 internal reason。

---

## 7. 對舊 ledger 的狀態更新

### C2「參考骨架整理中」

由 `PENDING_VERIFY` 更新為：

`PARTIALLY_SUPERSEDED / 10 REAL MISSING GUIDES`

舊 placeholder 文案可能已移除，但 coverage 並非 100%。真正缺口是最新 115-2 的 10 題。

### C3「解析生成中」

由先前 Part 3 的 `LIKELY_SUPERSEDED` 修正為：

`STILL PRESENT / STATUS MODEL NOT EXPOSED`

這是本輪重要更正：字串仍存在於 base 與後置安全 renderQuiz；只是 grading 顯示比舊版成熟。

---

## 8. 建議後續順序

1. 不要為了湊 100% coverage 自動生成 115-2 十題並冒充 verified。
2. 先讓最新 10 題清楚標示「官方新題・平台整理中」。
3. 分批建立 115-2 guide，建立後仍先標 `平台整理`。
4. 經來源查證 + per-question audit 後才升級 `已查證`。
5. 選擇題前端讀取 `analysis_status`（或由公開 presentation status 衍生），把 pending / review 的學生文案分開。
6. 42 review 題在 grading contract 已穩定後，另行評估是否重新排入 analyzer；2 個 AI JSON failure 應可獨立 retry。
7. 所有上述內容工作維持獨立 branch，不混入目前 Work 的 P0 code-health 原子 commit。
