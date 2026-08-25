# SWSI 公開前月更 Patch 設計

建立：2026-08-25
最後更新：2026-08-25（Cloudflare 題庫 CDN 與官方 grading mode 後端完成；月底只切學生端）

> 這是施工圖，不是已套用前端變更。更新本檔不代表 Netlify production 已部署。

## 原則

- 不加新功能，先修公開前 QA 已確認的 bug／可信度／資料可靠性問題。
- 學生端修改集中同一次月更，避免重複消耗 Netlify deploy credits。
- 每個 patch 都要能單獨驗收；任何核心流程失敗就回滾該段，不硬上。
- 官方題目與官方答案不因 AI 判斷而改動。
- 2026-08-25 已完成的 Supabase / Cloudflare 後端修正，不要月底再重做。
- **Cloudflare 題庫 Static Assets / shard 後端已完成，不要另開 R2／第三個 Worker。**
- **特殊給分不得再從 `answer='一律給分'` 猜規則；一律使用 `grading_mode`。**

---

## Patch A — `index.html` 安全輸出

### A1. `renderQuiz()` 全部動態資料 escape

**狀態：待月底 Netlify。**

修改範圍：`renderQuiz()` 及其他直接把資料庫／AI 文字塞進 `innerHTML` 的區域。

需 escape：

- 題幹 `item.q`
- 四個選項 `item.options[k]`
- `item.exp.why / others / trap / raw`
- `item.mnemonic`
- `item.law`
- `item.topic / major`
- `item.mistake`
- 題目 meta 中的 subject / year / round

換行內容一律：`esc(text).replace(/\n/g,'<br>')`。

驗收：植入 `<img src=x onerror=alert(1)>` 測試字串，只能顯示文字。

---

## Patch B — AI 使用者識別與錯誤訊息

### B1. 新增匿名 client ID helper

**狀態：待月底 Netlify；Worker 已支援。**

建議：

```js
const AI_CLIENT_ID_KEY='swsi_ai_client_id_v1';
function getAIClientId(){
  try{
    let id=localStorage.getItem(AI_CLIENT_ID_KEY)||'';
    if(!/^[A-Za-z0-9_-]{16,128}$/.test(id)){
      id=(crypto.randomUUID?crypto.randomUUID():('swsi_'+Date.now()+'_'+Math.random().toString(36).slice(2)));
      localStorage.setItem(AI_CLIENT_ID_KEY,id);
    }
    return id;
  }catch(_e){
    return 'swsi_'+Date.now()+'_'+Math.random().toString(36).slice(2);
  }
}
```

文字與照片 AI fetch headers 加：

```js
'X-SWSI-Client-ID': getAIClientId()
```

### B2. 顯示 Worker 真實錯誤訊息

**狀態：待月底 Netlify。**

新增共用 helper，非 2xx 時先嘗試 JSON：

- 有 `error.message` → 顯示該訊息
- `CLIENT_DAILY_QUOTA` / `GLOBAL_DAILY_QUOTA` → 不顯示立即重試
- 413 → 照片過大
- 502/503 → 稍後再試

驗收：分別模擬 client daily / global daily / rate limit / 502。

---

## Patch C — 照片 AI 收斂到 3 張

### C1. 前端

**狀態：待月底 Netlify。**

`gradePhoto()`：

- `files.length > 3` 時直接提示「一次最多 3 張」，不要默默吞第 4 張。
- input 可保留 `multiple`。
- 文案從「建議 1–3 張」改成「一次最多 3 張」。

### C2. Worker

**狀態：✅ production 已完成且 runtime smoke 已驗；不要月底重做。**

正式 Worker 已實測：
- AI no-Origin POST → 403
- 正式 SWSI Origin + 非 JPEG `data:image/png` → 400
- 正式 SWSI Origin + 第 4 張 JPEG → 400
- 公開 image URL 只接受 JPEG data URL
- invalid image request 在 D1 quota / Groq 前拒絕
- 錯誤回應 CORS 只允許正式 SWSI Origin

