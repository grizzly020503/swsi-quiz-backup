# SWSI 全站程式碼健康盤點 2026-08-26

狀態：`audit only / no student-facing changes`

基準：`main` 近期 HEAD `c8bd9c44c8878e22feb688aeec88b09a3fe4b926`（固定輕量 QA 後台 dashboard 資料契約）附近之現行架構。

> 本盤點不修改 `index.html`、`essay_guides.js`、`monthly_patch_parts/`、`sw.js`、`auto/` 或任何 Netlify 學生端檔案。
>
> 目的：重新區分「現在仍存在的 active bug」、「latent / release risk」、「已被後置 patch 或 production DB 修掉的舊問題」。

---

# 一、先釐清程式碼規模

目前 repo metadata 約 6 MB 級；它不是「五十幾萬行手寫程式」。

大量體積來自：
- 題庫 JSON / shard / auto payload
- audit / QA 文件
- release / preview / recovery 資料
- `index.html` 內嵌的大量題庫與功能程式

`index.html` 本身不到 3,000 個實體換行，但單行可能非常長，因此「bytes / repo size」不能直接換算成程式行數。

真正的風險不是單純行數，而是：
1. legacy 邏輯與後置 override 同時存在；
2. 多個 patch 依檔名排序決定誰最後生效；
3. production DB / GitHub recovery source 可能漂移；
4. release gate 尚未完整攔住已知 P0。

---

# 二、Confirmed active P0

## P0-1 計時模擬考仍使用舊判題引擎

### 現況
`index.html` 的 `MK` 封在 private closure 內，`grade(auto)` 仍以：

```js
var ok = picked != null && (
  picked === q.answer ||
  /一律給分|送分/.test(String(q.answer||''))
);
```

判題。

後面的 monthly patch 雖已建立：
- `gradingMode(item)`
- `acceptedAnswers(item)`
- `isCorrectAnswer(item,picked)`

但只能包 `MK.open()`，無法直接替換 closure 內的 `grade()`。

### 直接後果
- `standard` 多答案題：第二／第三個官方可接受答案可能被判錯。
- `all_credit`：未作答本來也得分，現在因 `picked != null` 被判錯。
- `any_answer`：有作答通常會因文字 fallback 得分，但仍依 answer 字串猜規則。
- 未作答普通題不進 `bySubj` 分母。
- 未作答普通題不呼叫 `record()`，不會進 history / review schedule。
- 結果頁仍只顯示 `正解 ${q.answer}`，沒有完整 `accepted_answers` / grading-mode 文案。

### 判定
`P0 / student scoring correctness`

### 正式修法
讓 MK grading 只呼叫共同 grading contract；因 closure 邊界，最穩妥是直接改 `index.html` 的 MK 內部，或把 grading helper 在建立 MK 前注入為唯一 dependency。

---

## P0-2 特殊給分缺 metadata 時仍 fail-open 猜測

### 現況
`monthly_patch_parts/00.part` 的 `gradingMode(item)` 仍保留：

```js
SWSI_ANY_ANSWER_LEGACY_IDS
```

以及：

```js
/一律給分|送分/.test(item.answer)
```

來推論 `any_answer / all_credit`。

`normalize()` 缺 `grading_mode` 時也會回頭呼叫上述 `gradingMode()` 合成 mode。

更重要的是 `validateShard()` 本身也呼叫這個會推論的 `gradingMode(row)`，所以「特殊給分 metadata 缺失」會被合理化成合法資料，而不是 fail closed。

### 直接後果
資料層若漏掉 `grading_mode`，學生端不會報資料錯誤，反而自行猜一個官方給分語意。

### 判定
`P0 / official scoring semantics`

### 正式修法
- 普通題缺 mode 可 legacy-default `standard`。
- `answer=一律給分` 或其他特殊 marker 卻缺 mode → `unknown / blocked`。
- `validateShard()` 必須直接讀 raw metadata 驗證，不能先經會推論的 helper。

---

## P0-3 `ESSAY_GUIDES` 已確認 duplicate key

已確認：

```text
社會工作-107-1-申論2
```

在 `essay_guides.js` object literal 中至少有兩份不同內容，JavaScript 會 last-write-wins，runtime 不報錯。

### 直接後果
- 人工以為前面已修正，後面同 key 仍可靜默蓋掉。
- runtime `Object.keys()` 看不出 source duplicate。

### 判定
`P0 / content integrity`

---

## P0-4 Release gate 沒有真正執行已存在的 P0 preflight

已存在：

```text
scripts/p0_frontend_preflight.js
```

而且目前設計上就是 `EXPECTED FAIL`，專門攔：
- duplicate essay guide key
- special grading legacy inference
- source-level home round contract

