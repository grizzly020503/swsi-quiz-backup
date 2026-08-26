# SWSI Multi-AI Collaboration Protocol

本檔定義如何讓 ChatGPT、Claude、Gemini、Codex、Work 或其他 AI 在沒有共享聊天記憶的情況下協作。

## 1. 核心原理

不同 AI **不假設彼此能直接看到聊天內容**。

共享狀態只透過：
- Git branch / commit
- `PROJECT_HANDOFF.md`
- `AGENTS.md`
- `DECISIONS.md`
- `KNOWN_ISSUES.md`
- review / audit 文件
- CI / test artifacts

任何只存在某 AI 對話裡的決策，都視為「尚未同步」。

## 2. 建議角色

### Chair / Coordinator
責任：
- 讀 handoff。
- 拆 scope。
- 指派角色。
- 防止兩個 Agent 同改高衝突檔。
- 收斂不同 reviewer 意見。
- 決定哪些問題升級成 `DECISIONS.md`。

Chair 不應只因自己偏好推翻已有 contract。

### Product / PM Reviewer
關注：
- 考生價值。
- scope creep。
- 是否真的需要新增功能。
- 免費、低門檻、手機體驗。

### Architecture Reviewer
關注：
- 模組邊界。
- patch 疊 patch。
- source of truth。
- 長期維護成本。
- migration / rollback。

### Implementer
責任：
- 根據已定 contract 實作。
- 一組修正一個 checkpoint commit。
- 不偷偷改產品需求。

### QA Reviewer
關注：
- regression。
- edge cases。
- browser smoke。
- data integrity。
- CI 是否真的測到行為，而非只 grep 字串。

### Security Reviewer
關注：
- secrets。
- RLS / RPC / SECURITY DEFINER。
- XSS。
- rate limit / abuse。
- production permissions。

### Content / Legal Reviewer
關注：
- 題幹與答案是否對題。
- 歷史法規版本。
- 政策時點。
- 官方來源與 SWSI 自製內容界線。

### Release Reviewer
只回答：
- 是否達到 `RELEASE.md` gate？
- 是否建議 merge？
- 是否建議 production deploy？

## 3. 一個任務的標準協作流程

### Phase A — 問題定義
Coordinator 建立任務摘要：
- 問題
- 影響
- 驗收條件
- 可修改範圍
- 禁止操作

### Phase B — 獨立分析
若問題風險高，可讓 2 個 reviewer **獨立分析**，避免互相錨定。

例如：
- Claude：架構 review
- ChatGPT：資料／grading review
- Gemini：測試／edge-case review

不要一開始把第一個 AI 的結論完整餵給其他 reviewer；先讓它們各自產生判斷。

### Phase C — 交叉審查
將不同分析寫入短 review 文件，例如：

`audit/reviews/<task>-architecture.md`
`audit/reviews/<task>-qa.md`
`audit/reviews/<task>-security.md`

Chair 比較：
- 共識
- 衝突
- 證據
- 風險

### Phase D — 決策
若只是實作細節，Chair 選一個方案。

若會影響全平台 contract，寫入 `DECISIONS.md`。

決策必須包含：
- chosen option
- rejected alternatives
- why
- migration / rollback impact

### Phase E — 實作
Implementer 在獨立 branch/worktree 寫 code。

每一組可獨立驗證的修改：
`code -> test -> diff -> commit`

### Phase F — Reviewer 不看作者自評
Reviewer 重新讀 diff、contract 與測試，不以 Implementer 的「我已修好」作為證據。

### Phase G — Release
只有 Release Reviewer 依 `RELEASE.md` 判定可否 merge / deploy。

## 4. 多 AI 發生衝突時

不要用「Claude 比 ChatGPT 強」或「某模型比較會寫 code」直接決定。

依序比較：
1. 哪個方案符合既有 contract。
2. 哪個有可重現測試證據。
3. 哪個改動範圍較小。
4. 哪個 rollback 較容易。
5. 哪個長期維護成本較低。
6. 哪個有官方／production evidence。

若仍無法決定，保留兩方案做 prototype / benchmark，再選。

## 5. 不建議的模式

### 不要讓 5 個 AI 同時改同一個檔案
這只會增加 merge conflict，並不等於五倍品質。

### 不要讓「主席」只做多數決
AI 可能共享相似訓練偏誤。三個模型都說同一句不代表一定正確；仍要看 source、test、production evidence。

### 不要互相無限 review
每個任務最多設定必要 reviewer。普通小 bug 不需要開完整「AI 董事會」。

## 6. 什麼任務值得多 AI

推薦：
- grading contract
- 資料庫 migration
- auth / security
- 大型重構
- 法規歷史版本
- release readiness
- 高風險 architecture decision

不推薦：
- 改一個文案
- 一個明確 CSS bug
- 已有 regression test 的小修

## 7. 跨平台交接模板

把任務交給任何 AI 時，可使用：

> 你是 SWSI 此任務的【角色名稱】。先讀 `AGENTS.md`、`PROJECT_HANDOFF.md` 與與此角色相關的專案文件。不要依聊天記憶猜架構。你目前只負責【範圍】；不要 merge main、不要 production deploy。請用 repo 現況、測試與證據提出結果，完成後把可持久化的結論寫回 branch / audit / decision 文件。

## 8. 最終目標

不是讓 AI 們「聊天看起來很熱鬧」，而是建立：

`獨立分析 -> 可驗證證據 -> 明確決策 -> 實作 -> 獨立 review -> CI -> release gate`

如此即使半年後換成完全不同的 AI，專案仍能延續。