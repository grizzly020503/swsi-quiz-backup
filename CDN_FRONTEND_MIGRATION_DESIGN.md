# SWSI 題庫 CDN — 前端月更切換設計

建立：2026-08-25
狀態：**設計完成，尚未修改 `index.html` / `sw.js` / Netlify production**

> 目的：月底一次施工時，讓學生端真正吃已上線的 Cloudflare exam-session shards，同時盡量不重寫既有 `ALL` / 刷題 / 錯題 / 模擬考架構。

---

## 1. 已完成的後端前提（不要重做）

Cloudflare Static Assets 已 production/runtime 驗收：

- `/question-shards/manifest.json`
- `/question-shards/104-1.json` … `/question-shards/115-2.json`
- 4,800 題 / 24 shards / 每 shard 200 題
- dataset revision：`8dafaf049f5200b54cd8`
- 24 題 `accepted_answers` 保留
- 16 題「一律給分」保留
- CORS / cache headers 正常
- AI Worker root 仍正常受 Origin guard 保護
- builder 會在完整 116、117…考次出現時自動增加 shard
- incomplete 新考次 fail closed

因此月底**只切 frontend loader**，不要另開 R2、不要另建 Worker、不要重新切資料。

---

## 2. 現行前端為什麼不能直接把 Supabase URL 換成 CDN URL

目前 `init()`：

```text
init()
  → loadAll()
      → Supabase 1000 題一頁抓到 4,800
      → merge auto/questions_auto.json
      → ALL = out.map(normalize)
      → saveOfflineQuestions(out)
  → loadAutoEssays()
  → go('home')
```

所以首頁**一定等 4,800 題全部抓完**才會出現。

而且大量功能直接假設 `ALL` 是完整題庫：

- `maxExamYear()`
- `kpFreq()` / 出題權重
- `startQuiz()`
- `examYears()`
- `focusedQuizFilter()`
- `reviewSummary()`
- 全域搜尋 `searchAll()`
- 考點／理論 MCQ count
- 模擬考 `bank()` / `papers()` / `buildExam()`

因此不可以只把 `ALL` 改成單一 shard 而不處理上述依賴。

---

## 3. 推薦架構：Manifest-first + Scope-on-demand + `ALL` 相容橋

### 核心原則

1. **首頁不再等待 4,800 題。**
2. manifest 先提供「總題數、年份、考次、shard file」等 catalog 資訊。
3. 使用者真的要刷某個範圍時，再下載該範圍需要的 shards。
4. 已下載 shard 合併進既有 `ALL`，讓大部分既有題庫邏輯繼續用。
5. 需要全庫的功能（搜尋、考點統計、模擬考、錯題複習）進入時才 `ensureAllQuestionsLoaded()`。
6. 每 shard 同步存 IndexedDB；離線時可讀已快取 shard。
7. Supabase 保留為 CDN 故障時的 fallback，不再是每位學生的正常冷啟動來源。

### 資料流

```text
開站
  ↓
Cloudflare manifest（約幾 KB）
  ↓
立即 render 首頁
  ↓
使用者選動作
  ├─ 指定 115 第二次 → 只載 115-2.json（200 題）
  ├─ 指定 115 全部 → 115-1 + 115-2（400 題）
  ├─ 近 3 年 → 6 shards
  ├─ 近 5 年 → 10 shards
  ├─ 智慧推薦 → 最近 10 年所需 shards
  └─ 全庫搜尋／考點／模擬考／複習 → ensureAll → 24 shards
```

這樣「指定歷屆」能得到最大的實際效益，而不需要一次重寫整站。

---

## 4. 建議新增的前端狀態

概念上新增：

```js
const QUESTION_CDN_BASE='https://wandering-wave-4418.c022050333.workers.dev/question-shards';
const CORE_SUBJECTS=[
  '社會工作',
  '社會工作直接服務',
  '社會政策與社會立法',
  '人類行為與社會環境',
  '社會工作研究方法'
];

const QB={
  manifest:null,
  loadedFiles:new Set(),
  loading:new Map(),
  allComplete:false,
  usingOffline:false
};
```

`SUBJECTS` 在 manifest-only 首頁階段可先由 `CORE_SUBJECTS` 初始化。

理由：現行社工師選擇題就是這 5 科；若未來國考科目制度真正改動，MOEX parser / DB schema / UI 本來就需要另一次制度級更新，不應為此讓現在首頁再強制下載 200 題只為取得科目名稱。

---

## 5. Manifest helper

### `loadQuestionManifest()`

正常路徑：

```text
Cloudflare manifest
  → validate schema/shards/count
  → IndexedDB save `question-manifest`
  → QB.manifest
```

失敗：

