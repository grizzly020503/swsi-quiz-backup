# Local Multi-AI Workstation — low-resource Windows mode

本文件定義如何把一般／舊款 Windows 筆電當成 SWSI 的 **AI 協作控制台／中繼站**，不是本機大型模型主機。

> **目前與目標要分開看：**
>
> - **Current mode**：目前已可使用 private repo + AI CLI + Git/Python/Node，必要時人工啟動一個 Implementer／Reviewer。
> - **Target mode**：Issue #290 的 **SWSI Council Relay**。Windows 登入後背景自啟，owner 不需要每次開 PowerShell、Antigravity 或其他 CLI，也不需要人工複製各 AI 回覆。
>
> Target architecture：`docs/AI_COUNCIL_RELAY_ARCHITECTURE.md`。

## 1. 目標

本機只負責：

- 保存 private GitHub repo clone。
- 讓不同 AI CLI／adapter 讀同一份 repo。
- 在本機跑 Git、Python、Node、靜態檢查與輕量測試。
- 讓一個 Implementer 寫 branch。
- 讓其他 AI 依序做 reviewer。
- 最後才 push／PR／必要 CI。
- Target mode 下，背景 Relay 自動從 GitHub durable queue 接任務並回寫結果。

AI 推理本身主要仍在雲端完成。

## 2. 不做的事

低資源模式預設**不做**：

- 本機跑大型 LLM。
- 安裝 30B／70B 模型。
- 為了 Council 同時常駐多個 agent。
- 為普通工作開完整 Docker stack。
- 把 Supabase production 複製成本機常駐服務。
- 讓多個 AI 同時修改同一 branch。
- 用 GitHub Actions 當永遠在線的 Council orchestrator。

若未來換新機或確有需求，再另做評估。

## 3. 最小工具

建議只保留：

- Git
- GitHub CLI
- 一個編輯器（例如 VS Code；非強制）
- 專案已需要的 Python / Node runtime
- 一個主力 AI CLI／adapter
- 一個免費或既有額度 Reviewer CLI／adapter（可選）
- Target mode 的輕量 Council Relay process

AI CLI 的安裝與登入方式可能變動，請以各供應商當下官方文件為準；不要把 token 寫入 repo。

## 4. 第一次準備 private repo

在私人工作資料夾 clone：

```powershell
git clone <PRIVATE_REPO_URL>
cd swsi-quiz-backup
git status
```

私有 repo 認證應交給 Git credential manager、官方 CLI 登入流程或 OS 安全儲存；不要把 PAT、API key、service-role key 寫進 `.env.example`、Markdown、聊天貼文或 commit。

## 5. Current mode：每次開工

```powershell
git fetch origin
git switch main
git pull --ff-only
git status
```

然後讓 AI 先讀：

1. `AGENTS.md`
2. `AI_PROJECT_CONTEXT.md`
3. `PROJECT_HANDOFF.md`
4. `AI_COLLABORATION.md`
5. 若涉及自動 Council：`docs/AI_COUNCIL_RELAY_ARCHITECTURE.md`

再讓它確認最新 PR／Issue／Actions。

這一節是**目前手動／半手動 fallback**。Target Relay 完成後，這些 freshness check 應由背景程式自動執行，不要求 owner 每次親自輸入命令。

## 6. Current mode：一個任務的安全流程

### A. 先建立工作 branch

```powershell
git switch -c task/<short-name>
```

### B. 指定角色

預設：

- 主力 AI = Implementer
- 第二 AI = Reviewer

普通任務不要同時開兩個寫入 agent。

### C. Implementer 完成主要修改

先用本機能做的檢查：

- syntax
- unit / smoke
- JSON / schema validation
- `git diff --check`
- `git status`
- diff review

### D. Reviewer 後跑

Reviewer 看：

- diff
- contract
- edge cases
- 是否有 secrets
- 是否破壞 Official Core
- 是否真的需要 GitHub Actions

Reviewer 預設不直接修改 branch；若發現問題，先回報，交 Implementer 修。

### E. 最後才 push / PR

符合 `docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md`：

- branch 施工期不要為每個 commit 開 PR。
- 準備好才 push／開 PR。
- PR 後只有真實 CI finding 才追加修改。

