# 社工師國考免費學習平台（SWSI）

SWSI 是一個以 **免費、低門檻、可長期維護** 為核心的社工師國考學習平台。

目前產品方向已從「持續增加功能」轉向：

> **把既有題庫、解析、法規、時事與自動維運做深、做穩、做可信。**

---

## 目前狀態

- 題庫主體：ROC 104–115，共 **24 個考次**
- 官方選擇題：**4,800 題**
- 官方申論題：**240 題**
- 官方題庫合計：**5,040 題**
- Repo：`grizzly020503/swsi-quiz-backup`
- Public Readiness：**收尾中**
- 目前 repository：**Private**
- 公開前安全主追蹤：Issue **#330**

> Repo 只有在完整 Git history audit、credential / privacy review 與公開前安全驗收真正完成後，才應切換 Public。

---

## 平台核心功能

學生端以三件事為核心：

1. **刷選擇題**：依年份、考次、科目與弱點練習歷屆題。
2. **錯題複習**：錯題本、弱點整理與間隔複習。
3. **申論練習**：歷屆申論、答題架構與 AI 輔助回饋。

其他重要能力包括：

- 法規與歷史法規追蹤
- 理論 / 考點整理
- 時事雷達與國考關聯
- 題庫健康檢查
- 自動同步新考次
- 資料品質 review queue
- 管理後台與監控
- AI 輔助解析 / evidence review

原則是：**前台做減法，後台做自動化。**

---

## 資料可信度原則

SWSI 將資料分成不同信任層級，不把 AI 生成內容與官方資料混在一起。

### Official Core

包含：

- 官方題目
- 官方選項
- 官方答案
- `accepted_answers`
- `grading_mode`
- 官方申論題

Official Core 不應由 AI 直接修改。

### Generated / Enrichment Layer

包含：

- 解析
- topic / keywords
- 理論關聯
- 法規關聯
- 申論 guide
- 時事與歷屆題關聯

這些內容可以由程式或 AI 協助產生，但必須經 QA、來源與 provenance 規則管理。

**有解析 ≠ 已人工 verified；有 law metadata ≠ 已證明直接法源。**

---

## 官方特殊給分

平台不只支援單一答案。

目前選擇題資料模型包含：

- `accepted_answers`
- `grading_mode='standard'`
- `grading_mode='all_credit'`
- `grading_mode='any_answer'`

因此學生端與後台不得只靠單一 `answer` 欄位推測計分規則。

---

## 系統架構

題庫主要資料流：

```text
考選部官方試題 / 答案
  ↓
Parser + Health Check
  ↓
Supabase
  ↓
Question Shard Builder
  ↓
Cloudflare Static Assets / CDN
  ↓
學生端
  ↓
IndexedDB / 離線備援
```

AI 相關功能採獨立 gateway / quota / safety boundary，不應影響核心刷題功能。

即使 AI 暫時不可用，刷題、錯題與非 AI 申論功能仍應維持正常。

---

## 長期維運方向

SWSI 的目標不是依賴人工逐題維護，而是逐步形成：

```text
官方 / 公開來源
  ↓
自動抓取
  ↓
結構與來源驗證
  ↓
Deterministic QA / Provenance
  ↓
高風險或 unresolved queue
  ↓
AI Shadow / Evidence Review
  ↓
Human / Quarantine（少數 conflict）
  ↓
版本化結果 + Health Report
```

AI 是輔助層，不是官方答案或 evidence 的替代品。

---

## 歷史法規與 629 題範圍

歷史法規驗證正在從早期高信賴 priority slice 擴充到完整 legal-ready mother scope。

重要原則：

- 不把 generated `law` metadata 直接當證據
- 不用關鍵字匹配取代 provenance
- deterministic Stage 2–6 chain 優先於 AI
- AI 只處理 unresolved / ambiguous lane
- source mismatch / outage 不得判定成功
- 不為了把數字湊到 629 而降低 evidence 規則

更完整規則請讀 [`docs/AI_MAINTENANCE.md`](docs/AI_MAINTENANCE.md)。

---

## AI / 新接手者：先讀這裡

任何 AI、Codex、ChatGPT Work 或新維運者，在修改程式、資料、workflow 或 production 前：

1. 重新確認遠端 `main`、open PR / Issue、最新 Actions 與部署狀態。
2. 讀本 README。
3. 讀 [`docs/AI_MAINTENANCE.md`](docs/AI_MAINTENANCE.md)。
4. 再依任務需要讀 `PROJECT_HANDOFF.md` 與專項 Issue / audit。
5. 不要假設聊天紀錄或舊 SHA 仍是最新。

### 絕對不要做

- 不要把 service-role key、provider token、internal key、密碼或 production secret 寫進 GitHub。
- 不要因 AI 推論不同就直接修改 Official Core。
- 不要把 heuristic signal 當成已證實錯題。
- 不要為了增加 coverage 降低 evidence threshold。
- 不要為了整理檔案就任意 rewrite Git history。
- 不要看到 GitHub Actions `0 steps` / `steps=null` / 無 logs 就直接當 code failure。
- 不要平行重做已存在的 parser、Guardian、historical-law verifier 或 health-check pipeline。

---

## 文件分工

- [`README.md`](README.md)：公開專案首頁與產品概覽
- [`docs/AI_MAINTENANCE.md`](docs/AI_MAINTENANCE.md)：AI / 維運長期規則
- `PROJECT_HANDOFF.md`：較細的工程交接與歷史脈絡
- `SECURITY.md`：安全政策
- `CONTRIBUTING.md`：貢獻方式
- Issue `#330`：Public Readiness 主追蹤
- `.github/workflows/`：實際自動化與 CI source of truth

具體任務進度應優先記在 GitHub Issues，而不是繼續新增「今天做到哪」型工作日誌。

---

## 安全與公開原則

Public repository 不代表可以公開 secret、private backup、管理員資料或 production credential。

公開前至少需要：

- 完整 Git history audit
- blocking finding 人工分類
- credential rotation（若真的發現有效 secret）
- identity / privacy review
- branch / ruleset / secret-scanning 治理確認

目前公開收尾以 **Issue #330** 為主。

---

## 授權

Repository visibility 與開源授權是兩件不同的事。

在正式選定並加入 license 前，不應假設 SWSI-authored code 自動採 MIT / Apache / GPL 等授權；考選部、政府與第三方資料的權利也應與 SWSI 自有程式碼分開處理。

---

## 核心原則

> **不要追求「看起來資料很多」；要追求學生真的可以相信。**

> **不要讓 AI 取代證據；讓 AI 幫忙把真正需要人處理的問題找出來。**