```text
IndexedDB `question-manifest`
  → 若存在就離線啟動
  → 再沒有才走 legacy full-cache / Supabase fallback
```

最低驗證：

- `schema_version === 1`
- `Array.isArray(shards)`
- `shard_count === shards.length`
- `total_questions === shard_count * 200`
- 每 meta 有 `year / round / file / question_count / sha256`
- `question_count === 200`

### 首頁 meta helper

不要再用 `ALL.length` 顯示總題數：

```js
function questionTotal(){
  return QB.manifest?.total_questions || ALL.length;
}
```

`examYears()` 優先從 manifest shards 取，不再要求 `ALL` 完整。

`maxExamYear()` 同理優先用 manifest。

---

## 6. Shard loader

### `loadQuestionShard(meta)`

優先順序：

```text
1. memory：QB.loadedFiles 已有 → 直接回
2. Cloudflare `${QUESTION_CDN_BASE}/${meta.file}`
3. IndexedDB `question-shard:${meta.file}`
4. Supabase scoped fallback（只查 meta.year + meta.round）
5. 都失敗 → 明確錯誤
```

成功後驗證：

- payload year / round 與 meta 相同
- `question_count === 200`
- `questions.length === 200`
- 每題 id 不空白
- 不允許同 ID 重複

之後：

```text
raw questions
  → normalize()
  → dedupe by id
  → append 到 ALL
  → QB.loadedFiles.add(file)
  → IndexedDB save shard
  → invalidate ALL-dependent caches
```

### cache invalidation

每新增 shard 後至少清：

```js
window._kpF=null;
window._kpFmax=1;
window._tmc={};
window._cmc={};
```

`maxExamYear()` 改看 manifest 後，不再依賴 `_maxY` 從部分 `ALL` 推算。

---

## 7. Scope → shards 對應

新增：

```js
function shardMetasForHomeScope(){ ... }
```

規則：

### specific

- year + round=1/2 → 1 shard
- year + round=all → 該年 2 shards

### recent3

- manifest 最新年度往前 3 年 → 6 shards

### recent5

- 最新年度往前 5 年 → 10 shards

### smart

現行智慧推薦規則是「最近 10 年」。因此先載最近 10 年對應 shards，再執行原本 `focusedQuizFilter()` / 權重。

### all

全部 manifest shards。

---

## 8. `startFocusedQuiz()` 改成 async gate

目前：

```js
function startFocusedQuiz(){
  const pool=ALL.filter(focusedQuizFilter);
  ...
}
```

月底建議：

```text
startFocusedQuiz()
  → 顯示「正在準備這組題目」
  → await ensureShardMetasLoaded(shardMetasForHomeScope())
  → 再跑原本 pool / startQuiz 邏輯
```

這是最重要的一個切點。

**指定歷屆 115-2 因此只需下載 1 個約 193 KB shard，而不是 4,800 題。**

---

## 9. 哪些功能進入前先確保全庫

為了月更一次成功，不要第一版就把每個功能都改成超細粒度查 shard。

### 第一版直接 `ensureAllQuestionsLoaded()` 的功能

- `go('search')`
- `go('topics')`
- `go('review')`
- `go('progress')`（若頁面會呼叫 `reviewSummary()` / ALL-derived data）
- `MK.open()` 模擬考
- `startDueReview()`

理由：這些功能本來就有跨年度／全庫統計語意；使用者主動打開時再載全庫，比在首頁冷啟動就載合理。

### 不需要全庫

- 首頁
- 申論首頁／申論寫作
- 時事庫
- 讀書指南
- 指定歷屆刷題
- 近 3 / 5 年刷題
- 智慧推薦只需現行規則所需最近 10 年 shards

---

## 10. `reviewSummary()` 的部分載入問題

現在：

```js
const exists=new Set(ALL.filter(...).map(q=>q.id));
```

若 `ALL` 只有部分 shard，會把尚未載入的舊錯題誤當「不存在」。

月底改成：

```text
若 QB.allComplete === true
  → 沿用 exists filter
若 QB.allComplete === false
  → 不用部分 ALL 去刪 review state
```

首頁因此仍能顯示「今天有幾題到期」。

使用者點「今日複習」時：

```text
await ensureAllQuestionsLoaded()
→ 再依 due IDs startQuiz
```

這是第一版最保守、最不容易丟錯題的做法。

之後如果真的需要再優化成「只載含 due IDs 的 shards」，可以另做；公開前不必增加風險。

---

## 11. 模擬考

目前 `MK.bank()` 直接回 `ALL`，`papers()` 也由 `ALL` 建歷屆清單。

第一版最低風險：

```text
MK.open()
  → await ensureAllQuestionsLoadedWithUI()
  → mount()
  → setup()
```

這樣 `MK` 內部絕大多數程式不用重寫。

