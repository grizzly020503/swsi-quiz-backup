# SWSI 高風險剩餘總盤點

日期：2026-08-26
狀態：`audit only / no student-facing changes`

> 本檔是 Batch 1–16 申論 QA 後的收斂盤點。目的不是繼續逐年暴力掃所有題，而是把已證實仍會直接影響學生答案／平台正確性的問題排優先序。

## 一、申論內容 QA 現況

### 已完成的高風險類型

1. **整題套錯 generic template**
   - 已透過 Batch 1–16 對大量明顯答非所問題建立逐題 verified payload。
   - 近期 115-1、114-2、114-1、113-2 已完成整屆或近完整逐題 QA；113-1 最高風險 5 題亦已完成 verified。

2. **歷史題倒灌後來政策／法律**
   - 長照3.0／2026內容倒灌104、105、107、112等舊題：已由 Batch 3、6、16 等鎖定歷史版本。
   - 104性平題倒灌2023後性平工作法：Batch 3 已處理。
   - 104社工安全題倒灌112年後我國修法：Batch 3 已改回 Lisa's Law 題意。
   - 112-1家暴法家庭成員：Batch 4 已鎖定112年12月6日前考試當時版本。
   - 兒少性剝削、老人福利法等法規題：相關 Batch 已建立考試時間版本鎖定。

3. **題目指定子問被 generic guide 吃掉**
   - 已針對抽樣、研究方法、社會政策、團體、家庭、發展、兒保／家暴、高齡等大量題建立 `guideMust / guideMustNot`。

### 本輪 marker scan 結論

- 目前 `essay_guides.js` 中最明顯的「帶明確後來年份」generic leakage 家族，已都有對應 audit 修正版。
- 暫未發現另一個可以在不重新逐題查考選部原題的情況下，直接判定為新 P0 的歷史倒灌家族。
- 因此不再把所有剩餘歷屆題一律升級成逐題重審；未被證實錯配者先視為 P1 / content-quality backlog，而不是 P0。

---

# 二、目前仍確定存在的 P0 結構性問題

## P0-1 `ESSAY_GUIDES` duplicate key 靜默覆蓋

### 已知案例
- `社會工作-107-1-申論2` 至少曾出現同一 object key 被定義成不同 guide 的情況。
- JavaScript object literal 對 duplicate key 不報錯，後值直接覆蓋前值，執行階段已無法看見被吃掉的版本。

### 風險
- audit 可能以為某題已修好，實際 bundle 最後載入的是另一個版本。
- 人工 review 很難發現。

### 正式施工要求
1. 建立 source lint，在 build／preview 前解析所有 essay guide key。
2. duplicate key > 0 直接 fail build / fail smoke。
3. 逐題 override 不再放進容易產生 duplicate literal key 的巨大單一 object；優先改用顯式 setter / registry，例如 `verified(id, payload)`，若 id 已存在就報錯或明確 override 並記錄來源。

---

## P0-2 特殊給分 `grading_mode` 缺失時仍會 legacy 猜測

### 現況
- Cloudflare preview / monthly patch 的 `gradingMode()` 尚保留 legacy fallback：可能根據舊題號或 `answer === '一律給分' / '送分'` 等字串猜特殊給分模式。

### 與 PROJECT_HANDOFF 衝突
- 已定案規則：特殊給分題若缺 `grading_mode` 必須 **fail closed**，不可猜。

### 風險
- 資料錯誤會被前端自動「合理化」，導致錯誤給分而不被發現。
- 題目文字／答案字串變化可能觸發錯誤模式。

### 正式施工要求
1. `grading_mode` 為特殊給分唯一 source of truth。
2. 特殊題缺 mode → 顯式資料錯誤／不可評分，不做 legacy guess。
3. 建 smoke：正常單選、複選、全給分、送分、缺 mode 五種案例。

---

## P0-3 首頁考試輪次 regression：`1/2` vs `第一次/第二次`

### 現況
- 原選單值使用 `1 / 2`。
- 底部 override 曾改成 `第一次 / 第二次`。
- `setHomeQuizRound()` 原樣保存字串，沒有 normalization。

### 風險
- query/filter/storage 可能拿到不同格式，造成題庫篩選失效或回到預設值。

### 正式施工要求
1. 內部 canonical value 統一成 `1 / 2`。
2. UI label 才顯示 `第一次 / 第二次`。
3. legacy storage 讀取時 normalization：`第一次 -> 1`、`第二次 -> 2`。
4. smoke：新舊 localStorage、首頁選擇、重新整理、開始測驗。

---

# 三、次優先但已證實的前端／API問題

## P1-1 申論照片數量前後端不一致
- 前端目前可默默截至4張；Worker限制3張。
- 要統一為同一上限，UI在選檔當下直接告知，不可 silent truncate。

## P1-2 搜尋 deep-link 名稱字串 vs render numeric index
- 搜尋點擊把 theory/law 名稱放入 `theoryOpen / lawOpen`。
- render端用 numeric index 比較，因此可能無法自動展開指定卡片。
- 要統一 identity（prefer stable id 或一致 index mapping）。

## P1-3 AI Worker client id／429訊息
- 前端 AI fetch 尚未送 `X-SWSI-Client-ID`。
- 429 UI把不同限制原因混成同一句且永遠顯示重試。
- 應讀 Worker `error.message`，區分 minute rate limit、daily quota 等。

## P1-4 localStorage 寫入失敗被吞掉
- `saveDraft()`、`saveHist()`、`saveReviewState()` 等已確認 catch 後不提示。
- 容量滿／隱私限制時，學生可能誤以為已儲存。
- 正式施工時需顯式 toast／fallback，並避免反覆噴訊息。

---

# 四、正式施工順序建議

1. **先修 P0-1 duplicate-key lint / registry**
2. **再修 P0-2 grading_mode fail-closed**
3. **再修 P0-3 exam round normalization**
4. 跑 Batch 1–16 essay smoke + grading smoke + round smoke
5. 再處理照片上限、deep-link、429/client id、localStorage錯誤提示
6. Cloudflare preview 全部驗收
7. 最後才進 Netlify 正式學生端

---

# 五、停止條件

除非後續 smoke、使用者回報或題幹抽查提出新證據，**不再為了追求「每題都看過」而把104–112全部逐題重審**。

下一階段的成功標準不是 audit 檔越多越好，而是：
- 沒有 duplicate key；
- 特殊給分不猜；
- 首頁輪次不 regression；
- 已 verified 的高風險申論確實在 preview 中命中；
- 正式站上線前 smoke 全綠。
