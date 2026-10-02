# SWSI 學生首頁 IA 盤點 — 2026-10-03

對應 Issue #307。

## 結論

目前首頁已不是功能牆，`monthly_patch_parts/20.product-philosophy.part` 已經採用「一個主要學習動作 + 少量次要入口」：

1. 主要：`20 題智慧練習`
2. 次要：`自己選範圍`
3. 次要：`錯題複習`
4. 次要：`計時模擬考`
5. 低干擾資源：`理論、法規與時事`

因此 #307 不應再做一次大型首頁重構。下一步應以減法、學生語言與任務情境為主。

## 第一屏現況

- Hero 已明確寫「今天先做一件事」。
- 主 CTA 會直接走既有 `startFocusedQuiz()`；不另建刷題邏輯。
- 年度、考次、科目、題數等進階設定預設收合。
- 錯題複習與模擬考維持兩個快速入口。
- 理論／法規／時事被降成單一低干擾資源入口，而非首頁多卡片並列。

## 「繼續上次」調查

目前 repo 可確認的學生端持久資料主要是：

- `swsi_v2_history`：作答歷史
- `swsi_review_v2`：複習／錯題排程
- IndexedDB：題庫 manifest / shard 離線快取

未找到一套可重建「尚未完成題組」的 durable session contract，例如：

- 當前題組 question IDs
- 當前題號
- 已選但尚未結束的答案狀態
- 題組來源／範圍設定
- 版本／題庫 fingerprint
- 過期或題庫版本變更時的 fail-closed 規則

因此目前**不得只加一個「繼續上次」按鈕**。若產品真的需要此功能，應先建立單一、可驗證、可失效的 quiz-session persistence contract；不能把作答歷史誤當成未完成 session。

## #307 下一步建議順序

### P1-A — 快速練習語言收斂

候選方向：將主 CTA 從「20 題智慧練習」收斂成更具任務感的短練習，例如「10 題快速練習」。

但修改 `monthly_patch_parts` 時必須同步：

- browser / launch smoke 中的按鈕 selector
- `cdn/monthly_patch.js` canonical concat artifact
- Cloudflare `cdn/index.html` 的 monthly patch digest
- preview / release artifact（若該 release owner 要求）

不可只改 source part，否則 `cloudflare_release_artifact_smoke.py` 會正確 fail closed。

### P1-B — 不增加首頁按鈕

在未刪除既有入口前，不新增新的 top-level CTA。

任何新情境，例如：

- 我只有 10 分鐘
- 我想練弱點
- 我要考一回完整模考

應優先映射到既有 `startFocusedQuiz()` / review / `MK.open()`，而不是建立平行功能。

### P1-C — 學生語言

優先把工程或系統語言換成學生能直接理解的任務語言；內部 contract 名稱不需要跟著改。

例如 `smart` 可以繼續做內部 scope key，但 UI 可用「系統推薦」或「快速練習」。

## 驗收原則

首頁簡化 patch 至少要同時證明：

- 不改 Official Core / grading contract。
- 不改題庫 loader ownership。
- 不增加 top-level 功能數。
- 320–430px 手機首屏仍有明確主 CTA。
- Chromium / WebKit launch smoke 維持綠燈。
- slow-network / offline / PWA 不因文案與入口調整退步。
- canonical `monthly_patch_parts` 與 tracked Cloudflare artifact 不漂移。

## 這輪沒有做的事

- 沒有新增「繼續上次」。
- 沒有建立第二套 session storage。
- 沒有直接改 production / Cloudflare / Netlify。
- 沒有因競品比較而照抄對方品牌、圖示、版面或文案。

這份盤點的目的，是把 #307 從「再做一版首頁」收斂成可驗證的學生任務簡化工作。
