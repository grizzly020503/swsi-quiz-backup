# SWSI Multi-AI Collaboration Protocol

本檔定義 ChatGPT、Codex、Claude、Gemini、Grok 或其他 AI 在沒有共享聊天記憶的情況下，如何用最低成本安全協作。

> **兩層模式，請勿混淆：**
>
> 1. **Current mode**：現在已可立即使用的低成本「單一 Implementer + Reviewer」模式。
> 2. **Target mode**：Issue #290 定義的背景式 **SWSI AI Council Relay**。它的目標是讓 owner 不必人工搬運各 AI 回覆、不必每次手動開 CLI，由 Windows 背景中繼站 + GitHub 任務池自動協調多模型。
>
> Target architecture 詳見 `docs/AI_COUNCIL_RELAY_ARCHITECTURE.md`。在 Relay 尚未實作完成前，不得假裝自動 Council 已存在。

## 1. 核心原理

不同 AI **不假設彼此能看到聊天內容**。

共享狀態只透過：

- Git branch / commit / PR
- `AGENTS.md`
- `AI_PROJECT_CONTEXT.md`
- `PROJECT_HANDOFF.md`
- `DECISIONS.md`
- `KNOWN_ISSUES.md`
- Issue / audit / test artifacts

任何只存在某個 AI 對話裡的決策，都視為尚未同步。

未來 Council Relay 也必須遵守同一原則：**模型之間不靠共享聊天記憶，而靠 GitHub durable task/evidence state 協作。**

## 2. 低預算預設模式（目前可用）

本專案不要求同時訂閱多個付費 AI。

預設策略：

- **一個主力 AI / Implementer**：負責真正讀 repo、寫 branch、修 code。
- **零到一個免費／既有額度 Reviewer**：負責第二意見、找漏洞、看 edge cases。
- Council / 多模型會議只在高風險決策啟用，不是日常預設。
- 任何新的付費 API、模型、雲端方案或訂閱都必須先取得 owner 明確同意。
- 不因某個 reviewer 額度用完就自動改用付費 API。

這樣可以在保留第二意見的同時，避免每月固定養多個昂貴訂閱。

## 3. 目標模式：背景自動 AI Council Relay

Issue #290 定義的長期目標不是讓 owner 每次手動：

`開筆電 -> 開 CLI -> 貼提示 -> 複製 AI 回覆 -> 貼給另一個 AI`

而是：

`任意裝置下任務 -> GitHub durable queue -> Windows 背景 Relay -> 獨立 AI proposals -> Coordinator -> 單一 Implementer -> Verification Council -> GitHub result`

Target mode 的基本規則：

- Lenovo 舊筆電只當輕量中繼站，不當大型模型主機。
- Windows 登入後 Relay 背景自啟，正常情況不要求 owner 開 PowerShell 或 AI CLI 視窗。
- 電腦關機時，任務可留在 GitHub queued；下次開機再自動接續。
- 多個 Council Members 第一輪獨立分析，不先互看答案，降低 anchoring。
- Coordinator 依 evidence 收斂，不以模型票數決定真假。
- 一次只有一個 Implementer 可寫 branch。
- 實作完成後，Reviewer 重新看 exact diff + tests，而不是只看作者摘要。
- Provider 必須透過 adapter 接入；未驗證的 Claude / Grok / 其他 provider 預設 disabled。
- Relay 不得成為 SWSI 正式營運 blocker。

## 4. 本機控制台／中繼站，而不是本機 AI 主機

若在 owner 的一般／舊款 Windows 筆電上協作：

- 本機只放 private repo、Git、必要 runtime 與 AI CLI／adapter。
- AI 推理主要由雲端模型完成。
- 預設一次只跑一個主要 agent；Reviewer 依序執行。
- 不要求本機跑大型 LLM。
- 不預設安裝 Ollama、70B/30B 模型、GPU 推理環境或重型 Docker stack。
- 能用 repo 檔案與靜態工具完成的，不要搬成 GitHub Actions。

目前手動／半手動操作詳見 `docs/LOCAL_MULTI_AI_WORKSTATION.md`；目標背景 Relay 詳見 `docs/AI_COUNCIL_RELAY_ARCHITECTURE.md`。

## 5. 建議角色

### Chair / Coordinator

- 讀 live handoff。
- 拆 scope。
- 指定唯一 Implementer。
- 防止兩個 Agent 同改高衝突檔。
- 收斂 reviewer 意見。
- 需要時把全平台 contract 決策寫入 `DECISIONS.md`。
- 在 Council 模式中，必須分辨「共識」與「真正被 evidence 證實」。

### Implementer

- 唯一主要寫入者。
- 根據既有 contract 實作。
- 不偷偷改產品需求。
- 先 branch，後 PR。
- 使用 checkpoint commit，但避免為每個小步驟觸發昂貴 CI。

### Architecture Reviewer

看：模組邊界、source of truth、長期維護、migration、rollback、供應商替換。

### QA Reviewer

看：regression、edge cases、data integrity、是否真的測到行為。

### Security Reviewer

看：secrets、RLS、RPC、SECURITY DEFINER、XSS、rate limit、production permissions。

### Content / Legal Reviewer

看：官方題目界線、歷史法規版本、政策時點、來源證據、申論 guide。

