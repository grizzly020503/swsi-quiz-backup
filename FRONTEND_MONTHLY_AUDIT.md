# SWSI 月底前端稽核補充

建立：2026-08-25
狀態：**只做 code audit，尚未修改 `index.html` / Netlify**

搭配閱讀：
- `CDN_FRONTEND_MIGRATION_DESIGN.md`
- `MONTHLY_PATCH_PLAN.md`

---

## 1. 重要：`index.html` 有 UI/UX V1 後置 override

檔案前段雖然已有 `renderHome()` / `renderReview()`，但檔案底部 `swsi-uiux-v1-script` **再次覆寫**：

- `renderHome=function(){...}`
- `renderReview=function(){...}`

因此月底修改時：

> **不能只修前面的原始 function。必須以最後實際生效的 override 為準，或把重複邏輯收斂成單一 implementation。**

目前底部新版 `renderHome()` 仍使用：

```js
ALL.length
```

顯示題數。

CDN manifest-first 後必須改成 `questionTotal()`，否則首頁在尚未載 shard 時會顯示 0 / 部分題數。

目前底部新版 `renderReview()` 仍使用：

```js
ids.map(id => ALL.find(q => q.id===id)).filter(Boolean)
```

若 `ALL` 尚未完整，舊錯題會暫時消失。因此進入 review 前必須 `ensureAllQuestionsLoaded()`，或 renderReview 明確處理 partial bank。

底部新版首頁「計時模擬考」仍直接：

```html
onclick="MK.open()"
```

所以 `MK.open()` 本身要成為 async full-bank gate，不能只改首頁某一個按鈕。

---

## 2. 現行判題 helper 本身不支援多答案

目前：

```js
function isGiveAll(a){
  a=(a==null?"":String(a));
  return a.indexOf("一律給分")>=0||a.indexOf("送分")>=0;
}
function ansCorrect(p,a){
  return p===a||isGiveAll(a);
}
```

問題：只接受單一 `answer` 字串；完全不知道 `accepted_answers`。

月底不要再擴充 `ansCorrect(p,a,accepted)` 這種易漏參數方式。

建議收斂成 item-based helper：

```js
function acceptedAnswers(item){
  if(!item) return new Set();
  if(isGiveAll(item.answer)) return new Set(['A','B','C','D']);
  if(Array.isArray(item.accepted_answers) && item.accepted_answers.length){
    return new Set(item.accepted_answers);
  }
  return new Set(item.answer?[item.answer]:[]);
}

function isCorrectAnswer(item,picked){
  return !!picked && acceptedAnswers(item).has(picked);
}
```

所有畫面只呼叫這兩個 helper。

---

## 3. `normalize()` 漏掉 `accepted_answers`

現行 normalized question object 有：

- id / subject / year / round / qno
- question/options
- `answer`
- exp / mnemonic / law / mistake / legal status

但沒有 `accepted_answers`。

月底至少補：

```js
accepted_answers: Array.isArray(r.accepted_answers)
  ? r.accepted_answers.filter(x=>['A','B','C','D'].includes(x))
  : null,
```

不要在 frontend 自己猜官方多答案；只讀 DB/CDN 已稽核的 metadata。

---

## 4. 一般刷題共有三個多答案漏點

### 4.1 選項綠框

目前：

```js
if(answered){
  if(k===item.answer || (isGiveAll(item.answer)&&k===selected)) cls+=' correct';
  else if(k===selected) cls+=' wrong';
}
```

多答案題若官方 B/C 都可，主 `answer=B`，學生選 C：現在 C 仍會被畫成 wrong。

改成：

```js
const accepted=acceptedAnswers(item);
if(answered){
  if(accepted.has(k)) cls+=' correct';
  else if(k===selected) cls+=' wrong';
}
```

送分題可考慮只把使用者選的那個標成「送分」，避免四個選項全部綠造成「四個都學理正確」的錯誤暗示。

### 4.2 「正解」marker

目前也是直接 `k===item.answer`。

多答案題應：

- accepted option 都可標 `官方答案`
- 或只在選項下方統一顯示 `官方可接受答案：B、C`

建議後者較不亂。

### 4.3 submit / wrong topic

目前：

```js
const correct=ansCorrect(selected,item.answer);
```

必須改：

```js
const correct=isCorrectAnswer(item,selected);
```

否則多答案題會被錯誤寫進：

- history
- review schedule
- weak topics
- 正確率

