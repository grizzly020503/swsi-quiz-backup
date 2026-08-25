# SWSI 公開前月更 Patch 設計

建立：2026-08-25

> 這是施工圖，不是已套用變更。建立本檔不觸發 Netlify production deploy。

## 原則

- 不加新功能，先修公開前 QA 已確認的 bug／可信度／資料可靠性問題。
- 學生端修改集中同一次月更，避免重複消耗 Netlify deploy credits。
- 每個 patch 都要能單獨驗收；任何核心流程失敗就回滾該段，不硬上。
- 官方題目與官方答案不因 AI 判斷而改動。

---

## Patch A — `index.html` 安全輸出

### A1. `renderQuiz()` 全部動態資料 escape

修改範圍：`renderQuiz()`。

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

新增共用 helper，非 2xx 時先嘗試 JSON：

- 有 `error.message` → 顯示該訊息
- `CLIENT_DAILY_QUOTA` / `GLOBAL_DAILY_QUOTA` → 不顯示立即重試
- 413 → 照片過大
- 502/503 → 稍後再試

驗收：分別模擬 client daily / global daily / rate limit / 502。

---

## Patch C — 照片 AI 收斂到 3 張

### C1. 前端

`gradePhoto()`：

- `files.length > 3` 時只取前三張，最好直接提示「一次最多 3 張」而不是默默切掉。
- input 可保留 `multiple`。
- 文案從「建議 1–3 張」改成「一次最多 3 張」。

### C2. Worker

- `imageCount > 3` → 400，訊息「最多一次上傳 3 張照片。」
- 公開模式 image_url 建議只允許前端實際會產生的 `data:image/jpeg;base64,`。
- 文字模式另設合理 request size／字數上限，避免所有請求都吃 4MB 上限。

原因：Qwen 3.6 官方模型頁標示 MAX INPUT IMAGES = 3；以較保守官方限制為準。

---

## Patch D — 模擬考未作答一致化

修改：`MK.grade()`。

目標：

- 未作答仍算 incorrect
- 未作答要進各科分母
- 未作答要進錯題／間隔複習排程
- UI 仍顯示「未作答」而不是偽裝成選錯某選項

注意：現行 `record(item,picked,correct)` 不會保存 picked，本身可接受 `null`；若未來要分析「漏答」，再另外新增欄位，不在本次擴充。

驗收：10 題只答 5 題交卷，總分／各科分母／錯題本三處應一致。

---

## Patch E — 搜尋 deep-link

修改：

- `openTheory(name)`
- `openLawCard(name)`

不要把 name 字串直接塞進目前以 index 判定的 `theoryOpen / lawOpen`。

建議：

```js
function openTheory(name){
  theoryQ=name;
  theoryOpen=THEORIES.findIndex(t=>t.n===name);
  go('theories');
}
function openLawCard(name){
  lawQ=name;
  lawOpen=LAWS.findIndex(l=>l.n===name);
  go('laws');
}
```

驗收：搜尋「增強權能」／「家庭暴力防治法」→ 點結果後直接看到展開內容。

---

## Patch F — 本機儲存可信度

### F1. 草稿顯示儲存狀態

`saveDraft()` 不再無聲 catch。

建議在 textarea 下方放：

- `已儲存在這台裝置`
- 或 `⚠ 無法儲存，請立即備份`

`saveHist()` / `saveReviewState()` 至少 console + 共用 storage warning flag，避免所有紀錄悄悄停止寫入。

### F2. 備份名稱說清楚

現有 TXT 按鈕可改：

> `匯出申論草稿（TXT）`

避免讓人誤會可一鍵還原。

### F3. 後續（非本次必做）

設計 JSON 匯出／匯入：

- drafts
- history
- review state
- font setting

原始 history 未來可做上限或彙總，避免無限成長。

---

## Patch G — 申論 AI 可信度與隱私

### G1. 移除過度承諾

Prompt：

> 「校過骨架（已人工核對的正確考點……）」

改成：

> 「平台提供的參考骨架與關鍵字」

AI 不得宣稱平台骨架皆經人工逐題核對。

### G2. 隱私文案

補一句：

> 「照片／文字會送至外部 AI 服務處理；請勿輸入或上傳可識別真實個案或個人的資料。」

保留既有「AI 回饋非官方評分」。

---

## Patch H — 首頁定位與 SEO

### H1. 首頁第一屏

保留「今天要練什麼？」行動導向，新增短句：

> **免費社工師國考學習平台**
> 歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。

### H2. Head

建議：

- title：`社工師國考免費題庫｜SWSI`
- meta description
- canonical
- og:title
- og:description
- og:type
- og:image（若已有可用分享圖才加，不臨時亂做）

---

## Patch I — 無障礙與色彩

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
- 答題後能讓讀屏知道正解／你選的

顏色：

- 小字 muted 加深
- pine 小字必要時用 `--pine-deep`
- `--ink-3` 不承擔重要文字
- 白字 + gold 實心背景重新調深

---

## Patch J — PWA cache version

只要本次改動包含 `essay_guides.js` 或其他 cache-first 靜態檔：

- bump `sw.js` VERSION
- 安裝新版 Service Worker 後刪舊 cache

驗收：

1. 舊 PWA 開啟
2. 上線新版
3. 重開／重新整理
4. 確認新 essay guide 能出現
5. 飛航模式重開，確認已下載題庫仍可進

---

## Patch K — Supabase AI queue 公平排序（獨立 migration 候選）

目前：

```sql
order by q.source_exam_code nulls last,
         q.subject,
         numeric_qno,
         q.id
```

候選：

```sql
order by q.source_exam_code nulls last,
         numeric_qno,
         q.subject,
         q.id
```

效果：同樣每日最多 25 題，但最新考次會大致五科平均消化，而不是一科做完才換下一科。

套用前：保留現行 function definition；用 migration 做，不直接臨時改 production。

驗收：下一個新考次前 25 題的 subject 分布應接近 5/5/5/5/5。

---

## Patch L — AI 解析品質閥門

### L1. 先修兩筆已確認資料

- `SP113-1-30`：移除錯誤「官方答案有瑕疵／D 其實為真」內容；D 把通常保護令有效期限誤寫成 5 年，因此官方 D 為錯誤選項並無問題。
- `SP105-1-31`：移除模型自我修正殘渣，直接解釋 B 把「以提供到宅托育為限」寫反成「不得提供到宅托育」。

### L2. 自動 quality report

不讓 AI 自動改官方答案，只報告：

- `exp_why` 開頭選項字母 ≠ official answer
- 解析出現「答案有瑕疵／官方答案／題庫正解／建議複查」
- ready 但 explanation/topic/mistake 空白

人工確認後才修改解析。

---

## 建議施工順序

1. 先備份目前 `index.html / worker.js / sw.js` SHA
2. Supabase queue migration 與解析資料修正獨立處理、獨立驗收
3. 在 GitHub 一次完成 `index.html` Patch A–I
4. Worker Patch C
5. `sw.js` bump version
6. diff review
7. Netlify production deploy 一次
8. 手機 Safari / Android Chrome / 桌面 Chrome smoke test
9. AI 文字 1 次、照片 1–3 張、quota 錯誤、模擬考未作答、搜尋 deep-link、離線 PWA逐項驗收

## 明確不做

- 不新增付費牆
- 不要求登入才能刷題
- 不增加每日打卡／連勝壓力
- 不為了『看起來厲害』新增更多首頁入口
- 不讓 AI 修改官方題目／官方答案
- 不因一筆解析爭議就批次重跑全部 4,800 題