## 7. Target mode：背景 Council Relay

Target mode 的正常使用不應要求 owner 執行第 5、6 節的日常 CLI 步驟。

理想流程：

```text
Owner 在手機／平板／其他電腦下任務
        -> GitHub durable Council Task
        -> Lenovo 目前若關機：保持 queued
        -> 下次 Windows 登入：Relay 自動啟動
        -> fetch / freshness / clean-worktree checks
        -> 依任務等級順序呼叫 AI adapters
        -> Coordinator 收斂
        -> 需要實作時只啟用單一 Implementer
        -> reviewer 驗證 exact diff / tests
        -> 結果回 GitHub
```

### 正常使用要求

- 不要求 owner 開 PowerShell。
- 不要求 owner 開 Antigravity／Claude／其他 AI CLI 視窗。
- 不要求 owner 把 AI A 的整篇回答複製給 AI B。
- 沒有任務時不啟動 AI process。
- 一次只跑一個主要 provider process。
- 發生錯誤時要留下本機 log 與 GitHub durable status，不可 silent fail。

## 8. Council 怎麼跑最省錢

### 平常

只用一個 AI。

### 中風險

主力 AI 做完，再用一個免費／既有額度模型 review。

### 高風險

才把同一份 frozen task brief 交給 2–3 個 reviewer 獨立分析，再由 Coordinator 收斂。

Target Relay 即使能自動呼叫多個模型，也**不能**變成每次固定叫四個付費模型。

## 9. 舊筆電資源策略

- 一次只開／啟動一個主要 AI CLI process。
- 不需要時不常駐大型瀏覽器分頁與重型 IDE extension。
- AI reviewer 依序跑，不並行。
- 大量 repo QA 優先用 Python / Node 腳本，而不是本機模型。
- 長時間任務要有 durable checkpoint，避免當機後全丟。
- Relay idle 時應低 CPU / RAM。
- 每個 provider process 都要有 timeout 與 bounded retry。
- 若風扇長時間高轉、記憶體吃滿或系統卡頓，Relay 應停止擴大並行，而不是硬撐多 agent。

## 10. 推薦拓樸

### Current mode

```text
Private GitHub repo
        |
        v
Windows laptop local clone
        |
        +--> Main AI CLI (Implementer)
        |
        +--> Free/existing-quota AI CLI (Reviewer, sequential)
        |
        +--> Local Git/Python/Node checks
        |
        v
One branch -> one PR -> necessary CI -> main
```

### Target mode

```text
Any device / GitHub-capable AI
        |
        v
Private GitHub Council Queue
        |
        v
Windows background Relay
        |
        +--> Provider adapters (sequential)
        +--> Git / local checks
        |
        v
Coordinator -> single Implementer -> Verification Council
        |
        v
GitHub durable result / PR / evidence
```

## 11. Current baseline 已完成的能力

目前已具備：

- private repo 能在本機 clone / pull / branch。
- GitHub CLI 已登入 private repo。
- Node 已可用；PowerShell 下可用 `.cmd` wrapper 避免 ExecutionPolicy 問題。
- Gemini / Antigravity 已完成登入。
- Antigravity 已能讀相同 private repo 並以 read-only reviewer 身分正確理解 SWSI contract。
- 只有一個 AI 應寫 branch。
- 不新增任何新的付費服務。

這些能力是 Target Relay Phase 1 的基礎，不需要重做。

## 12. Target Relay 第一階段驗收

真正的 Relay MVP 不是「能開 Gemini CLI」，而是：

1. GitHub 已存在一個 queued Council review task。
2. Lenovo 可在 task 建立時處於關機狀態。
3. Lenovo 下次登入後 Relay 自動啟動。
4. Relay 自動同步 repo 並 claim task。
5. Antigravity 自動以 read-only reviewer 執行。
6. 審查結果自動寫回 GitHub。
7. owner 不需要開 terminal、不需要貼提示、不需要搬回覆。
8. Windows 重啟後不得重複提交同一結果。
9. 不為此啟動不必要 GitHub Actions。
10. 不需要新增付費 API。

Tracking: **Issue #290**。