因此月底只補學生端 3 張限制與錯誤顯示，不再改 Worker guard。

---

## Patch D — 模擬考未作答依 `grading_mode` 一致化

**狀態：P0，待月底 Netlify。**

修改：`MK.grade()` 及共用判題 helper。

Production 官方給分模式已驗：

| `grading_mode` | 題數 | A-D 作答 | 未作答 |
|---|---:|---|---|
| `standard` | 4,784 | 依單／多答案集合判定 | incorrect |
| `all_credit` | 12 | correct | **correct** |
| `any_answer` | 4 | correct | **incorrect** |

目標：

- 每一題都進各科分母，不因未作答而消失。
- 統一使用 `isCorrectAnswer(item,picked)`，不要在 `MK.grade()` 再寫第二套判題。
- `standard` / `any_answer` 未作答才進錯題／間隔複習。
- `all_credit` 未作答仍得分，**不得污染錯題本**。
- UI 一律保留「未作答」狀態，再另外說明官方特殊給分結果。

驗收至少要同場包含：普通題、多答案、`all_credit` 空白、`any_answer` 空白；總分／各科分母／history／錯題／review schedule 必須一致。

---

## Patch E — 搜尋 deep-link

**狀態：待月底 Netlify。**

修改：

- `openTheory(name)`
- `openLawCard(name)`

不要把 name 字串直接塞進目前以 index 判定的 `theoryOpen / lawOpen`。

驗收：搜尋「增強權能」／「家庭暴力防治法」→ 點結果後直接看到展開內容。

---

## Patch F — 本機儲存可信度

**狀態：待月底 Netlify。**

### F1. 草稿顯示儲存狀態

`saveDraft()` 不再無聲 catch。

顯示：
- `已儲存在這台裝置`
- 或 `⚠ 無法儲存，請立即備份`

`saveHist()` / `saveReviewState()` 至少設共用 storage warning flag。

### F2. 備份名稱說清楚

現有 TXT 按鈕改為：

> `匯出申論草稿（TXT）`

### F3. 後續（非本次必做）

JSON 匯出／匯入：drafts、history、review state、font setting。

---

## Patch G — 申論 AI 可信度與隱私

**狀態：待月底 Netlify。**

### G1. 移除過度承諾

將「校過骨架（已人工核對的正確考點……）」改成：

> 「平台提供的參考骨架與關鍵字」

### G2. 隱私文案

補：

> 「照片／文字會送至外部 AI 服務處理；請勿輸入或上傳可識別真實個案或個人的資料。」

保留「AI 回饋非官方評分」。

---

## Patch H — 首頁定位與 SEO

**狀態：待月底 Netlify。**

### H1. 首頁第一屏

保留「今天要練什麼？」行動導向，新增：

> **免費社工師國考學習平台**  
> 歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。

### H2. Head

- title：`社工師國考免費題庫｜SWSI`
- meta description
- canonical
- og:title
- og:description
- og:type
- og:image（有正式分享圖才加）

---

## Patch I — 無障礙與色彩

**狀態：待月底 Netlify。**

優先順序：

1. 一般刷題 `.opt`
2. 模擬考 `.mk-opt`
3. A/A/A 字級鈕 aria-label
4. select/input label / aria-label
5. 搜尋卡片與其他 `div onclick`

作答選項至少需：
- 可 Tab 到
- Enter / Space 可選
- 有 radio / selected 語意
- 答題後讓讀屏知道正解／你選的

---

## Patch J — PWA cache version

**狀態：月底前端施工時一起做。**

只要本次改動包含 `essay_guides.js`、題庫讀取方式或其他 cache-first 靜態檔：

- bump `sw.js` VERSION
- 安裝新版 Service Worker 後刪舊 cache

驗收：
1. 舊 PWA 開啟
2. 上線新版
3. 重開／重新整理
4. 確認新內容
5. 飛航模式重開，確認已下載內容可進

---

## Patch K — Supabase AI queue 公平排序

**狀態：✅ production 已完成，不是月底工作。**