指定歷屆模擬考未來可以再優化為只載單一 shard，但不是公開前必要 P0。

---

## 12. `normalize(r)` 必修：帶入 `accepted_answers`

現行 `normalize()` 把 DB row 轉成前端 object 時漏掉 `accepted_answers`。

月底至少改：

```js
accepted_answers: Array.isArray(r.accepted_answers) ? r.accepted_answers : null,
```

然後所有判題都統一呼叫一個 helper，不要每個畫面自己判：

```js
function acceptedAnswers(item){
  if(item.answer==='一律給分' || /送分/.test(String(item.answer||''))){
    return new Set(['A','B','C','D']);
  }
  if(Array.isArray(item.accepted_answers) && item.accepted_answers.length){
    return new Set(item.accepted_answers);
  }
  return new Set([item.answer]);
}

function isCorrectAnswer(item,picked){
  return !!picked && acceptedAnswers(item).has(picked);
}
```

一般刷題與 `MK.grade()` 都必須使用同一 helper。

---

## 13. IndexedDB 相容策略

現有：

- DB：`swsi-quiz-offline`
- version：1
- store：`cache`
- key：`questions`
- value：`{rows, savedAt}`

**不需要立刻升 DB version／建新 object store。**

直接在同一 `cache` store 增加 key：

```text
question-manifest
question-shard:104-1.json
question-shard:104-2.json
...
```

每 shard record：

```js
{
  rows:[...],
  file:'115-2.json',
  sha256:'...',
  savedAt:Date.now()
}
```

### Legacy `questions` key

不要刪。

用途：

1. 舊使用者已存在完整離線題庫，可繼續救援。
2. manifest + shard 全部失敗時，最後 fallback。
3. 當本次 session 最終載滿全部 shards 時，可順手再寫一次完整 `questions`，維持向下相容。

---

## 14. 離線行為

Cloudflare CDN 是跨 Netlify origin，現行 `sw.js` 不會攔截它；這是正確的，不要硬把跨域題庫塞進 Service Worker shell cache。

題庫離線由 IndexedDB 負責：

- 已看過／載過的 shard 可離線再開
- 有舊完整 `questions` cache 的使用者仍可完整離線
- 若某 shard 從未下載，離線時不能假裝有資料

首頁離線提示文案因此不要再保證「完整題庫」；建議改為：

> 「目前使用這台裝置已快取的題庫資料；恢復網路後可同步其他考次與最新內容。」

若公開後真的需要「一鍵下載完整離線題庫」，再另做明確按鈕，不要偷偷在行動網路背景下載 6.84 MB。

---

## 15. Supabase fallback

不要刪掉 `fetchQuestionPage()`，但把它降級成救援路徑。

建議新增 scoped fallback：

```text
fetchSupabaseExamSession(year, round)
```

只在 Cloudflare + IndexedDB shard 都失敗時查該 200 題。

只有以下極端狀況才回到現行完整 `loadAllFromSupabase()`：

- manifest 取不到
- manifest cache 也沒有
- legacy offline cache 也沒有

如此即使 Cloudflare 暫時故障，平台仍不會整站死掉。

---

## 16. `auto/questions_auto.json` 的處理

CDN builder 已直接讀 production Supabase，且每天約 11:10 接在 MOEX 10:35 同步之後。

因此學生端切 CDN 後：

- **CDN 是正常題庫主來源**
- `auto/questions_auto.json` 不應再在首頁無條件混進部分 `ALL`，否則會破壞「目前載入哪些 scope」的可預測性
- 可保留為短暫同步延遲／舊版相容 fallback，但只在有明確完整考次驗證時使用

第一版最安全做法：正常 CDN 路徑不 merge auto MCQ；Supabase / auto 僅作 fallback。`auto/essays_auto.json` 與選擇題 loader 無關，可繼續目前邏輯。

---

## 17. 首頁需要改的幾個依賴

### 題數 chip

現在：`ALL.length`

改：`questionTotal()`。

### 年份 dropdown

現在：`examYears()` 掃 `ALL`

改：優先由 manifest shards 取年份。

### `maxExamYear()`

改：優先由 manifest 最新年份。

### SUBJECTS

manifest-only 階段用 `CORE_SUBJECTS`。

### review

部分資料時不以 `ALL` 判斷 review item 是否存在；點入複習再 ensureAll。

---

## 18. 載入 UI

不要再顯示：

> 已載入 1000 / 2000 / 3000…題

改成使用者任務導向：

- 首頁啟動：`正在讀取題庫目錄…`
- 指定歷屆：`正在準備 115 年第二次題目…`
- 智慧推薦：`正在準備最近 10 年題庫…`
- 全庫功能：`正在準備完整題庫，第一次可能需要幾秒…`
- 離線：`正在開啟這台裝置已快取的題庫…`