但目前：
- `.github/workflows/monthly-frontend-qa.yml` 沒有執行它。
- `.github/workflows/build-netlify-package.yml` 也沒有執行它。

因此已知 blocker 存在時，production-shaped smoke / release package 仍可能成功。

### 判定
`P0 / release-gate gap`

---

## P0-5 `essay_guides.js` 沒有完整進 release QA gate

`monthly-frontend-qa.yml`：
- `push.paths` 沒列 `essay_guides.js`。
- JS syntax step 沒有 `node --check essay_guides.js`。
- duplicate-key preflight 沒有執行。

`build-netlify-package.yml`：
- 會 copy `essay_guides.js`
- 但也沒有 `node --check essay_guides.js`
- 沒有 source-level duplicate-key lint

### 直接後果
只修改 `essay_guides.js` 時：
- monthly frontend QA 不一定自動跑。
- syntax / duplicate key 不一定在封版前被 gate 攔住。

### 判定
`P0 / release-gate + essay content integrity`

---

## P0-6 Service Worker 可能讓舊 `monthly_patch.js` / `essay_guides.js` 黏住

`sw.js` 現況：

```js
const VERSION = 'v5';
```

`monthly_patch.js`、`essay_guides.js` 屬於「其他靜態檔」，走 cache-first。

HTML 是 network-first，但如果本次只更新 monthly patch / guide，而 `sw.js` 本身 byte-for-byte 沒變、cache key 仍 `v5`：
- 瀏覽器會拿到新 HTML；
- 但同 URL 的 `monthly_patch.js` / `essay_guides.js` 仍可能由舊 cache 回應。

而兩個 release workflow 還以 grep 強制目前 `VERSION = 'v5'`。

### 直接後果
GitHub / Netlify 已修好的 bug，既有學生裝置仍可能繼續跑舊 patch。

### 判定
`P0 / deployment correctness`（尤其正式修 scoring P0 時）

### 正式修法
至少二擇一：
1. 每次 student-facing static release bump SW cache version；或
2. `monthly_patch.js` / `essay_guides.js` 改 network-first / versioned URL / content-hashed asset。

---

# 三、Confirmed P1

## P1-1 CDN shard manifest SHA-256 目前沒有真的驗內容

`cdn/question-shards/manifest.json` 每個 shard 都有 `sha256`。

但前端 `loadQuestionShard()`：
1. fetch JSON；
2. `validateShard()` 只檢查 schema/year/round/200 題/ID；
3. 沒有對下載 bytes 重新算 SHA-256；
4. 成功後直接寫：

```js
{ payload, sha256: meta.sha256 }
```

進 IndexedDB。

也就是「預期 hash」被當成「實際已驗證 hash」。

此外舊 IndexedDB row 若完全沒有 `rec.sha256`，目前條件：

```js
!rec.sha256 || rec.sha256 === meta.sha256
```

仍會接受。

### 風險
CDN 若回傳結構完整但版本錯誤的 200 題 shard，前端會接受並把它標記成正確 hash。

### 判定
`P1-high / data version integrity`

---

## P1-2 shard 完整性只驗「單檔」，沒有全庫總量／跨 shard ID invariant

每個 shard 內會檢查 duplicate ID，但 `mergeRowsIntoAll()` 以 `Map(id)` 合併，跨 shard 相同 ID 會 last-write-wins。

`QB.allComplete` 依 loadedFiles 數量判斷，而不是：

```text
ALL unique count == manifest.total_questions
```

首頁 `questionTotal()` 又優先顯示 manifest total。

因此若兩個 shard 發生跨檔 ID collision，UI 仍可能顯示完整題數，但實際 `ALL` 少題。

### 判定
`P1 / silent partial bank`

---

## P1-3 Unified Question QA 沒有對它實際檢查的資料路徑觸發

`.github/workflows/unified-question-qa.yml` 真實測試會讀：

```text
cdn/question-shards/115-2.json
auto/essays_auto.json
```

但 `push.paths` / `pull_request.paths` 沒有列這兩類 data paths。

### 後果
題庫快照真的變更時，Unified Question QA 不一定自動跑。

MOEX workflow 另有 `health_check_v2.py`，所以不是完全無驗證；但 Unified QA 現在還不能被視為可靠的 data release gate。

### 判定
`P1 / QA trigger coverage`

---

## P1-4 Cloudflare Worker 把 analyzer 要求的 temperature=0 變成 0.4

Worker：

```js
Number(body.temperature) || 0.4
```

JavaScript 中 `0` 是 falsy。

Supabase analyzer 明確傳：

```js
temperature: 0
```

因此實際送 Groq 的是 `0.4`，不是 0。

### 後果
後台以為解析生成 deterministic，實際存在額外隨機性，可能增加同題重跑差異與 QA 不穩定。

### 判定
`P1 / AI generation determinism`

---

