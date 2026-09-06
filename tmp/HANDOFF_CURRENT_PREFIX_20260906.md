# SWSI 社工師國考平台 — 專案交接／續聊清單

## 2026-09-06 最新營運狀態（READ FIRST）

> **本節是目前最高優先級的接手基線。** 下方 2026-08-27 Round 8 與其他歷史章節保留作稽核紀錄；若 SHA、part 數量、branch、部署狀態或「下一步」與本節衝突，以本節與遠端真實狀態為準。每次接手仍必須先重新讀 `main`、Actions、open PR/issues，不可把任何 SHA 當永久最新。

### 最新基線

- 本 handoff refresh 建於 `main@5ce724fcba9bf9204e2f8c8889ef9cd01d9921c9`；合併本 docs-only handoff 後 `main` 會再前進，接手時務必重新讀遠端 HEAD。
- canonical runtime source：`monthly_patch_parts/*.part`，目前維持 **38 parts 上限**；generated runtime 為 `cdn/monthly_patch.js`。
- 官方選擇題庫仍為 **4,800 題**；官方 shard wording / answer / grading source 不因前端顯示修正而改寫。
- 學生端核心：做題 → 解析 → 錯題／複習 → 弱點 → 申論 → AI 回饋；核心刷題不依賴 AI 額度才能運作。
- Netlify production 本輪沒有被修改；除非使用者明確要求，仍不要把 Netlify 當作這輪的變更目標。

### 2026-09-06 已完成且不要重做

1. **承上題／承前題 standalone context 修復**
   - #57 修復「承上題」類官方題目被單獨抽出時失去前題情境的問題。
   - 官方 shard 保持唯讀；只做 presentation-only context adapter。
   - 初版新增第 39 個 runtime part，main 的 Runtime Owner QA 正確抓到結構回歸。
   - #58 把 adapter 折回既有 `code_health_p0` late `renderQuiz` owner，runtime 回到 38 parts；Dependent Question Context QA 與 Runtime Owner QA 均通過。

2. **Feedback modal accessibility race 修復**
   - #58 同時修掉 feedback modal `setTimeout(...focus(), 30)` 對 Shift+Tab focus trap 的搶焦點 race。
   - 改成 dialog 插入後立即 initial focus；Launch Readiness Chromium/WebKit/mobile/accessibility smoke 已通過。

3. **Monitoring V2 正式上線**
   - 舊 #56 因 #57/#58 後 main 漂移而關閉、不合併。
   - #59 從 post-bugfix main 乾淨 refresh，generated runtime 由最新 38 canonical parts 重建，不複製 stale runtime。
   - Five-radar：時事、法規、題庫、系統、feedback 公開監測；Public Uptime、Knowledge Snapshot、Storage、Usage Analytics、Monthly Frontend、Launch Readiness 等 exact-head gates 通過。
   - #59 merge commit：`e502ddf5fff0b6cec9a1e6526eb6f919c6c56235`（歷史證據；不是永久最新 HEAD）。

4. **MOEX／MOJ 真實同步已驗證**
   - 2026-09-06 正式同步完整通過：時事掃描、MOJ 法規檢查、官方考題 fetch、local question-bank health、Supabase changed-only import、Supabase health、verified payload commit。
   - bot commit `1b6b99eda95d68b7eb589e19c8e9924028bb4abe` 只更新 legal-watch internal state/report，沒有覆蓋 runtime。
   - 真實偵測到 **民法** official modified date `2021-01-20 → 2026-08-17`，52/52 laws matched，`changed_count=1`。

5. **Public legal-watch 即時發布閉環**
   - 上線後發現 internal `data/legal_watch_report.json` 已抓到民法變更，但 public `auto/legal_watch.json` 尚停在舊 snapshot。
   - 根因：Public Monitoring Feed 原本只有 schedule / PR trigger，MOEX bot 更新 main 後不會立即刷新 public legal snapshot。
   - #60 增加 main-only `push` trigger，僅監聽 workflow 本身與 `data/legal_watch_report.json`；**不監聽 `auto/legal_watch.json`**，避免 monitoring bot 自觸發 loop。
   - 第一版 regression 因註解字串造成 false positive；已修為只解析 YAML list entries，不放寬功能條件。
   - production run 真實產生：`Public legal-watch snapshot updated: 52/52 matched, changed=1`，publish step success。
   - monitoring bot commit `79cf778a36914d9751f7b4bbcf767e6441f3d491` 已把 `auto/legal_watch.json` 與 `cdn/auto/legal_watch.json` 對齊，內容含：`民法`、`changed=true`、`2021-01-20 → 2026-08-17`。
   - 該 snapshot commit 沒有再觸發 Public Monitoring Feed，證明無 self-loop；Cloudflare Workers build 亦 success。

6. **Runtime Owner gate 前移到 PR**
   - #57 暴露治理缺口：Runtime Owner QA 原本只有 `push`，第 39 part / extra owner 要到 merge main 後才第一次被抓到。
   - #61 只修改 `.github/workflows/runtime-owner-qa.yml`，加入與 push 相同 paths 的 `pull_request` trigger。
   - #61 exact PR HEAD 已實際觸發並通過：maintainability structure、runtime owner chain、late owner chains、essay metadata enhancer。
   - #61 merge 後 main `push` Runtime Owner QA 也再次完整 PASS。
   - 往後凡修改 `monthly_patch_parts/**`、structure config 或 owner smoke，應在 **PR 合併前** 就被 Runtime Owner QA 阻擋結構回歸。

### 目前營運判斷

- 2026-09-06 本輪收尾時：**沒有 open PR、沒有 open issue、沒有 queued / in-progress main workflow**。
- main 最近真正紅燈皆是已被後續修復 supersede 的歷史 run；不要因 Actions history 還留著 failure 記錄就重開已結案問題。
- Monitoring V2 已經歷一次真實法規變更事件，從 MOJ detection → internal report → public snapshot → Cloudflare build 的鏈路已閉環。
- Runtime layering 維持 38 parts，且現在 PR / main 都有 Runtime Owner gate。
- 不要再做沒有明確收益的 owner-count cleanup、cosmetic refactor 或「為了變綠而放寬 guardrail」。

### 真正的下一步

1. **先讀遠端真實狀態**：`main` HEAD、最新 Actions、open PR/issues、最新 Monitoring snapshots。
2. 若沒有新紅燈／使用者回報，**不要憑空製造 cleanup 任務**；等待真實 feedback、監測異常、官方資料更新或明確產品需求。
3. 若有學生端 bug：先重現 → 找 canonical owner → 加 regression → exact-head PR gates → merge → main post-merge → production/public artifact 驗證。
4. 若有官方題庫／法規更新：保持 official source-of-truth 與 fail-closed；不要用 AI 猜答案或把 presentation workaround 寫回官方資料。
5. Netlify production 仍需使用者明確授權才改；目前 Cloudflare 路徑的 production-facing evidence 已驗證。

---