這不是只有 UI 顏色問題，而會污染學習紀錄。

---

## 5. 一般刷題解析區的答案文案

目前沒有解析時顯示：

```text
正確答案是 ${item.answer}
```

多答案題必須顯示完整集合，例如：

```text
官方可接受答案：B、C
```

建議新增：

```js
function answerLabel(item){
  if(isGiveAll(item.answer)) return '一律給分';
  const xs=[...acceptedAnswers(item)];
  return xs.length>1 ? `官方可接受答案：${xs.join('、')}` : `正確答案：${xs[0]||'—'}`;
}
```

結果頁與解析區都用同一 helper。

---

## 6. 模擬考計分是另一套獨立判定，必須一起改

目前 `MK.grade()`：

```js
var ok=picked!=null && (
  picked===q.answer ||
  /一律給分|送分/.test(String(q.answer||''))
);
```

這不會走一般刷題 `ansCorrect()`，所以只修 `ansCorrect()` **完全不夠**。

必須改成：

```js
var ok=picked!=null && isCorrectAnswer(q,picked);
```

---

## 7. 模擬考結果頁也只顯示主 answer

目前：

```text
正解 ${q.answer}
```

多答案題要顯示完整 accepted set。

例如：

```text
官方可接受答案 B、C
```

送分題：

```text
本題一律給分
```

不要顯示 `正解 一律給分`。

---

## 8. 模擬考「未作答」bug 與多答案要同一輪修

現行 `MK.grade()`：

- 未作答會進 `wrong[]`
- 但 `record()` / `bySubj` 只在 `picked != null` 才執行

所以月底改 `MK.grade()` 時一次處理：

1. `ok = isCorrectAnswer(q,picked)`
2. 未作答視為 incorrect
3. 未作答進各科分母
4. 未作答進 review schedule / history
5. UI 仍顯示「未作答」

這樣不用同一函式改兩次。

---

## 9. 目前 answer-related code audit 結論

已定位的直接判題／答案顯示點：

| 區域 | 現況 | 月底動作 |
|---|---|---|
| `isGiveAll()` | 可保留 | 作為 `acceptedAnswers(item)` 的送分分支 |
| `ansCorrect(p,a)` | 單答案 | 淘汰或只留 compatibility wrapper |
| `normalize()` | 漏 `accepted_answers` | 必補 |
| `renderQuiz()` option class | `k===item.answer` | 改 accepted set |
| `renderQuiz()` marker | `k===item.answer` | 改共同 answer label / accepted set |
| `renderQuiz()` wrong | `ansCorrect(selected,item.answer)` | `isCorrectAnswer(item,selected)` |
| `submit()` | `ansCorrect(selected,item.answer)` | `isCorrectAnswer(item,selected)` |
| `MK.grade()` | `picked===q.answer` | `isCorrectAnswer(q,picked)` |
| MK review result | `正解 q.answer` | `answerLabel(q)` |

目前完整檔案搜尋到的直接 `q.answer` / `item.answer` 判題路徑主要就是上述區域；月底修改後應再做一次全文 grep，要求除了 helper / 顯示用途之外，不得存在自行判斷 `picked===answer` 的第二套邏輯。

---

## 10. 月底驗收方式

### 24 題官方多答案

逐題測：

- 每個 accepted option 都應 correct
- 非 accepted option 應 wrong
- 不得因選到第二 accepted answer 而加入錯題本
- 結果頁顯示完整 accepted set

### 16 題一律給分

對每題抽測 A/B/C/D：

- 任一已作答選項皆 correct
- 不加入錯題本
- 文案明確「官方一律給分」
- 不暗示四個選項在學理上都正確

### 一般單答案

抽至少 20 題確認：

- 正確選項仍正常
- 錯誤選項仍正常
- 不因 helper 改寫而 regression

### 模擬考

至少組一場含：

- 普通單答案
- 多答案
- 一律給分
- 未作答

核對：總分、各科分母、history、review schedule、結果頁四者一致。

---

## 11. 月底施工中特別提醒

`index.html` 是「原始函式 + 後面 patch/override」累積而來，不是乾淨單層程式。

因此每改一個核心函式前先問：

> **檔案後面有沒有再次 override 這個 function？**

目前已確認：

- `renderHome()`：有 UIUX V1 override
- `renderReview()`：有 UIUX V1 override

月底 diff review 必須從檔案尾端往回檢查 override，避免「前面修對、後面又蓋回舊版」。
