# SWSI Multi-AI Collaboration Protocol

本檔定義 ChatGPT、Codex、Claude、Gemini、Grok 或其他 AI 在沒有共享聊天記憶的情況下，如何用最低成本安全協作。

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

## 2. 低預算預設模式

本專案不要求同時訂閱多個付費 AI。

預設策略：

- **一個主力 AI / Implementer**：負責真正讀 repo、寫 branch、修 code。
- **零到一個免費／既有額度 Reviewer**：負責第二意見、找漏洞、看 edge cases。
- Council / 多模型會議只在高風險決策啟用，不是日常預設。
- 任何新的付費 API、模型、雲端方案或訂閱都必須先取得 owner 明確同意。
- 不因某個 reviewer 額度用完就自動改用付費 API。

這樣可以在保留第二意見的同時，避免每月固定養多個昂貴訂閱。

## 3. 本機控制台，而不是本機 AI 主機

若在 owner 的一般／舊款 Windows 筆電上協作：

- 本機只放 private repo、Git、必要 runtime 與 AI CLI。
- AI 推理主要由雲端模型完成。
- 預設一次只跑一個主要 agent；Reviewer 可改成後續順序執行。
- 不要求本機跑大型 LLM。
- 不預設安裝 Ollama、70B/30B 模型、GPU 推理環境或重型 Docker stack。
- 能用 repo 檔案與靜態工具完成的，不要搬成 GitHub Actions。

詳見 `docs/LOCAL_MULTI_AI_WORKSTATION.md`。

## 4. 建議角色

### Chair / Coordinator

- 讀 live handoff。
- 拆 scope。
- 指定唯一 Implementer。
- 防止兩個 Agent 同改高衝突檔。
- 收斂 reviewer 意見。
- 需要時把全平台 contract 決策寫入 `DECISIONS.md`。

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

## 5. 什麼時候需要幾個 AI

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

只適用：全平台架構方向、重大資料模型改造、供應商遷移、release-critical 決策。

Council 不是多數決；最後仍依 contract、測試、官方來源、rollback 與 production evidence 決策。

## 6. 標準協作流程

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

必要時存成 `audit/reviews/` 文件。

### Phase D — 決策

若影響全平台 contract，寫入 `DECISIONS.md`；一般實作細節可由 Coordinator 在任務文件／PR body 固定。

### Phase E — 單一 Implementer 實作

只讓指定 Implementer 寫主工作 branch。

`code -> local/static test -> diff -> checkpoint commit`

### Phase F — 獨立 review

Reviewer 重新讀 diff、contract 與測試，不看作者自評就直接相信。

### Phase G — PR / CI / release

遵守 `docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md`：branch 先做完，PR 最後才開，集中跑必要 CI。

## 7. 多 AI 衝突時怎麼決定

不要用「哪個模型名氣比較大」決定。

依序比較：

1. 是否符合既有 contract。
2. 是否有可重現 evidence。
3. 是否改動較小。
4. 是否 rollback 容易。
5. 是否長期維護較低。
6. 是否符合官方／production evidence。
7. 是否不引入新的付費或 quota 依賴。

若仍無法決定，可保留兩個 prototype 做 benchmark，不要讓兩個版本同時進 main。

## 8. 不建議的模式

- 5 個 AI 同時改同一檔案。
- 每個小 bug 都召開 Council。
- Reviewer 為了顯得有貢獻硬找問題。
- 為讓 CI 綠而降低安全／資料品質標準。
- 把 AI 一致意見當成事實來源。
- 自動切到需要付費的新模型或 API。
- 把多 AI 協作搬到 GitHub Actions 內長時間常駐，持續燃燒 2,000 分鐘額度。

## 9. 跨平台交接模板

> 你是 SWSI 此任務的【角色】。先讀 `AGENTS.md`、`AI_PROJECT_CONTEXT.md`、`PROJECT_HANDOFF.md`、`AI_COLLABORATION.md`，再重讀最新 main、open PR、相關 Issue 與 Actions。你目前只負責【範圍】。若不是指定 Implementer，請保持 read-only，不要 merge main、不要 production deploy、不要新增付費服務。請以 repo、測試、官方來源與 production evidence 提出結論。

## 10. 最終目標

不是讓 AI 們聊天很熱鬧，而是：

`共享 context -> 獨立分析 -> 可驗證證據 -> 明確決策 -> 單一實作 -> 獨立 review -> 必要 CI -> release gate`

如此即使日後換模型、換供應商或只剩一個付費 AI，SWSI 仍能延續。