目前 production：

```sql
order by q.source_exam_code nulls last,
         numeric_qno,
         q.subject,
         q.id
```

每日最多 25 題不變，但最新考次跨科目較平均消化。

---

## Patch L — AI 解析品質閥門與特殊給分隔離

**狀態：✅ 後端已完成；月底只需前端顯示相容。**

已完成：

- 舊錯誤解析已清理／重排
- 24 官方多答案題隔離 `review`
- 16 官方特殊給分題隔離 `review`：**12 `all_credit` + 4 `any_answer`**
- DB trigger `trg_reject_ai_answer_meta_commentary`
- 官方內容異動 trigger 已把 `grading_mode` 納入 AI reset
- 禁止 ready 解析含「題庫答案／官方答案／答案待查／建議查答案」等 meta 話術
- ready meta 污染驗收為 0
- analyzer production v7 支援 `accepted_answers`
- importer production v4 fail-closed 驗證 `grading_mode`

不要再批次重跑 4,800 題。

---

## Patch M — 官方多答案 + 特殊給分前端統一支援

**狀態：P0，待月底 Netlify。**

資料庫／官方 audit 已完成：
- 24 題 `accepted_answers`
- grading mode：4,784 `standard` / 12 `all_credit` / 4 `any_answer`
- official answer findings：0
- official grading-mode mismatches：0

`normalize()` 必須同時保留：

```js
accepted_answers: Array.isArray(r.accepted_answers)
  ? r.accepted_answers.filter(x=>['A','B','C','D'].includes(x))
  : null,
grading_mode: ['standard','all_credit','any_answer'].includes(r.grading_mode)
  ? r.grading_mode
  : (r.answer==='一律給分' ? 'unknown' : 'standard'),
```

判題不得再用 `item.answer==='一律給分'` 猜特殊模式。建議共用：

```js
function acceptedAnswers(item){
  const mode=gradingMode(item);
  if(mode==='all_credit' || mode==='any_answer') return new Set(['A','B','C','D']);
  if(Array.isArray(item.accepted_answers) && item.accepted_answers.length){
    return new Set(item.accepted_answers.filter(x=>['A','B','C','D'].includes(x)));
  }
  return ['A','B','C','D'].includes(item.answer) ? new Set([item.answer]) : new Set();
}

function isCorrectAnswer(item,picked){
  const mode=gradingMode(item);
  if(mode==='unknown') return false;
  if(mode==='all_credit') return picked==null || acceptedAnswers(item).has(picked);
  return picked!=null && acceptedAnswers(item).has(picked);
}
```

需檢查：
- 一般刷題
- 指定歷屆
- 錯題本
- 間隔複習
- 模擬考
- 結果頁正解顯示
- 弱點／正確率統計

UI：
- 多答案：`官方可接受答案：B、C`
- `all_credit`：`官方一律給分（未作答也得分）`
- `any_answer`：`官方規則：除未作答者不給分外，其餘均給分`
- 特殊給分題不要把 A-D 四個都塗綠，避免暗示「四個學理都正確」。

驗收：
- 24 多答案逐題 accepted option 都正確
- 12 `all_credit`：A-D 與未作答都正確
- 4 `any_answer`：A-D 都正確、未作答錯誤

4 題 `any_answer`：
- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

---

## Patch N — Cloudflare 題庫 CDN / exam-session shard

**狀態：✅ 後端 production 已完成；月底只做前端 loader 切換。**

已完成架構：

> Supabase = 後台 source of truth  
> GitHub Actions = 產生／驗證靜態 exam-session shard  
> Cloudflare Static Assets = CDN cache  
> Netlify 前端 = 月底改成依需求載入 shard

目前 production：
- 4,800 題
- 24 baseline shards（104-1 ～ 115-2）
- 每 shard 200 題
- revision：`e721d6293d4c6acdddee`
- 約 6.84 MB 未壓縮總量
- 單 shard 約 193–301 KB
- 24 多答案完整保留
- `grading_mode` 完整保留：4,784 `standard` / 12 `all_credit` / 4 `any_answer`

