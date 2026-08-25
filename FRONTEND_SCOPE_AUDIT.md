# SWSI 指定歷屆／刷題範圍 Audit

建立：2026-08-25
狀態：**已確認現行 bug；尚未修改 Netlify**

---

## 1. 已確認 bug：UIUX V1 把 `homeQuizRound` value 改成不相容格式

核心 filter：

```js
function focusedQuizFilter(q){
  ...
  if(homeQuizScope==='specific'){
    if(String(q.year)!==String(homeQuizYear)) return false;
    if(homeQuizRound!=='all' && canonicalRound(q.round)!==homeQuizRound) return false;
  }
  return true;
}
```

而：

```js
function canonicalRound(v){
  ...
  if(s.includes('二')||s.includes('2')) return '2';
  if(s.includes('一')||s.includes('1')) return '1';
}
```

因此 `focusedQuizFilter()` 實際期待：

```text
homeQuizRound = "1" / "2" / "all"
```

原始 `renderHome()` 也確實是：

```html
<option value="1">第一次</option>
<option value="2">第二次</option>
```

但檔案尾端 UIUX V1 override 重新定義 `renderHome()` 後，改成：

```html
<option value="第一次">第一次</option>
<option value="第二次">第二次</option>
```

結果：

```text
canonicalRound(q.round) === "1"
homeQuizRound === "第一次"
```

永遠不相等。

### 使用者影響

首頁：

> 自訂範圍 → 指定歷屆 → 選某年份 → 選「第一次」或「第二次」

可能得到：

> 「這個條件目前沒有題目」

選「全部考次」則不受此 bug 影響。

---

## 2. 月底修法

不要在各處混用：

- `1 / 2`
- `第一次 / 第二次`
- `第1次 / 第2次`

內部狀態一律 canonical：

```text
"1"
"2"
"all"
```

UI label 才顯示：

```text
第一次
第二次
全部考次
```

最小修法：UIUX V1 override 改回：

```html
<option value="1">第一次</option>
<option value="2">第二次</option>
```

並保留：

```js
setHomeQuizRound(this.value)
```

### 額外防呆

`setHomeQuizRound()` 可 canonicalize：

```js
function setHomeQuizRound(v){
  homeQuizRound = v==='all' ? 'all' : canonicalRound(v);
  render();
}
```

這樣即使未來某 UI 傳入 `第一次`，內部仍轉成 `1`。

---

## 3. CDN loader 必須沿用同一 canonical round

`CDN_FRONTEND_MIGRATION_DESIGN.md` 的 scope → shard mapping 不可直接拿 UI label 拼檔名。

正確：

```text
homeQuizRound "1" → manifest round "第一次" → file 115-1.json
homeQuizRound "2" → manifest round "第二次" → file 115-2.json
```

建議 shard matcher：

```js
function roundNo(v){
  const c=canonicalRound(v);
  return c==='1'||c==='2' ? c : '';
}
```

比對 manifest 時也用 `canonicalRound(meta.round)`。

---

## 4. 模擬考不要跟著亂改

`MK.papers()` / `MK.buildExam()` 目前是從實際 `q.round` 產生並以同一字串比對：

```js
String(q.round||'').trim()===exRound
```

這條目前內部是一致的。

月底若要優化 MK 指定歷屆只載單 shard，再轉成 canonical mapping；不要為修首頁 bug 順手把 MK round 格式改一半。

---

## 5. 月底驗收

至少測：

- 115 年 → 全部考次：400 題 pool
- 115 年 → 第一次：200 題 pool
- 115 年 → 第二次：200 題 pool
- 再加科目 filter：單一考次＋單科 = 40 題
- 指定第二次時 Network 只需 `115-2.json`
- 指定第一次時 Network 只需 `115-1.json`

另抽舊年度 104 年做同樣測試，避免只對最新年度正常。

---

## 6. 結論

這是一個**現行 UI override regression**，不是資料庫問題，也不是題庫缺題。

月底 CDN 切換時要先把 round 內部格式統一，否則 shard loader 即使完全正確，仍會因 UI state 值不一致而看起來像「CDN 沒題目」。
