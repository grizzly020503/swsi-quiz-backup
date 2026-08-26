# Unified Question QA — 115-2 Baseline V2

日期：2026-08-26
狀態：`QA baseline / non-production`
Workflow run: `Unified Question QA #6`
Commit under test: `175d37bb1bf92500b3252536fbc53621f0b7bd99`

## 目的

驗證「新年度／新考次題庫不應因所有題目都要逐題人工過審而讓後台變笨重」。

本版新增：

1. `legal_watch` 可在**明確指定為當期新考次**時，消化已確認未變動的現行法規 review。
2. 歷史題預設仍不信任 current legal watch，避免拿今天法條倒灌舊考題。
3. 修正 `第三條路` 被 `第三條` 法條 regex 誤判的 false positive。
4. `analysis_status: ready` 現在正確計入已生成，而不是 pending generation。

---

# 真實 115-2 結果

資料：

- `cdn/question-shards/115-2.json`：200 題選擇題
- `auto/essays_auto.json`：115 年第二次 10 題申論
- `data/legal_watch_report.json`：2026-08-25 法規監測結果

命令概念：

```text
unified_question_qa.py
  --year 115
  --round 第二次
  --legal-watch data/legal_watch_report.json
  --trust-current-legal-watch
```

## Official Core

- total: **210**
- passed: **210**
- needs_review: **0**
- blocked: **0**
- release_ready: **true**

## Enrichment

- passed: **210**
- needs_review: **0**
- blocked: **0**
- pending_generation: **185**

### Generation backlog 細分

- MCQ pending_generation: **175 / 200**
- Essay pending_generation: **10 / 10**

這些是自動生成／補解析的工作佇列，不是人工審核佇列。

## Human review queue

**0 / 210**

這是本架構最重要的驗證結果。

前一版 baseline 人工 queue 為 12 題：

- 11 題 MCQ 法規／政策風險
- 1 題申論法規風險

V2 後：

- `第三條路` 已不再誤判成「第三條」法規。
- 真正點名現行法律的題目，若 `legal_watch` 已確認法規存在、查詢成功且 `changed=false`，當期 intake 不再要求人重複確認。
- 若 watched law `changed=true`，自我測試確認該題會重新進人工 queue。

---

# 安全界線

`--trust-current-legal-watch` **不得用於歷史考題回填／舊題重審**。

歷史題仍需：

- `historical_checked`
- 該考試當時法規版本
- 或既有 historical audit

原因：

> 「今天法規沒有變」不代表「104 年考試當時的法條和今天一樣」。

因此 current legal watch 只負責降低「新考次每次都重複人工確認現行法」的維護成本，不取代歷史版本 QA。

---

# 自動測試已通過的 invariants

1. 200 個 MCQ 解析 pending → human queue **0**。
2. 10 個 essay guides pending → human queue **0**。
3. `一律給分` 但缺 explicit `grading_mode` → **blocked**。
4. `第三條路` → **不是法條訊號**。
5. 當期題＋未變動 legal watch → 重複 law review **自動清除**。
6. watched law 變更 → review **自動恢復**。

---

# 對未來後台的意義

正常新考次的管理首頁不應顯示：

```text
待審核：210 題
```

而應類似：

```text
116-1 新考次
Official Core：210 passed / 0 blocked
人工異常：0
解析生成：185 pending
```

只有真正發生以下事件才打斷人工：

- 官方更正答案／特殊給分 metadata 異常
- 題數、題號、科目或來源完整性失敗
- 新法／修法被 legal watch 偵測
- 解析完成後與官方答案／題幹需求產生矛盾
- 歷史法規版本題需要 historical QA

因此資料量成長不必等比例增加人工工作量。

本 baseline 沒有修改學生端或執行任何部署。