## P1-5 最後生效的 AI UI 仍把不同 429 混成泛用訊息

Worker 已會回：
- `CLIENT_DAILY_QUOTA`
- `GLOBAL_DAILY_QUOTA`
- minute rate limit
- upstream 429

早期 `00.part` 曾有 `aiErrorInfo()` 能讀 error code。

但後面的 Product V1 `runAIFeedback / gradePhoto` 再次 override，最後對 429 主要顯示：

```text
目前 AI 使用量較高，請稍後再試
```

### 後果
學生今天額度已用完時，不知道是「今天不能再用」而不是「等一下就好」。

### 判定
`P1 / UX + unnecessary retries`

---

## P1-6 history / review storage 失敗仍缺可見提示，且 history 無上限

目前申論 `saveDraft()` 已能在畫面顯示：

```text
⚠ 無法儲存，請立即備份
```

但：
- `saveHist()`
- `saveReviewState()`

失敗時主要只設定 `window.__swsiStorageWarning` + `console.warn`，沒有全站 toast / visible banner。

同時 `record()` 會持續：

```js
h.push(...)
```

沒有 retention / compaction / cap。

### 長期風險
重度使用者累積大量 history 後可能碰到 localStorage quota；之後刷題看似正常，但進度停止保存。

### 判定
`P1/P2 / long-term progress durability`

---

## P1-7 Production Supabase 與 GitHub recovery SQL 已出現 schema drift

Live production DB 目前 `reset_ai_analysis_on_official_change()` 已包含：

```text
new.grading_mode is distinct from old.grading_mode
```

trigger columns 也包含 `grading_mode`。

但 GitHub：

```text
supabase/migrations/20260825094110_production_qa_consolidation.sql
```

內的 recovery consolidation 版本沒有 `grading_mode`。

### 後果
正式站現在是對的，但若日後依 repo consolidation 災難復原，可能退回成「grading_mode 改變不清舊解析」。

### 判定
`P1 / disaster-recovery drift`

---

## P1-8 MOEX import 對 ID 只驗「非空 + payload 內唯一」，缺跨考次 collision 防護

`import-moex-social-worker` 與 `health_check.py` 都有：
- 200 / 10 題數
- subject
- qno
- source_exam_code
- payload 內 unique ID

但沒有強制驗證：

```text
incoming ID 對應到既有 row 時，既有 row 的 exam/session/subject/qno 必須與 incoming 相同
```

import 最後以：

```text
upsert ... onConflict: id
```

寫入。

### 風險
若未來 parser regression 產生一個「在新 payload 內唯一、但碰巧撞到舊考次既有 ID」的 ID，upsert 可能覆蓋舊 row，再由後續 remote health 才發現總數異常；也就是 gate 可能在破壞性寫入之後才報錯。

### 現況
Live DB 已查：
- questions = 4,800
- source_exam_code 對 year/round mismatch = 0

所以這是防護缺口，不是目前已有資料毀損。

### 判定
`P1 / importer integrity`

---

## P1-9 Patch ordering 已成為架構風險

最終 `monthly_patch.js` 是：

```bash
cat monthly_patch_parts/*.part
```

而同一功能存在多次 override，例如：
- `renderHome`
- `runAIFeedback`
- `gradePhoto`
- `aiFeedbackHTML`
- navigation helpers

目前正常是因為檔名 `99_ / zz_ / zzz_ / ...` 的 lexical ordering 剛好讓正確版本最後生效。

### 風險
新增一支檔名排序更後的 patch，或未來合併／重新命名，即可能讓舊版本復活。

### 判定
`P1 / architectural regression risk`

---

## P1-10 Anonymous AI client id 不是強身份，可被重建／偽造

Worker 對公開 AI 配額主要以 `X-SWSI-Client-ID` 做 client daily quota。

這是前端 localStorage UUID：
- 使用者可清除／替換。
- HTTP script 可偽造 Origin + client id。
- 若 localStorage 不可用，`swsiGetClientId()` 每次呼叫可能重新產生 ID。

### 緩解
目前仍有：
- per-IP minute limit
- global daily text/photo cap

所以不是無限成本漏洞。

### 判定
`P1/P2 / quota abuse availability`

---

# 四、內容層（不是純程式 bug，但目前仍會影響學生）

## C0-1 Batch 1–16 verified 申論修正版尚未等同「學生端已全部套用」

目前大量高風險申論已完成 audit / verified payload：
- generic template 答非所問
- 歷史題倒灌未來法規／政策
- 題目指定子問被 generic guide 吃掉

但這些 audit 的目的原本就是等正式 student-facing patch window 再合併。

因此：

> 「我們已經知道正確修法」不代表 `essay_guides.js` 現在所有錯配都已經消失。

正式 patch 時應以 verified registry 為唯一 merge source，再跑 must / must-not smoke。