### Release Reviewer

只回答：是否達到既有 release gate、是否建議 merge／deploy。

## 6. 什麼時候需要幾個 AI

### Level 0 — 不需要多 AI

適用：文案、小 CSS bug、已有 regression test 的明確小修。

做法：單一 Implementer。

### Level 1 — 一主一審

適用：一般功能修改、資料 pipeline 中風險變更、workflow 調整。

做法：

1. Implementer 完成 branch。
2. 一個 Reviewer 看 diff／測試。
3. 有真實問題才回寫 branch。

### Level 2 — 獨立雙審

適用：grading、資料庫 migration、auth/security、歷史法規、重要架構。

做法：兩個 Reviewer 先獨立分析，避免互相錨定，再由 Chair 比較共識與衝突。

### Level 3 — Council

適用：全平台架構方向、重大資料模型改造、供應商遷移、release-critical 決策。

Target Relay 完成後，Level 2/3 可由背景 orchestrator 自動安排；在此之前仍可人工／半人工執行。

Council 不是多數決；最後仍依 contract、測試、官方來源、rollback 與 production evidence 決策。

## 7. 標準協作流程

### Phase A — 問題定義

Coordinator 準備：

- 問題
- 影響
- 驗收條件
- 可修改範圍
- 禁止操作
- 成本／Actions 限制

### Phase B — 獨立分析

高風險問題可讓不同 reviewer 先各自回答，不先互看結論。

### Phase C — 收斂

比較：

- 共識
- 衝突
- 證據
- 風險
- rollback
- 成本

必要時存成 `audit/reviews/` 文件或 Council Task result。

### Phase D — 決策

若影響全平台 contract，寫入 `DECISIONS.md`；一般實作細節可由 Coordinator 在任務文件／PR body 固定。

### Phase E — 單一 Implementer 實作

只讓指定 Implementer 寫主工作 branch。

`code -> local/static test -> diff -> checkpoint commit`

### Phase F — 獨立 review

Reviewer 重新讀 diff、contract 與測試，不看作者自評就直接相信。

### Phase G — PR / CI / release

遵守 `docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md`：branch 先做完，PR 最後才開，集中跑必要 CI。

## 8. Evidence Freshness Rule

任何 AI 若聲稱「目前是 X」，應盡量附：

- `evidence_timestamp`
- `evidence_source`
- exact SHA / run ID / deployment ID / production target（能取得時）
- freshness：`live | current_remote | snapshot | historical`

一般衝突時，優先核對：

1. 正式官方來源／既有不可變 contract（適用時）
2. live production evidence
3. GitHub remote / exact deployment evidence
4. current source/data file
5. tests / reproducible output
6. handoff / docs snapshot
7. AI inference

不要把 `PROJECT_HANDOFF.md`、舊 audit、local clone 或 AI 記憶中的快照當成永遠的 current truth。

## 9. 多 AI 衝突時怎麼決定

不要用「哪個模型名氣比較大」決定。

依序比較：

1. 是否符合既有 contract。
2. 是否有可重現 evidence。
3. evidence 是否夠新、來源是否正確。
4. 是否改動較小。
5. 是否 rollback 容易。
6. 是否長期維護較低。
7. 是否符合官方／production evidence。
8. 是否不引入新的付費或 quota 依賴。

若仍無法決定，可保留兩個 prototype 做 benchmark，不要讓兩個版本同時進 main。

## 10. 不建議的模式

- 5 個 AI 同時改同一檔案。
- 每個小 bug 都召開 Council。
- Reviewer 為了顯得有貢獻硬找問題。
- 為讓 CI 綠而降低安全／資料品質標準。
- 把 AI 一致意見當成事實來源。
- 自動切到需要付費的新模型或 API。
- 把多 AI 協作搬到 GitHub Actions 內長時間常駐，持續燃燒 2,000 分鐘額度。
- 要求 owner 長期擔任 AI 之間的人工 copy/paste 中繼站。
- 未驗證某 provider integration 就宣稱它已能自動參與 Council。

## 11. 跨平台交接模板

> 你是 SWSI 此任務的【角色】。先讀 `AGENTS.md`、`AI_PROJECT_CONTEXT.md`、`PROJECT_HANDOFF.md`、`AI_COLLABORATION.md`；若任務涉及自動多 AI 協作，再讀 `docs/AI_COUNCIL_RELAY_ARCHITECTURE.md`。再重讀最新 main、open PR、相關 Issue 與 Actions。你目前只負責【範圍】。若不是指定 Implementer，請保持 read-only，不要 merge main、不要 production deploy、不要新增付費服務。請以 repo、測試、官方來源與 production evidence 提出結論。

## 12. 最終目標

現在：

`共享 context -> 獨立分析 -> 可驗證證據 -> 明確決策 -> 單一實作 -> 獨立 review -> 必要 CI -> release gate`

目標 Relay：

`任意裝置提交 -> GitHub durable queue -> 背景獨立分析 -> Coordinator evidence reconciliation -> 單一實作 -> Verification Council -> GitHub durable result`

如此即使日後換模型、換供應商、筆電關機後再開、或只剩一個付費 AI，SWSI 仍能延續。

Primary Council Relay tracking: **Issue #290**。
