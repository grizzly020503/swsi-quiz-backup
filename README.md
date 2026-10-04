# 社工師國考免費學習平台（SWSI）

SWSI 是一個以 **免費、低門檻、資料可信與可長期維護** 為核心的社工師國考學習平台。

目前重點不是繼續堆功能，而是把既有題庫、解析、法規、時事與自動維運做深、做穩、做可信。

## 目前內容

- ROC 104–115，共 24 個考次
- 官方選擇題：4,800 題
- 官方申論題：240 題
- 官方題庫合計：5,040 題

## 學生端核心

1. **刷選擇題**：依年份、考次、科目與弱點練習歷屆題。
2. **錯題複習**：錯題本、弱點整理與間隔複習。
3. **申論練習**：歷屆申論、答題架構與輔助回饋。

其他能力包括法規與歷史法規追蹤、理論／考點整理、時事雷達、題庫健康檢查、自動同步新考次、資料品質 review queue、管理後台與監控。

原則是：**前台做減法，後台做自動化。**

## 資料可信度

SWSI 明確區分官方資料與平台加工內容。

### Official Core

包含官方題目、選項、答案、`accepted_answers`、`grading_mode` 與官方申論題。

Official Core 不應因模型推論、關鍵字規則或一般內容整理而被直接改寫。

### Enrichment Layer

包含解析、topic／keywords、理論與法規關聯、申論 guide、時事與歷屆題關聯等。

這些內容可由程式或 AI 協助產生，但必須受 QA、來源與 provenance 規則管理。

> 有解析不等於已人工 verified；有 law metadata 不等於已證明直接法源。

## 系統架構

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

AI 相關功能採獨立 gateway / quota / safety boundary。即使 AI 暫時不可用，核心刷題與非 AI 學習功能仍應維持正常。

更完整架構見 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

## 長期維運

SWSI 希望逐步形成：

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
輔助 review
  ↓
Human / Quarantine（少數 conflict）
  ↓
版本化結果 + Health Report
```

維運原則與資料邊界見 [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md)。

## 專案文件

- [`ARCHITECTURE.md`](ARCHITECTURE.md)：系統架構
- [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md)：長期維運與資料規則
- [`TESTING.md`](TESTING.md)：測試與驗收
- [`SECURITY.md`](SECURITY.md)：安全政策
- [`CONTRIBUTING.md`](CONTRIBUTING.md)：貢獻方式
- [`AGENTS.md`](AGENTS.md)：自動化工具與程式代理的最低操作邊界
- GitHub Issues / Pull Requests：目前任務、決策與進度的主要來源

不再以根目錄的聊天交接稿、模型專屬 prompt 或「今天做到哪裡」日誌作為專案入口。

## 安全

Public repository 不代表可以公開 secret、private backup、管理員資料、使用者原始資料或 production credential。

不要把 service-role key、provider token、密碼、MFA / recovery code、private backup 或其他 credential 寫進 Git、Issue、PR、log 或 artifact。

## 授權

Repository visibility 與開源授權是兩件不同的事。

在正式選定並加入 license 前，不應假設 SWSI-authored code 自動採 MIT / Apache / GPL 等授權；考選部、政府與第三方資料的權利也應與 SWSI 自有程式碼分開處理。

## 核心原則

> **不要追求「看起來資料很多」；要追求學生真的可以相信。**