Runtime 已驗：
- manifest HTTP 200
- 115-2 shard HTTP 200／200 題
- `CF-Cache-Status: HIT`
- 單一 `Access-Control-Allow-Origin: *`
- `Cache-Control: public, max-age=300, must-revalidate`
- `X-Content-Type-Options: nosniff`
- AI root no-Origin POST 仍 403
- AI 非 JPEG / 第 4 張照片 guard 皆 production smoke 通過

自動化：
- `scripts/build_question_shards.py`
- `.github/workflows/question-shards-build.yml`
- `.github/workflows/question-shards-publish.yml`
- 台灣時間每日約 11:10
- dataset/header 不變 → 零 commit
- 新考次不完整 → fail closed，不發布半套
- 完整 116、117…考次自動新增 shard，不需每年改程式
- 模擬 116-1 → 5,000 題／25 shards／`116-1.json` success

月底前端修改：
- 先讀 `/question-shards/manifest.json`
- 指定歷屆只載該考次 200 題
- 其他需要跨考次的功能按實際需求載入／快取 shard
- 沿用現有 `normalize(r)`，但補 `accepted_answers` + `grading_mode`
- 保留 Supabase / IndexedDB 作必要 fallback，不再讓每位學生冷啟動都先下載整套 4,800 題

驗收：
- 首頁不先下載 4,800 題整包
- 進某考次只載必要 shard
- Cloudflare cache hit 正常
- Supabase public egress 明顯下降
- PWA 已下載的題目仍可離線使用

**不要重建 CDN、不要另開 R2、不要另建第三個 Worker。**

---

## Patch O — 最新申論 PDF 私用字元

**狀態：待月底同包。**

`E-115-2-R-1` 仍有 `  ` 私用字元；不同手機／字型可能變方框。

改成穩定的 `(一) (二) (三)` 或一般 Unicode 編號，並同步：
- source parser 清理規則
- `auto/essays_auto.json`
- PWA cache version

不要為這一題單獨觸發 Netlify deploy。

---

## 建議施工順序

1. **Cloudflare 題庫 CDN / shard 與 grading-mode 後端已完成，不要重做**
2. 到約定月更時，先備份目前 `index.html / sw.js / manifest.json` SHA
3. **先修指定歷屆 round canonical regression**
4. 補 `normalize().accepted_answers + grading_mode`
5. 建立統一 `gradingMode / acceptedAnswers / isCorrectAnswer / answerLabel`
6. 同輪改一般刷題 + `MK.grade()` + grading-mode 未作答規則
7. 切換 Patch N 的 CDN manifest/shard loader + scope/full-bank gate
8. 修底部 `renderHome / renderReview` override
9. 再完成 Patch A、B、C1、E、F、G、H、I、O
10. bump `sw.js` VERSION
11. 全文 grep 第二套判題／XSS／後置 override
12. diff review
13. Netlify production deploy **一次**
14. 手機 Safari / Android Chrome / 桌面 Chrome smoke test
15. 驗收：
   - 首頁／一般刷題
   - 24 多答案
   - 12 `all_credit`（含空白仍得分）
   - 4 `any_answer`（含空白不得分）
   - 指定歷屆只抓對應 shard
   - 錯題／間隔複習
   - 搜尋 deep-link
   - 申論文字 AI
   - 申論照片 1–3 張／第 4 張拒絕
   - quota 錯誤訊息
   - 題庫 CDN cache
   - 離線 PWA

## 明確不做

- 不新增付費牆
- 不要求登入才能刷題
- 不增加每日打卡／連勝壓力
- 不為了「看起來厲害」新增更多首頁入口
- 不讓 AI 修改官方題目／官方答案
- 不因一筆解析爭議就批次重跑全部 4,800 題
- 不在月底重做已完成的 Supabase queue／多答案 DB／grading mode／法規 mapping／AI meta trigger
- 不在月底重做 Cloudflare Static Assets / shard builder / publish workflow
