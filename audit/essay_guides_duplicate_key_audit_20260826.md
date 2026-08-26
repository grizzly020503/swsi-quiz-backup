# ESSAY_GUIDES Duplicate-Key Audit

日期：2026-08-26
狀態：`blocker / audit only`

> 本檔只記錄 `essay_guides.js` 的資料完整性風險；未修改學生端、`monthly_patch_parts/`、Cloudflare preview 或 Netlify 正式站。

## 已確認問題

### `社會工作-107-1-申論2`

在同一個 `window.ESSAY_GUIDES = {...}` object literal 中，這個 key 至少出現兩次，而且內容不同：

1. 前一版：
   - 主題：`增強權能（賦權）觀點`
   - 關鍵內容：無力感、夥伴關係、個人／人際／政治三層次培力。

2. 後一版：
   - 主題：`優勢觀點與復原力`
   - 關鍵內容：優勢／資源、保護因子 vs 危險因子、去病理化、希望感。

## 實際執行後果

JavaScript object literal 遇到相同 property key 時，後面的定義會覆蓋前面的定義；一般不會因此丟出 runtime error。

因此目前實際載入：

```js
window.ESSAY_GUIDES['社會工作-107-1-申論2']
```

只會留下後面的「優勢觀點與復原力」版本；前面的「增強權能」版本已經在解析／建立物件時消失。

這代表：

- 不能只用 `Object.keys(window.ESSAY_GUIDES)` 檢查重複 key，因為執行完成後重複資訊已遺失。
- 某題即使前面已人工修好，後面若再出現同 key，仍可能被靜默覆蓋。
- smoke 若只驗證「key 存在」，也抓不到這類 regression。

## 嚴重度

`P0 / content-integrity blocker`

原因不是單純冗餘，而是同一題可能載入錯誤主題，且錯誤不會主動報錯。

## 正式施工窗口建議

### 1. 在「執行 JS 前」做 duplicate-key lint

建議新增 prebuild／smoke script，直接讀 `essay_guides.js` 原始碼，用 parser 或可靠的 source-level 掃描找出 `window.ESSAY_GUIDES` object literal 中所有 property keys。

驗證規則：

```text
每一個題目 id 必須且只能出現一次。
```

若重複，build／preview smoke 直接 fail，並輸出：

- 重複 id
- 第一次 source location
- 第二次 source location
- 兩個 value 的摘要／hash（可選）

### 2. 不要用 runtime Object.keys 當唯一檢查

錯誤示範：

```js
const ids = Object.keys(window.ESSAY_GUIDES);
```

這只能看到覆蓋後的物件，無法知道 source 曾有重複 key。

### 3. 長期較安全的資料產生方式

可考慮讓生成器先產出 records array，再明確建 Map／Object，插入時遇到重複 id 就 throw：

```js
const out = Object.create(null);
for (const row of rows) {
  if (Object.hasOwn(out, row.id)) {
    throw new Error(`Duplicate ESSAY_GUIDE id: ${row.id}`);
  }
  out[row.id] = row.guide;
}
```

這樣重複題號會在生成階段 fail closed，而不是瀏覽器端 last-write-wins。

## 本次 audit 邊界

目前只把「已直接確認」的 `社會工作-107-1-申論2` 記為 confirmed duplicate；沒有因為檔案內容大量共用模板，就推測所有題號都有重複。

下一步應以 source-level parser 一次掃完整檔後，再建立完整 duplicate report。正式修正仍留在學生端施工窗口，不在本次 audit commit 內進行。
