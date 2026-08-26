# SWSI 選擇題＋申論題統一自動 QA Pipeline

日期：2026-08-26
狀態：architecture / non-production

> 本文件只定義未來題庫進件、風險分級與人工審核策略；不修改學生端。

## 0. 核心原則

未來每次新增國考題，不採「全部題目逐題人工審完才發布」。

改成：

```text
官方資料進件
  ↓
官方核心層自動驗證
  ↓
完整且無異常 ─────────→ 官方題幹／官方答案可發布
  ↓
解析／標籤／申論參考架構等加值層
  ↓
自動風險分級
  ↓
低風險自動通過／中高風險進人工佇列／重大異常阻擋
```

**官方核心層與 SWSI 加值層必須分離。**

解析還沒審完，不應阻止一份已經通過官方完整性檢查的考選部原題進題庫。

---

# 1. 三層資料模型

## Layer A — Official Core（近似唯讀）

只保存考試本身：

### 選擇題
- id
- subject
- year
- round
- qno
- question
- A/B/C/D
- official answer
- accepted_answers
- grading_mode
- source_exam_code
- official source / immutable hash

### 申論題
- id
- subject
- year
- round
- qno
- official question stem
- points
- source_exam_code
- source_url
- immutable hash

### 原則
- 不在這層保存 AI 是否覺得答案好。
- 不因解析尚未完成而改寫官方原題。
- 官方更正答案必須形成 correction record，而不是偷偷覆蓋沒有紀錄。

---

## Layer B — Enrichment（SWSI 加值層）

可包含：
- 選擇題解析
- why / others / trap
- 口訣
- 延伸閱讀
- 法規提示
- topic / major / keywords
- 申論考點
- 申論作答架構
- guideMust / guideMustNot
- AI 參考批改資訊

這層可以比 Official Core 晚完成。

例如：

```text
116-1 選擇題正式公布
→ 200 題官方核心驗證通過
→ 200 題立刻可刷題
→ 其中 37 題解析仍待生成／審核
```

不需要因為 37 題解析沒完成而卡住其餘 163 題，甚至不需要卡住官方題幹本身。

---

## Layer C — QA / Audit Log

每一次檢查只記錄事件，不把大量歷史欄位塞回題目本體。

建議格式：

```json
{
  "item_id": "SW-116-1-16",
  "checked_at": "2027-02-01T10:00:00+08:00",
  "layer": "official_core",
  "rule": "MCQ_SPECIAL_GRADING_EXPLICIT",
  "result": "blocked",
  "message": "answer 顯示一律給分但缺 grading_mode",
  "resolved_by": null,
  "resolved_at": null
}
```

後台真正看的應該是「目前仍未解決的 event」，而不是把十年的 audit 全攤在同一個題目頁。

---

# 2. 統一 QA 狀態

只有三個主狀態：

- `passed`：自動檢查通過，不需要人看。
- `needs_review`：題目本體可保留，但某項加值內容／特殊情況需人工確認。
- `blocked`：官方核心完整性或特殊給分等有重大問題，不可發布該項資料。

另外保留風險等級：

- `low`
- `medium`
- `high`
- `critical`

不要再建立大量互相重疊的狀態名稱。

`verified / reviewed / reference_only` 可以繼續存在於「申論參考架構本身」，但不是整個題庫共同的 QA 狀態。

---

# 3. 選擇題自動 Gate

一個完整新考次正常應有：

- 200 題
- 5 科
- 每科 40 題
- 每科 qno 1–40
- 所有 id 唯一
- 題幹非空
- A/B/C/D 非空
- source_exam_code 存在
- `grading_mode` 明確存在

## 3.1 自動 passed

`standard` 題：
- official answer ∈ A/B/C/D
- accepted_answers 若存在必須合法、去重且包含 primary answer

全部正常 → 不需要人工逐題點開。

## 3.2 自動 needs_review

例如：
- 題目涉及明確法規／政策時效，但法律狀態尚未檢查
- 官方後續出現更正公告
- OCR／文字 normalization 有異常跡象
- SWSI 解析和 official answer 出現邏輯衝突

只把這些題丟入人工 queue。

## 3.3 自動 blocked

例如：
- 缺題
- 重複題號／ID
- 某科不是 40 題
- grading_mode 缺失或非法
- `standard` 卻沒有 A/B/C/D 正式答案
- `all_credit / any_answer` 的 metadata 不完整
- special grading 只靠「一律給分」答案文字推理

