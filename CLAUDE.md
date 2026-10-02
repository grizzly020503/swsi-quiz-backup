# Claude entrypoint for SWSI

Claude 接手本 repo 時，不要把本檔當完整專案說明；它只是入口。

## 必讀順序

1. `AGENTS.md`
2. `AI_PROJECT_CONTEXT.md`
3. `PROJECT_HANDOFF.md`
4. `AI_COLLABORATION.md`
5. 與當前任務相關的 Issue / docs / audit
6. 最新 main / open PR / Actions / production evidence

## 預設角色

除非 owner 或 Coordinator 明確指定你是 Implementer，否則預設以 **Reviewer** 身分工作：

- 可讀 repo、分析架構、找 edge cases、review diff。
- 不要自行搶寫另一個 AI 正在處理的 branch。
- 不要直接 merge main。
- 不要 production deploy。
- 不要啟用新的付費 API／模型／服務。

## 若你是 Implementer

- 遵守 branch-first / PR-last。
- 先本機／靜態驗證，再集中開 PR。
- Official Core、grading、歷史法規、安全邊界以 `AGENTS.md` 為準。
- 完成後留下 commit／PR／Issue evidence，不要只在聊天裡說「已完成」。

## 成本

SWSI 把每月 2,000 GitHub Actions 分鐘視為硬預算。不要為普通小改動反覆觸發 CI；詳見 `docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md`。

## 最短接管句

> 先讀 SWSI 共用 context 與 live GitHub 狀態。若未指定 Implementer，保持 read-only reviewer；依 contract、測試與 evidence 提出結論。