---

# 五、舊盤點中已經修好／目前不應再算 active bug 的項目

## 已修 1：首頁考次 runtime canonicalization
最終 monthly patch / Product V1 renderHome 已使用：

```text
value = all / 1 / 2
label = 全部考次 / 第一次 / 第二次
```

並且 `setHomeQuizRound()` 會 canonicalize。

`index.html` 仍保有 legacy source，因此 preflight 會把它當 source debt；但目前最後 runtime UI 已不是舊的「第一次/第二次 value」bug。

## 已修 2：照片上限
目前最後 UI / worker 都是 1–3 張，沒有再 silent slice 4 張。

## 已修 3：theory / law search deep-link
後置 patch 已把名稱轉成實際 numeric index 再開卡。

## 已修 4：`X-SWSI-Client-ID`
`swsiFetchWithTimeout()` 最後 override 會自動加 header；AI 與 feedback 都可使用 stable anonymous ID（localStorage 可用時）。

## 已修 5：主要 stored-XSS surface
一般刷題題幹、選項、解析、topic、major、mistake、search、progress 等主要 DB-derived output 已改走 `swsiEsc / swsiEscLines`。

仍應保留 source-level XSS smoke，但不應把 8/25 audit 的全部項目當成「現在還沒修」。

## 已修 6：申論草稿 storage 可見提示
目前 `saveDraft()` 已有 visible failure status。

## 已修 7：production DB grading_mode change reset
Live Supabase trigger 已包含 `grading_mode`；正式 DB 現況正常。

## 已修 8：analysis_completed_at / 25-per-24h
Live Supabase 有 `trg_questions_analysis_completed_at` + `set_analysis_completed_at()`，`ready` 時會寫完成時間，因此 claim queue 的 25/24h cap 有資料來源。

## 已修 9：高權限 SECURITY DEFINER function 權限
Live Supabase 查得相關 queue/control functions EXECUTE 僅授權 `postgres` / `service_role`，沒有匿名公開執行權。

## 已修 10：questions / essays 公開資料權限
Live Supabase：
- RLS enabled
- anon/authenticated 對 questions / essays 為 SELECT-only
- 寫入由 service role 流程處理

---

# 六、正式學生端 patch 建議順序

## 第一階段：先讓 gate 不能放過已知 P0
1. monthly QA + release package 都執行 `p0_frontend_preflight.js`
2. `essay_guides.js` 加入 workflow trigger
3. `node --check essay_guides.js`
4. source-level duplicate-key lint fail build

## 第二階段：修真正會算錯學生分數的程式
5. MK `grade()` 改共同 grading contract
6. `gradingMode()` special metadata fail closed
7. `validateShard()` 不得使用會推論的 grading helper
8. 加 official multi / all_credit / any_answer / missing-mode browser smoke

## 第三階段：讓修正一定送到學生裝置
9. 修 Service Worker static update strategy / bump cache version
10. release smoke 測「舊 SW cache → 新 release」升級流程

## 第四階段：題庫完整性
11. 真正計算 shard SHA-256
12. 舊 cache 無 hash 不再直接 trusted
13. 完整載入後 assert unique IDs / `ALL.length == manifest.total_questions`
14. importer 加 existing-ID session collision guard

## 第五階段：申論內容
15. verified Batch 1–16 透過 registry 合併
16. must / must-not + duplicate + browser smoke

## 第六階段：P1 UX / backend
17. 429 讀 error code / message
18. Worker temperature 0 bug
19. history retention / compaction + visible storage warning
20. unified QA data-path triggers
21. recovery SQL 與 live Supabase schema resync
22. quota abuse hardening視流量再做

---

# 七、這次總判定

目前不是「整個平台到處都是 bug」。

比較準確的描述是：

> **核心資料／安全／QA 基礎已經比早期強很多，但仍有少數舊 closure、legacy fallback、cache 與 release-gate 沒完全跟上新架構。**

最危險的不是程式碼總行數，而是：

1. `MK.grade()` 還活在舊世界；
2. special grading 資料錯誤會被前端猜掉；
3. essay guide duplicate/source QA gate 還沒封死；
4. Service Worker 可能讓修好的 patch 到不了既有使用者；
5. manifest hash 目前只是「寫著有 hash」，不是「真的驗過 hash」。

只要正式施工先把這五條封住，平台的 correctness 風險會下降非常多。

---

# 八、本次沒有做的事

- 沒有修改 Netlify student-facing files。
- 沒有部署 production frontend。
- 沒有修改 Supabase schema / data。
- 對 Supabase 只做 read-only SQL inspection。
- 沒有把 speculative concern 當成 confirmed bug；例如 production DB 的 grading reset、analysis_completed_at、RLS / privileged RPC 權限經 live check 後都已從 bug 清單移除。