**特殊給分一律 fail closed；不可從 answer 字串或 legacy ID 猜 grading_mode。**

---

# 4. 申論題自動 Gate

正常一個考次應有：

- 10 題
- 5 科
- 每科 2 題
- qno 1、2
- 官方題幹非空
- source_exam_code 存在
- source_url 存在

以上只屬 Official Core。

## 4.1 官方題幹 passed ≠ SWSI guide verified

一題申論可以是：

```text
Official Core: passed
SWSI Guide: needs_review
```

學生仍可以先看到官方歷屆題目。

參考架構可以顯示「待整理」或暫不顯示，而不是阻塞整題。

## 4.2 自動風險偵測

下列情況提高 review risk：

### 法規／政策題
關鍵訊號：
- 法
- 條例
- 第X條
- 修正
- 公布
- 施行
- 政策方案
- 某年／某期計畫

→ `high`
→ 需要 historical-law-version QA。

### 多子問題
偵測：
- 「說明……並……」
- 「比較……並舉例」
- （一）（二）（三）
- 多個指定 action verb

系統應抽出 question requirements，例如：

```json
[
  "定義A",
  "比較B與C",
  "提出兩項措施",
  "舉例"
]
```

SWSI guide 若沒有覆蓋全部 requirements → `needs_review`。

### 特定學者／模型／專有名詞
例如：
- Kohlberg
- Thomas & Chess
- Le Grand
- Lisa's Law
- sampling frame

→ 至少 `medium`
→ 禁止只套 generic template。

---

# 5. 「人工審核量」應該怎麼算

假設未來一次考試：

- 200 題選擇題
- 10 題申論

理想 dashboard 不顯示：

> 待審 210 題

而應顯示：

```text
本次進件：210

Official Core
✅ passed:       204
⚠ needs_review: 4
⛔ blocked:      2

Enrichment
✅ passed:       171
⚠ needs_review: 31
⏳ pending:      8
```

管理者優先只處理：
- 2 個 blocked
- 4 個 official review

解析／申論參考架構可逐步完成，不阻止官方題庫發布。

---

# 6. 發布 Gate

## Gate A — Official Core Release

必須：
- `blocked = 0`
- 整個考次題數完整
- official source integrity 通過
- 特殊給分 metadata 明確

通過後可發布官方題幹／答案。

## Gate B — Enrichment Release

每一題各自決定。

- passed → 正常顯示
- needs_review → 隱藏高風險解析或標示 reference_only
- blocked → 不顯示該加值內容

**Gate B 不反向卡 Gate A。**

---

# 7. 與現有 repo 的整合

目前已存在：

- `scripts/build_question_shards.py`
  - 已自動檢查 200 題、每科40、qno、grading metadata。
- `data/official_exam_readonly.lock.json`
  - 可作官方原題 immutable baseline。
- `data/legal_watch_*`
  - 可作法律／政策時效 review signal。
- `scripts/historical_answer_audit*.py`
  - 可作舊題歷史答案異常檢測。
- `scripts/essay_verified_registry_lint.js`
  - 可作申論 verified registry 防重複。
- `scripts/p0_frontend_preflight.js`
  - 可作前端正式施工前 P0 gate。

因此未來不是重做整套後台，而是增加一個「orchestrator」把已有檢查結果整合成一張 queue/report。

---

# 8. 建議的最終資料流

```text
MOEX / official source
   ↓
immutable source snapshot
   ↓
parser
   ↓
Official Core QA
   ├─ passed
   ├─ needs_review
   └─ blocked
   ↓
Official Core publish
   ↓
Enrichment generator
   ↓
Enrichment QA
   ├─ low risk → auto pass
   ├─ medium/high → review queue
   └─ critical → block enrichment only
   ↓
CDN / student frontend
```

---

# 9. 成功標準

未來新增完整考次時：

1. 不需修改程式碼才能認出新年度／考次。
2. 正常選擇題不需人工逐題審。
3. 官方原題與 SWSI 解析互不綁死。
4. 只有 anomaly 進人工 queue。
5. 一題解析有問題，不會拖垮整個 200 題考次。
6. 特殊給分與官方更正必須 fail closed。
7. 法規歷史版本只阻擋相關 enrichment，不阻擋 official stem。
8. audit log 與題目本體分離，避免後台愈來愈肥。

這是未來年度題庫能長期維護、而不重演 2026 大規模人工清債的基本架構。
