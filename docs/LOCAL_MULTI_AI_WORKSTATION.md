# Local Multi-AI Workstation — low-resource Windows mode

本文件定義如何把一般／舊款 Windows 筆電當成 SWSI 的 **AI 協作控制台**，不是本機大型模型主機。

## 1. 目標

本機只負責：

- 保存 private GitHub repo clone。
- 讓不同 AI CLI 讀同一份 repo。
- 在本機跑 Git、Python、Node、靜態檢查與輕量測試。
- 讓一個 Implementer 寫 branch。
- 讓其他 AI 依序做 reviewer。
- 最後才 push／PR／必要 CI。

AI 推理本身主要仍在雲端完成。

## 2. 不做的事

低資源模式預設**不做**：

- 本機跑大型 LLM。
- 安裝 30B／70B 模型。
- 為了 Council 常駐多個 agent。
- 為普通工作開完整 Docker stack。
- 把 Supabase production 複製成本機常駐服務。
- 讓多個 AI 同時修改同一 branch。

若未來換新機或確有需求，再另做評估。

## 3. 最小工具

建議只保留：

- Git
- 一個編輯器（例如 VS Code；非強制）
- 專案已需要的 Python / Node runtime
- 一個主力 AI CLI
- 一個免費或既有額度 Reviewer CLI（可選）

AI CLI 的安裝與登入方式可能變動，請以各供應商當下官方文件為準；不要把 token 寫入 repo。

## 4. 第一次準備 private repo

在私人工作資料夾 clone：

```powershell
git clone <PRIVATE_REPO_URL>
cd swsi-quiz-backup
git status
```

私有 repo 認證應交給 Git credential manager、官方 CLI 登入流程或 OS 安全儲存；不要把 PAT、API key、service-role key 寫進 `.env.example`、Markdown、聊天貼文或 commit。

## 5. 每次開工

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

再讓它確認最新 PR／Issue／Actions。

## 6. 一個任務的安全流程

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

## 7. Council 怎麼跑最省錢

### 平常

只用一個 AI。

### 中風險

主力 AI 做完，再用一個免費／既有額度模型 review。

### 高風險

才把同一份任務摘要分別給 2–3 個 reviewer，要求獨立分析，再把結果交給 Chair 收斂。

不要讓 Council 變成每次都同時呼叫多個付費模型。

## 8. 舊筆電資源策略

- 一次只開一個主要 AI CLI session。
- 不需要時關掉大型瀏覽器分頁與重型 IDE extension。
- AI reviewer 依序跑，不並行。
- 大量 repo QA 優先用 Python / Node 腳本，而不是本機模型。
- 長時間任務要有 checkpoint commit，避免當機後全丟。
- 若風扇長時間高轉、記憶體吃滿或系統卡頓，先減少並行工具，不要硬撐多 agent。

## 9. 推薦的最低成本拓樸

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

## 10. 第一階段驗收

只要做到以下事項，就已經具備基本多 AI 協作能力：

- private repo 能在本機 clone / pull / branch。
- 主力 AI 能讀 `AGENTS.md` 與 `AI_PROJECT_CONTEXT.md`。
- 第二 AI 能讀相同 repo 並以 reviewer 身分工作。
- 只有一個 AI 寫 branch。
- PR 前能在本機完成基本檢查。
- 不新增任何新的付費服務。

之後若真的需要自動 Council，再另外挑工具，不把 Council 工具本身當第一階段 blocker。