不要讓基礎設施術語（shard、CDN、Supabase）出現在一般學生畫面。

---

## 19. 並行與去重

`loadQuestionShard(file)` 要有 in-flight promise map：

```js
QB.loading.set(file,promise)
```

同一 shard 被兩個功能同時要求時，只發一個 request。

合併 `ALL` 必須以 `id` dedupe，避免：

- shard 重載
- Supabase fallback
- legacy cache

造成同題重複。

---

## 20. 月底施工順序（精確）

### Phase 0 — 備份

記錄修改前：

- `index.html` SHA
- `sw.js` SHA
- `manifest.json` SHA

### Phase 1 — 只改 loader infrastructure

新增：

- `QB`
- manifest load/cache
- shard load/cache
- scope→shard mapping
- `ensureShardMetasLoaded()`
- `ensureAllQuestionsLoaded()`
- Supabase scoped fallback
- `questionTotal()` / manifest-based years

先不碰判題。

### Phase 2 — 接入既有入口

- `init()`：manifest-first，不再 await 4,800 Supabase
- `startFocusedQuiz()`：scope-on-demand
- `go(search/topics/review/progress)`：必要時 ensureAll
- `startDueReview()`：ensureAll
- `MK.open()`：ensureAll

### Phase 3 — 多答案

- `normalize()` 補 `accepted_answers`
- 共用 `acceptedAnswers()` / `isCorrectAnswer()`
- 一般刷題
- 模擬考
- 錯題／統計／結果 UI

### Phase 4 — 同包其他公開前 patch

依 `MONTHLY_PATCH_PLAN.md`：

- XSS escape
- Client-ID
- quota message
- 模擬考未作答
- deep-link
- storage warning
- AI 文案／隱私／3 張
- 免費定位／SEO
- accessibility
- `E-115-2-R-1` 私用字元

### Phase 5 — PWA

- bump `sw.js` VERSION
- 不把 Cloudflare shards 加入同網域 SHELL
- 確認 IndexedDB fallback

### Phase 6 — 一次 deploy

- diff review
- Netlify production deploy **一次**

---

## 21. 月底必測矩陣

### 冷啟動

- 新瀏覽器首次開首頁：不應先打 Supabase 4,800 題
- manifest 成功後首頁可先出現

### 指定歷屆

- 115 第二次 → 只要求 `115-2.json`
- 115 全部 → `115-1.json` + `115-2.json`
- 題數／科目／順序正確

### 智慧推薦

- 載入最近 10 年需要的 shards
- 不抽被確認已修法題
- 權重仍正常

### 全庫功能

- 搜尋完整
- 考點／理論 MCQ count 完整
- 模擬考 papers 完整
- review due 題不消失

### 多答案

24 題逐題：
- 任一 accepted answer → correct
- 非 accepted → wrong
- UI 顯示完整官方可接受答案

### 一律給分

16 題：A/B/C/D 任一選項都算 correct；不要把「四個選項都學理正確」寫進解析。

### fallback

- Cloudflare manifest 失敗 + IDB manifest 有 → 可啟動
- 某 shard Cloudflare 失敗 + IDB shard 有 → 可做題
- Cloudflare shard + IDB shard 都沒有 → scoped Supabase fallback
- 全部遠端失敗 + legacy full cache 有 → 可離線

### PWA

- 在線使用一個考次 → 關網路 → 該已快取考次可再進
- 舊版已有完整 offline `questions` 的使用者不被 migration 弄壞

### 效能

用 Network 面板確認：
- 首頁冷啟動沒有 `/rest/v1/questions?select=*` 4,800 全庫流量
- 指定歷屆沒有偷偷下載 24 shards
- 同 shard 不重複請求

---

## 22. 不做的事

- 不把 24 shards 重新拆一套新 schema
- 不另開 R2
- 不另建第三個 Worker
- 不讓 frontend 直接修改 Supabase
- 不刪 legacy offline cache
- 不在第一版為每個 due review ID 做複雜 shard index
- 不為了「完全 lazy」重寫所有 `ALL`-based 功能
- 不在月底拆成多次 Netlify deploy

---

## 23. 最終判斷

對目前這個單檔前端而言，**最安全的公開前改法不是全面改成 reactive / virtual data store，而是讓 CDN loader 逐步把需要的資料注入既有 `ALL`。**

這能同時做到：

- 首頁不再被 4,800 題阻塞
- 指定歷屆真的只載 1–2 shards
- Supabase 不再承受每位學生的正常題庫 egress
- 既有刷題／權重／模擬考／錯題邏輯大部分保留
- 離線 fallback 不必整套推翻
- 月底一次 deploy 的風險可控
