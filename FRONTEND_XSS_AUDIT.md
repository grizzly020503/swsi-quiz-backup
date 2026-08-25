# SWSI 月底前端 Stored XSS 稽核

建立：2026-08-25
狀態：**只做 code audit，尚未修改 `index.html` / Netlify**

目的：月底一次修學生端時，不只修 `renderQuiz()` 題幹，而是把所有「外部／資料庫資料 → `innerHTML`」入口一起收斂。

---

## 1. 威脅模型

題庫目前是 Supabase 公開唯讀，匿名使用者不能直接寫入，風險已比早期低很多。

但資料仍可能來自：

- MOEX parser
- Supabase 後台同步
- AI 題解
- 法規監測／修法註記
- 未來管理流程
- 舊資料匯入

因此「目前 DB 沒有惡意 payload」不能取代 output encoding。

Stored XSS 的原則：

> **任何不是寫死在前端程式裡的字串，只要進 `innerHTML`，都先視為不可信文字。**

---

## 2. 現行 `esc()` 的限制

目前全域：

```js
function esc(s){
  return (s||'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;');
}
```

這對「純文字節點」基本足夠，但**不是 attribute / JavaScript string encoder**，因為沒有處理：

- `"`
- `'`

而且即使把 `'` 變成 HTML entity，若資料被放進 inline `onclick="fn('...')"`，瀏覽器解析 attribute 後仍可能還原成引號，不能把 HTML escaping 當 JavaScript escaping。

月底不要只做「全域 esc 多加兩個 replace」就宣告 XSS 全修完。

---

## 3. 建議的安全規則

### 3.1 純文字節點

例如：

```html
<div>${text}</div>
```

使用：

```js
function escText(v){
  return String(v??'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}
```

換行：

```js
escText(v).replace(/\n/g,'<br>')
```

### 3.2 HTML attribute

不要把不可信資料手工串進 attribute。

優先：

- 用固定 index / id
- render 完後 `addEventListener`
- 或 `data-*` + DOM API 設定

不要：

```js
`onclick="openThing('${dbText}')"`
```

### 3.3 URL

不只 escape，還要驗 scheme。

外部來源只允許：

```text
https:
```

若真的需要才放行 `http:`。

明確拒絕：

- `javascript:`
- `data:`（除非是特定受控圖片流程）
- 其他未知 scheme

---

## 4. P0：一般刷題 `renderQuiz()`

這是目前最明確的 stored XSS surface。

### 4.1 選項文字

目前：

```js
<span>${item.options[k]}</span>
```

必改：

```js
<span>${escText(item.options[k])}</span>
```

### 4.2 題幹

目前：

```js
<div class="qtext">${item.q}</div>
```

必改：

```js
<div class="qtext">${escText(item.q).replace(/\n/g,'<br>')}</div>
```

### 4.3 題目 meta

目前 raw：

- `item.subject`
- `item.year`
- `item.round`

至少文字輸出皆 escape。

年度原則上是數字，但仍不要為「理論上應該是數字」開例外。

### 4.4 解析

目前 raw：

- `item.exp.why`
- `item.exp.others`
- `item.exp.trap`
- `item.exp.raw`

全部必先 escape，再轉換換行。

尤其這些內容曾由 AI 產生，是最不應直接信任的資料之一。

### 4.5 extra

目前 raw：

- `item.mnemonic`
- `item.law`

必 escape。

### 4.6 topic / major / mistake

目前 raw：

- `item.topic || item.major`
- `item.mistake`

必 escape。

---

## 5. P0：`renderSummary()`

本次錯題的 weak topic 來自：

```js
item.topic || item.major
```

最後直接：

```js
weak.map(t=>`<div class="item">· ${t}</div>`)
```

必改成 `escText(t)`。

這條資料可由 Supabase 題目進入 history/sessionStats，所以也是 stored data path。

---

## 6. P0：`renderTopics()`

`major` 是由題庫資料聚合成 group name，目前卡片直接：

```js
<div class="name">${name}</div>
```

必改：

```js
<div class="name">${escText(name)}</div>
```

`onclick="practiceTopic(${i})"` 用的是數字 index，這種方式是對的；不要改成把 major 字串塞進 onclick。

---

## 7. P0：`renderProgress()`

作答紀錄會保存：

- subject
- major
- mistake

因此即使題庫之後被修正，localStorage 仍可能保有舊字串。

目前未 escape：

### 各科名稱

