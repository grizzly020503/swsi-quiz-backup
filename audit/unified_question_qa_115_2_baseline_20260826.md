# Unified Question QA — 115-2 真實快照基準

日期：2026-08-26
狀態：`QA baseline / non-production`
Workflow run: `Unified Question QA #2`
Commit under test: `fe442b7e7428672b7bdd8c3d1f56a78a4baa9492`

## 結果

針對目前 repo 的：

- `cdn/question-shards/115-2.json`：200 題選擇題
- `auto/essays_auto.json` 中的 115 年第二次：10 題申論

執行 `scripts/unified_question_qa.py`。

### Official Core

- total: **210**
- passed: **210**
- needs_review: **0**
- blocked: **0**
- official release ready: **true**

這代表官方題幹、題數、科目分布、題號、來源欄位與選擇題 grading metadata 可由機器完成主要完整性 gate，不需要人工逐題點 210 次。

### Enrichment

- passed: **198**
- needs_review: **12**
- blocked: **0**
- pending_generation: **210**

注意：`pending_generation: 210` **不是人工待審 210 題**。

它只是表示目前這批資料的解析／guide enrichment 尚未在統一狀態機中被標記完成；可交由生成流程逐步補齊。

### 真正人工 queue

**12 / 210**

其中：

- MCQ：11 題
- Essay：1 題

#### MCQ 11 題

目前被規則判為法律／政策 enrichment 需要時效確認：

- `SP-115-2-004`
- `SP-115-2-022`
- `SP-115-2-023`
- `SP-115-2-026`
- `SP-115-2-027`
- `SP-115-2-028`
- `SP-115-2-029`
- `SP-115-2-032`
- `SP-115-2-033`
- `SP-115-2-035`
- `SP-115-2-038`

這 11 題 **Official Core 全部 passed**；需要人工看的只有 SWSI 法規／政策解析時效，而不是考選部題目本身。

#### Essay 1 題

- `E-115-2-SP-2`

題幹直接指定《性侵害犯罪防治法》，因此申論 guide 進 historical/current law review。

Official Core 仍為 passed。

---

# 合成測試同時通過

CI 另驗證：

1. 200 題 MCQ 官方核心正常、200 個解析 pending
   - manual queue = **0**
2. 10 題申論官方核心正常、10 個 guide pending
   - manual queue = **0**
3. 「一律給分」但缺 explicit `grading_mode`
   - official item = **blocked**
4. 只有 1 題法規申論
   - enrichment manual queue = **1**

因此未來新年度題庫不需要走「210 題全部人工過審」。

---

# 對後台設計的實際意義

後台預設首頁應呈現 anomaly queue，而不是完整題目表：

```text
116-1 新考次（示意）
官方核心：210 passed / 0 review / 0 blocked
生成佇列：210 pending
人工待處理：12
```

管理者點進去只處理那 12 題。

完整 210 題仍可搜尋／檢視，但不應變成 210 張「待辦卡」。

---

# 下一步

1. 將 Unified QA 接到未來 MOEX sync 的「發布前 report」，但先不要改既有正式發布 gate。
2. 把 `legal_watch_state/report` 的已確認結果餵回 QA，讓已核對的法規題自動從 12 題 queue 中消失。
3. 增加 official correction detector：只有考選部更正答案／特殊給分才進 Official Core 人工 queue。
4. Enrichment generator 完成後，再跑 guide coverage QA；多子問但 coverage 完整者自動 passed。
5. 管理頁未來只讀 report 的 anomaly queue，不直接把全部題庫當人工待辦。

本 baseline 沒有修改學生端，也沒有部署任何內容。
