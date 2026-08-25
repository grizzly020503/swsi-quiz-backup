# SWSI 月底前端稽核補充

建立：2026-08-25
最後更新：2026-08-25（官方給分模式已拆成 standard / all_credit / any_answer）
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

## 2. 判題不能只看 `answer`；必須同時讀 `accepted_answers` + `grading_mode`

目前舊 helper：

```js
function isGiveAll(a){
  a=(a==null?"":String(a));
  return a.indexOf("一律給分")>=0||a.indexOf("送分")>=0;
}
function ansCorrect(p,a){
  return p===a||isGiveAll(a);
}
```

這有兩個根本問題：

1. 不知道 `accepted_answers`，所以多答案題會判錯。
2. 把所有 `answer='一律給分'` 當成同一種規則，但考選部其實有兩種不同語意：
   - `all_credit`：真正「一律給分」，**未作答也得分**。
   - `any_answer`：「除未作答者不給分外，其餘均給分」，**A-D 任一作答得分，但空白不得分**。

Production 4,800 題目前已由官方 PDF audit 驗證為：

- `standard`：**4,784 題**
- `all_credit`：**12 題**
- `any_answer`：**4 題**
- grading-mode mismatch：**0**

月底不要再從 `answer` 字串猜 grading rule。

建議收斂成 item-based helper：

```js
const GRADING_MODES=new Set(['standard','all_credit','any_answer']);

function gradingMode(item){
  const m=item&&String(item.grading_mode||'');
  if(GRADING_MODES.has(m)) return m;
  // 普通 legacy row 可安全視同 standard；特殊給分缺 mode 不可猜。
  if(item && item.answer!=='一律給分') return 'standard';
  return 'unknown';
}

function acceptedAnswers(item){
  if(!item) return new Set();
  const mode=gradingMode(item);
  if(mode==='all_credit' || mode==='any_answer'){
    return new Set(['A','B','C','D']);
  }
  if(Array.isArray(item.accepted_answers) && item.accepted_answers.length){
    return new Set(item.accepted_answers.filter(x=>['A','B','C','D'].includes(x)));
  }
  return ['A','B','C','D'].includes(item.answer)
    ? new Set([item.answer])
    : new Set();
}

function isCorrectAnswer(item,picked){
  const mode=gradingMode(item);
  if(mode==='unknown') return false; // fail closed，不猜官方特殊給分規則
  if(mode==='all_credit'){
    return picked==null || acceptedAnswers(item).has(picked);
  }
  return picked!=null && acceptedAnswers(item).has(picked);
}
```

所有畫面只呼叫共同 helper，不再各自寫 `picked===answer`。

---

## 3. `normalize()` 必須帶 `accepted_answers` 與 `grading_mode`

現行 normalized question object 有：

- id / subject / year / round / qno
- question/options
- `answer`
- exp / mnemonic / law / mistake / legal status

但尚未完整保留新的官方計分 metadata。

月底至少補：

```js
accepted_answers: Array.isArray(r.accepted_answers)
  ? r.accepted_answers.filter(x=>['A','B','C','D'].includes(x))
  : null,
grading_mode: ['standard','all_credit','any_answer'].includes(r.grading_mode)
  ? r.grading_mode
  : (r.answer==='一律給分' ? 'unknown' : 'standard'),
```

原則：

> 普通 legacy row 缺 mode 可視為 `standard`；`answer='一律給分'` 卻缺 mode 時不能在 frontend 自己猜是 `all_credit` 還是 `any_answer`。

CDN / Supabase production 現在都已提供正式 `grading_mode`，所以正常路徑不應出現 `unknown`。

---

## 4. 一般刷題的答案 UI 與學習紀錄要一起收斂

### 4.1 普通／多答案選項綠框

目前：

```js
if(answered){
  if(k===item.answer || (isGiveAll(item.answer)&&k===selected)) cls+=' correct';
  else if(k===selected) cls+=' wrong';
}
```

普通與多答案題可改成：

```js
const mode=gradingMode(item);
const accepted=acceptedAnswers(item);
if(answered && mode==='standard'){
  if(accepted.has(k)) cls+=' correct';
  else if(k===selected) cls+=' wrong';
}
```

### 4.2 特殊給分題不要把 A-D 四個都畫成「學理正確」

`all_credit` / `any_answer` 的 A-D 都可能依官方規則得分，但這**不代表四個選項在學理上都正確**。

因此特殊給分題建議：

- 使用者有作答：只標示「你的作答」；另外顯示「本題依官方特殊給分規則計分」。
- `all_credit` 未作答：顯示「未作答｜官方一律給分，本題仍得分」。
- `any_answer` 未作答：顯示「未作答｜依官方規則，本題不得分」。
- 不要把四個選項全部塗綠。

### 4.3 submit / wrong topic

目前：

```js
const correct=ansCorrect(selected,item.answer);
```

必須改：

```js
const correct=isCorrectAnswer(item,selected);
```

否則會污染：

- history
- review schedule
- weak topics
- 正確率

---

## 5. 答案文案統一由 `answerLabel(item)` 產生

不要再顯示：

```text
正確答案是 ${item.answer}
```

建議：

