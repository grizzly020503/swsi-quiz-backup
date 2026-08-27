# SWSI AGENTS.md

本檔是所有 AI coding agent、聊天模型、Work/Codex/Claude/Gemini 或人工工程師接手本專案時的共同入口。

## 0. 原則

**GitHub repo 是唯一可跨對話、跨模型、跨工具共享的 source of truth。**

不要把聊天記憶、私人 scratchpad、單一 Work session 或某個 AI 的口頭摘要視為專案真相。若決策、修正或測試結果沒有寫回 repo，它對下一個接手者而言就不存在。

## 1. 接手前必讀順序

1. `AGENTS.md`
2. `PROJECT_HANDOFF.md`
3. `ARCHITECTURE.md`
4. `KNOWN_ISSUES.md`
5. `DECISIONS.md`
6. `TESTING.md`
7. `RELEASE.md`
8. 最近 commits / PR / GitHub Actions
9. 與當前工作相關的 `audit/` 文件

讀完後才開始修改程式。不要重新猜架構，不要重做 handoff 已標示完成的工作。

## 2. 目前工作分支

程式健康修復工作目前集中在：

`fix/code-health-p0-20260826`

除非 `PROJECT_HANDOFF.md` 已更新成其他 branch，否則 P0/P1 修復請延續此 branch。

## 3. 不可違反的工程規則

### Grading
- `grading_mode` 合法值只允許 `standard / all_credit / any_answer`。
- 特殊給分 metadata 缺失或不一致時 **fail closed**。
- 不得從題目 ID、答案文字「一律給分／送分」或其他 legacy heuristic 猜特殊給分模式。
- 一般刷題、模擬考、複習、錯題紀錄必須共用相同 grading contract。

### 歷史題／法規
- 歷史考題必須使用「考試當時」法規／政策版本。
- 不得用現在的法條、2026 後政策或現行制度倒灌舊考題。
- 法規監測的「目前沒變」不能自動替歷史題背書。

### 題庫完整性
- 官方題幹、選項、答案、accepted_answers、grading_mode 視為 Official Core。
- CDN shard 必須做實際 SHA-256 驗證，不可只相信 manifest metadata。
- 官方核心異動後，相關 AI 解析／加值內容必須被重新審核或清除。

### 安全
- 不得為了 CI 綠燈刪除安全檢查。
- 不得把 secrets、service-role key、API key、token 寫入 repo、log、audit 或測試 fixture。
- Production `SECURITY DEFINER` functions 不得開給 `PUBLIC/anon/authenticated`，除非有明確安全設計與審核。

### 發布
- 不得未經使用者明確授權直接 merge `main` 或部署正式 Netlify。
- 修復 branch 可以跑 CI、Cloudflare preview、browser smoke。
- 不可逆 production 操作必須停下來要求本人確認。

## 4. 修改流程

每完成一個可獨立驗證的修正：

1. 修改程式。
2. 跑對應 syntax / unit / smoke / browser test。
3. 檢查 diff 與 secrets。
4. 測試通過後立即 commit。
5. 再進下一組修正。

**不要累積數小時的未 commit 工作。** 長時間 Agent 若額度中斷，至少已完成成果必須已持久化到 branch。

## 5. 多 AI 協作規則

不同 AI 可以扮演不同角色，但共享同一 repo 狀態：

- Coordinator / PM：拆任務、維護 handoff、控制 scope。
- Architect：審架構與長期技術債，不直接覆蓋其他人的實作。
- Implementer：實際改 code。
- QA：只依需求與 contract 驗證，不為了讓測試過而降低標準。
- Security reviewer：看 secrets、RLS、RPC、XSS、quota、部署風險。
- Content reviewer：看題幹、法規版本、申論 guide 與官方來源。
- Release reviewer：只判斷是否達到 merge / deploy gate。

若多 Agent 同時工作：
- 優先分不同 branch / worktree / 任務範圍。
- 不要兩個 Agent 同時修改同一個高衝突大檔。
- 每個 Agent 完成後 commit，再由 Reviewer 比較 diff。
- 發生設計衝突時，把結論寫入 `DECISIONS.md`，不要只留在聊天裡。

## 6. 交班要求

每次工作階段結束前，更新 `PROJECT_HANDOFF.md` 至少包含：

- Current branch / HEAD
- 本階段完成項目
- 已跑測試與結果
- 剩餘 P0/P1
- 真正 blocker
- 下一步 3–8 項
- 是否建議 merge

如果無法修改 handoff，至少必須把工作成果 commit，並在 commit message / PR body 留明確狀態。

## 7. 對 AI 的最短接管指令

新的 AI 只需要收到：

> 接管 SWSI repo。先依 `AGENTS.md` 的順序閱讀專案文件、目前 branch、最近 commits 與 CI；不要依聊天記憶猜架構。確認 handoff 後從 Next Actions 繼續，能自行處理的直接做，完成一組就測試並 commit。

詳細規則以 repo 文件為準。