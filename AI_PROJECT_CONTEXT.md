# SWSI AI Project Context

本檔是 ChatGPT、Codex、Claude、Gemini、Grok 或其他 AI 接手 SWSI 時的**共用專案入口摘要**。它只放相對穩定的專案事實與操作邊界；會快速變動的 HEAD、PR、Issue、queue count、production 狀態必須現查，不可相信本檔中的舊快照。

## 1. 專案是什麼

SWSI 是社工師國考學習平台，長期目標是把歷屆題、申論、模擬考、錯題、弱點分析、法規、理論、時事與 AI 解析整合成一個可長期維運的系統。

核心方向不是無限加功能，而是：

- 官方資料可靠、可追溯。
- AI 加值內容和官方內容清楚分離。
- 資料品質可自動檢查、異常可隔離。
- 平台能在 10／20／30 年尺度下低人力維運、可移轉、可復原。
- 手機可用性、操作順暢度與學生閱讀負擔要持續受控。

## 2. 穩定資料基線

目前官方歷屆 corpus 的穩定基線為：

- 考次：104-1 ～ 115-2，共 24 考次。
- 選擇題：4,800 題。
- 申論題：240 題。
- 合計：5,040 題。

這些數字是目前歷史 corpus 的基線，不代表未來考制永遠固定。未來年度與考制變更必須依正式考制設定與官方證據判斷，不能因為歷史是 5 科／40 題／2 申論就自動假定永遠如此。

## 3. Official Core

下列內容屬官方核心或官方評分契約，不得由 AI 為了讓測試通過而自行改寫：

- 官方題幹
- 官方選項
- 官方答案
- `accepted_answers`
- `grading_mode`

AI 解析、topic、keywords、理論、法規連結、申論 guide、時事關聯等均屬平台加值內容，不得包裝成官方原文。

Official Core 變更必須有官方來源與可追溯證據；相關 AI 加值內容需重新審查或標 stale。

## 4. 主要系統邊界

目前專案主要由以下部分組成：

- GitHub repo：程式、資料契約、文件、workflow 與跨 AI source of truth。
- Supabase：production database、Auth、Edge Functions 與部分同步／分析流程。
- Netlify：正式前端發布。
- Cloudflare Worker / static assets：題庫 shard、公開 AI 路由與部分 CDN 能力。
- GitHub Actions：MOEX、時事、健康檢查、QA、發布驗證等自動流程。

任何 AI 開工前都必須重新確認真實 live state，不要把這些描述當成固定版本。

## 5. 資料品質原則

### 時事
核心鏈：

`新聞／官方資料 -> 社工判讀 -> 社會工作管理 -> 國考五科主／輔科 -> 法規／制度 -> 歷屆考點 -> 學生可讀內容`

- 社會工作管理是上層架構，不是第六科。
- 不可只靠關鍵字分類。
- 重大社工事件不能因不是政策公告就被漏掉。
- 單純出現「社工」職稱也不能自動視為國考重要事件。
- 同一事件多篇報導應增加 evidence，不應灌成多個獨立趨勢事件。

### 法規
- 歷史題優先對照考試當時的法規／政策版本。
- 現行法不得直接倒灌證明舊題。
- 長期要保留：考試當年版本、後續修法、現行版本與來源 provenance。

### AI 解析
- `ready` 不等於逐題人工 verified。
- 反向題、法規數字、年份、例外規定、易混淆理論屬高風險。
- 嚴格 QA 應 fail closed；不要為提高 coverage 放寬驗證。

## 6. 長期維運方向

Issue #262 是 10／20／30 年低人力維運主追蹤。

核心能力包括：

- 考制設定版本化。
- 全庫週期巡檢。
- 任務 registry／漏跑偵測。
- 來源變更追蹤與 stale propagation。
- AI 品質回歸。
- 有上限的自動重試與有限自復原。
- 備份、隔離式還原與異地復原。
- 模型／雲端／排程供應商可替換。
- 可移轉資料格式與維護者接班。

不要把「30 年低人力」理解成「部署一次後 30 年無人處理」。未知例外必須隔離並保留最後可信版本。

## 7. 成本與 GitHub Actions 邊界

專案把每月 **2,000 GitHub Actions 分鐘**視為硬預算。

必讀：`docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md`

預設開發模式：

1. branch 先做完主要修改。
2. 施工期間盡量不要開 PR。
3. 能在本機或靜態檢查完成的，不要為小改動叫 Actions。
4. branch 準備好後才開 PR，集中跑一次必要 CI。
5. merge main 後只保留必要正式驗證。
6. 不為了量測 Actions 再新增一個耗 Actions 的監測 workflow。

任何新的付費 API、模型、雲端方案或訂閱都不是預設允許；必須先取得 owner 明確同意。

## 8. 多 AI 協作原則

必讀：`AGENTS.md` 與 `AI_COLLABORATION.md`

預設低成本模式：

- 一個 AI 當 Implementer，負責實際寫 branch。
- 其他 AI 優先當 read-only Reviewer。
- 不要讓多個 AI 同時修改同一高衝突檔。
- 普通小修不開完整 Council。
- 架構、migration、security、grading、法規時點、release readiness 才值得多 AI 獨立 review。
- 多 AI 一致不等於事實成立；仍要看官方來源、測試與 production evidence。

在舊筆電上使用多 AI 時，電腦只是控制台：repo 在本機，AI 推理仍由雲端模型完成。預設不要安裝本機大型 LLM、Ollama 或其他重型推理環境。

## 9. 開工前必做 live check

任何 AI 不論模型，都應先重新確認：

1. `main` 最新 HEAD。
2. `PROJECT_HANDOFF.md` 最上方最新有效段落。
3. 所有 open PR。
4. 與任務相關的 open Issue。
5. 最近 GitHub Actions 與 production 狀態。
6. 若涉及 Supabase，重新讀 production 真實 schema／function／queue 狀態。
7. 若涉及部署，重新確認目前 Netlify／Cloudflare production 版本。

不要相信任何固定 SHA、舊 queue count 或聊天摘要永遠是最新。

## 10. 高風險禁止事項

未經明確授權與驗證，不得：

- 直接改 Official Core。
- 為 CI 綠燈刪安全檢查。
- 把 secrets、service-role key、token、private backup 寫進 repo／log／Issue。
- 放寬 production RLS／SECURITY DEFINER 權限。
- 讓 AI 自己猜考制變更後直接放行。
- 讓多個 AI 同時直接寫 main。
- 為省時間跳過 rollback／差異檢查。
- 自動啟用新的付費服務。

## 11. 建議閱讀順序

最短接管順序：

1. `AGENTS.md`
2. `AI_PROJECT_CONTEXT.md`
3. `PROJECT_HANDOFF.md`
4. `AI_COLLABORATION.md`
5. `ARCHITECTURE.md`
6. 與當前任務相關的 Issue／audit／docs
7. 最新 commits / PR / Actions / production evidence

## 12. 給任何 AI 的最短接管指令

> 接管 SWSI。先讀 `AGENTS.md`、`AI_PROJECT_CONTEXT.md`、`PROJECT_HANDOFF.md`、`AI_COLLABORATION.md`，再重讀最新 main、open PR、相關 Issue 與 Actions。不要依聊天記憶或舊 SHA 猜現況。你目前若不是明確指定 Implementer，預設只做 reviewer；不要 merge main、不要 production deploy、不要新增付費服務。