```js
function answerLabel(item){
  const mode=gradingMode(item);
  if(mode==='all_credit') return '官方一律給分（未作答也得分）';
  if(mode==='any_answer') return '官方規則：除未作答者不給分外，其餘均給分';
  if(mode==='unknown') return '官方特殊給分規則資料不完整';
  const xs=[...acceptedAnswers(item)];
  return xs.length>1
    ? `官方可接受答案：${xs.join('、')}`
    : `正確答案：${xs[0]||'—'}`;
}
```

一般刷題解析區、模擬考結果頁都用同一 helper。

---

## 6. `MK.grade()` 是第二套判定，必須一起改

目前：

```js
var ok=picked!=null && (
  picked===q.answer ||
  /一律給分|送分/.test(String(q.answer||''))
);
```

不能保留外層 `picked!=null`，因為 `all_credit` 題即使未作答也應得分。

改成：

```js
var ok=isCorrectAnswer(q,picked);
```

這也是為什麼 grading rule 必須集中到 item-based helper。

---

## 7. 模擬考結果頁不能只顯示主 answer

目前：

```text
正解 ${q.answer}
```

應統一使用：

```js
answerLabel(q)
```

顯示範例：

- 多答案：`官方可接受答案：B、C`
- `all_credit`：`官方一律給分（未作答也得分）`
- `any_answer`：`除未作答者不給分外，其餘均給分`

---

## 8. 模擬考「未作答」規格：不是一律 incorrect

現行 `MK.grade()`：

- 未作答會進 `wrong[]`
- 但 `record()` / `bySubj` 只在 `picked != null` 才執行

月底同一輪修正，但規則要依 `grading_mode`：

| grading_mode | A-D 作答 | 未作答 |
|---|---|---|
| `standard` | 依單／多答案集合判定 | incorrect |
| `all_credit` | correct | **correct** |
| `any_answer` | correct | **incorrect** |

共同要求：

1. 每一題都進各科分母，不因未作答消失。
2. 每一題都依 `isCorrectAnswer(q,picked)` 計分。
3. incorrect 才進錯題／間隔複習；`all_credit` 空白不得污染錯題。
4. history 可記錄 `picked=null`，UI 仍明確顯示「未作答」。
5. `all_credit` 空白結果要同時顯示「未作答」與「官方一律給分，本題仍得分」。

目前 `record(item,picked,correct)` 並沒有把 `picked` 寫進 history，只記 id/subject/major/mistake/correct/ts，因此技術上可接受 `picked=null`；真正要注意的是傳入的 `correct` 必須先依 grading mode 算對。

---

## 9. answer-related code audit 結論

| 區域 | 現況 | 月底動作 |
|---|---|---|
| `isGiveAll()` | 把特殊給分混成一類 | 淘汰為判題依據；不得從 answer 字串猜 mode |
| `ansCorrect(p,a)` | 單答案 | 淘汰或只留 compatibility wrapper |
| `normalize()` | 漏 `accepted_answers` / `grading_mode` | 必補 |
| `renderQuiz()` option class | `k===item.answer` | standard 用 accepted set；特殊給分另顯示規則 |
| `renderQuiz()` marker | `k===item.answer` | 改共同 `answerLabel()` |
| `renderQuiz()` wrong | `ansCorrect(selected,item.answer)` | `isCorrectAnswer(item,selected)` |
| `submit()` | `ansCorrect(selected,item.answer)` | `isCorrectAnswer(item,selected)` |
| `MK.grade()` | `picked!=null && picked===q.answer...` | 只用 `isCorrectAnswer(q,picked)` |
| MK review result | `正解 q.answer` | `answerLabel(q)` |

月底修改後再全文 grep：除了 helper / 純顯示用途之外，不得存在第二套 `picked===answer` 或 `/一律給分|送分/` 判題邏輯。

---

## 10. 月底驗收方式

### 24 題官方多答案

逐題測：

- 每個 accepted option 都應 correct
- 非 accepted option 應 wrong
- 不得因選到第二 accepted answer 而加入錯題本
- 結果頁顯示完整 accepted set

### 12 題 `all_credit`

每題至少測：

- A/B/C/D 任一作答皆 correct
- **未作答也 correct**
- 不加入錯題本
- 文案明確「官方一律給分」
- 不暗示四個選項在學理上都正確

### 4 題 `any_answer`

每題至少測：

- A/B/C/D 任一作答皆 correct
- **未作答 incorrect**
- 未作答應進錯題／間隔複習
- 文案明確「除未作答者不給分外，其餘均給分」
- 不暗示四個選項在學理上都正確

目前 4 題為：

- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

### 一般單答案

抽至少 20 題確認：

- 正確選項仍正常
- 錯誤選項仍正常
- 不因 helper 改寫而 regression

### 模擬考

至少組一場含：

- 普通單答案
- 多答案
- `all_credit`（含未作答）
- `any_answer`（含未作答）

核對：總分、各科分母、history、review schedule、結果頁五者一致。

---

## 11. 月底施工中特別提醒

`index.html` 是「原始函式 + 後面 patch/override」累積而來，不是乾淨單層程式。

因此每改一個核心函式前先問：

> **檔案後面有沒有再次 override 這個 function？**

目前已確認：

- `renderHome()`：有 UIUX V1 override
- `renderReview()`：有 UIUX V1 override
- `applyFocusedTabbar`：有 wrapper
- 時事雷達會 hook `NL.open` / `NL.filter`

月底 diff review 必須從檔案尾端往回檢查 override，避免「前面修對、後面又蓋回舊版」。
