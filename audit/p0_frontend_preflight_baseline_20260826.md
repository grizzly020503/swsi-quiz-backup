# P0 Frontend Preflight Baseline

日期：2026-08-26
狀態：`audit / expected-fail baseline`

> 本檔與 `scripts/p0_frontend_preflight.js` 只建立防回歸門檻；沒有修改任何學生端檔案。

## 為什麼現在應該是紅燈

### P0-1 — `ESSAY_GUIDES` duplicate key

`essay_guides.js` 使用 JavaScript object literal 保存逐題 guide。若同一題 ID 在 source 中被定義兩次，後一個 value 會靜默覆蓋前一個，runtime 不會報錯。

已人工確認至少有：
- `社會工作-107-1-申論2`

preflight 會掃描所有歷屆申論 key；任何重複都直接 fail。

### P0-2 — 特殊給分仍有 legacy inference

`monthly_patch_parts/00.part` 目前 `gradingMode(item)` 仍包含：
- `SWSI_ANY_ANSWER_LEGACY_IDS`
- 依 `answer` 文字中的「一律給分／送分」推論 `all_credit`
- `normalize()` 在缺 `grading_mode` 時回頭呼叫 `gradingMode(...)` 合成 mode

這違反目前題庫 invariant：
- 官方特殊給分題必須由資料層明確提供 `grading_mode`／`accepted_answers`。
- 不得由題號或答案字串猜 grading semantics。
- 一般題缺 mode 可安全視為 standard；已知／疑似特殊題缺 mode 應 fail closed，而非推論。

preflight 會在 legacy ID、answer-text inference、normalize synthesis 任一仍存在時 fail。

### P0-3 — 首頁考次值不一致

`index.html` 目前同時存在兩套 round select：
- 一套使用 canonical `1`／`2`
- 後面的首頁 override 使用 `第一次`／`第二次`

但 `focusedQuizFilter()` 使用：

```js
canonicalRound(q.round) !== homeQuizRound
```

因此 UI 若把 `homeQuizRound` 設為「第一次」，就不會等於 canonical `1`。

preflight 會拒絕任何首頁 round option/state 使用「第一次／第二次」作 value；顯示文字可以是第一次／第二次，但 value 必須維持 `1`／`2`。

---

# 修完後的 PASS contract

## 1. Essay guides

- 所有歷屆申論 ID 在 source 中只能出現一次。
- 若需逐題 override，必須在明確 override layer 進行，不可在同一 object literal 以 duplicate key 偷蓋。
- 加入 source lint 後，duplicate key 應使 build／preflight fail。

## 2. Grading

允許的 mode：
- `standard`
- `all_credit`
- `any_answer`

契約：
- 明確 mode → 照資料層 mode grading。
- `standard` → 依 `accepted_answers`，若無則才使用單一正式 answer。
- `all_credit` → 未作答也得分。
- `any_answer` → A/B/C/D 任一實際作答皆得分，blank 不得分。
- 不得看 legacy ID 猜 mode。
- 不得看「一律給分／送分」文字猜 mode。
- 特殊題 metadata 缺失不得 silently downgrade／upgrade。

## 3. Round

唯一 canonical state：
- `all`
- `1`
- `2`

UI label：
- `all` → 全部考次
- `1` → 第一次
- `2` → 第二次

所有 renderHome override、localStorage 還原與 `focusedQuizFilter()` 必須使用相同 canonical contract。

---

# 執行方式

```bash
node scripts/p0_frontend_preflight.js
```

需要機器可讀輸出：

```bash
node scripts/p0_frontend_preflight.js --json
```

目前基準：**EXPECTED FAIL**。

正式學生端 P0 patch 完成後：**必須 PASS**，之後才進 browser smoke／Cloudflare preview。

---

# 部署安全

依 `scripts/netlify_ignore.py`，一般 `scripts/` 與 `audit/` 變更不屬 student-facing；本輪未修改：
- `index.html`
- `essay_guides.js`
- `monthly_patch_parts/`
- `auto/questions_auto.json`
- `auto/essays_auto.json`
- `sw.js`
- `manifest.json`

因此這一輪只建立檢查門檻，不應觸發正式學生端語意更新。