```js
${subj}
```

### 常錯考點

```js
${m}
```

### 錯因

```js
${m}
```

全部必 `escText()`。

這也是為什麼「現在 Supabase 已安全」仍不能只修資料庫：**localStorage 本身也是持久資料來源。**

---

## 8. Review 有兩套 implementation

### 舊 `renderReview()`

錯因名稱目前 raw：

```js
${reason}
```

### UIUX V1 override

後置 override 已有：

```js
esc(pair[0])
```

但月底不能因此忽略舊版。

建議：

1. 若保留兩套 → 兩套都修。
2. 更理想 → 月底確認 UIUX V1 已穩定後，讓共同 helper 被兩套共用，避免未來 override 又把安全修正蓋掉。

不要在公開前大規模刪整段舊 UI，只為了「程式漂亮」增加回歸風險。

---

## 9. 模擬考目前相對安全，但仍統一規格

`MK` 自己的 `E(s)` 已處理：

- `&`
- `<`
- `>`
- `"`

題幹／選項顯示大多經 `E()`。

因此模擬考不是目前 stored-XSS 第一風險區。

但月底若改多答案結果文案，新增的：

- accepted answer label
- 題目 meta
- explanation

仍應全部走 `E()` / `escText()`，不要因為是新字串又直接串 raw。

---

## 10. Search / essay / theory / laws

目前多數搜尋結果、申論題文字、理論／法規靜態資料已使用 `esc()` / `E()`。

但注意兩類情況：

### 10.1 inline JS attribute

例如：

```html
onclick="openThing('動態字串')"
```

不能因為用了 `esc()` 就視為安全。

若動態值來自外部資料，月底優先改成 index / stable id。

### 10.2 source URL

時事／法規來源連結除了 HTML escape，還要驗 scheme。

只允許 `https:` 為預設。

---

## 11. 不要使用的修法

### ❌ `stripTags()`

刪 `<script>` 不代表安全，事件 handler、svg、malformed HTML 仍可能繞過。

### ❌ 黑名單替換

不要只替換：

- `<script>`
- `onerror`
- `javascript:`

應依輸出 context encode。

### ❌ 全站把資料丟 DOMPurify 當成文字 escape

平台大多欄位本來就只需要「文字」，最安全的是 encode 成文字，不是允許 HTML 再 sanitize。

---

## 12. 月底建議共用 helper

最少：

```js
function escText(v){
  return String(v??'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}

function textWithBreaks(v){
  return escText(v).replace(/\n/g,'<br>');
}

function safeHttpUrl(v){
  try{
    const u=new URL(String(v||''),location.href);
    return u.protocol==='https:' ? u.href : '';
  }catch(_e){
    return '';
  }
}
```

然後逐步把舊 `esc()` callsite 收斂，不必為了命名一次改遍所有靜態內建資料。

---

## 13. 月底 XSS 驗收 payload

在**本地／preview 測試資料**塞入，不要污染 production DB：

```text
<img src=x onerror=alert(1)>
```

```text
<svg onload=alert(1)>
```

```text
"><img src=x onerror=alert(1)>
```

```text
';alert(1);//
```

測欄位至少：

- question
- opt_a
- exp_why
- mnemonic
- law
- topic
- major
- mistake
- subject
- source_url

驗收：

- 畫面只顯示字面文字
- 不建立 IMG / SVG node
- 不出現 alert
- 不改 DOM 結構
- 不執行 inline JS
- 非 HTTPS source_url 不產生可點外連

---

## 14. 月底 diff review checklist

完成前全文再搜尋：

```text
item.q
item.options
item.exp
item.mnemonic
item.law
item.topic
item.major
item.mistake
wrongMajor
byMistake
innerHTML
onclick="
source_url
```

要求：

- 所有 DB / AI / localStorage 字串進 HTML 前都有 context-aware encoding
- 所有 URL 有 scheme allowlist
- 不可信字串不直接進 inline JS attribute

---

## 15. 結論

目前最危險的不是「有人現在能直接寫 Supabase」，而是前端仍把一部分**持久資料與 AI 文字當可信 HTML**。

月底修法應以：

> **資料永遠是文字，HTML 是前端模板。**

為原則。

先修 `renderQuiz()`、`renderSummary()`、`renderTopics()`、`renderProgress()`，再全文掃描 override 與 attribute context，就能把公開前 stored-XSS 風險大幅壓低，而不需要重寫整站。
