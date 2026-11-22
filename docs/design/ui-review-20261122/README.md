# SWSI UI 改版候選（2026-11-22）— 未核准、不得合併或部署

這次直接改在**真網站**上，題目也是正式題庫的真題，不是示意稿。Owner 之前否決過幾輪，主要原因有四個：顏色、看起來像模板、只是示意稿、不夠好用。這一輪就是針對這四點重做。

## Owner 選定方向（2026-11-22）

風格 4「簡單大字」，加上 Apple 的簡潔高雅和社工的溫暖。已直接寫進程式本體，不是預覽：

| 要的感覺 | 做法 |
|---|---|
| 簡單大字 | 題目 21px、內文 18px、說明 15px；A／A／A 放大到 24／27px；首頁大標題 32px＋一顆按鈕 |
| Apple 的高雅 | 入口改成 iPhone「設定」式分組清單（白色圓角、細分隔線、右側小箭頭）；頁首、底部分頁、答題結果列用半透明毛玻璃；不用陰影、不用立體按鈕 |
| 社工的溫暖 | 米白底 `#F7F5F0`、偏暖的灰字、陶土主色 `#A9532B`（白字對比 5.3:1）；陪伴口吻文案 |

主色：Owner 選定 **暖陶**（比較圖 `images/accent-compare.webp`，B 沉穩藍 `#1F4FA3` 未採用）。

頁尾與「關於／資料來源／隱私／使用條款」視窗：文字與連結不變，只改成同一套字級與顏色（連結 15px、觸控 44px）。

## 這個分支實際改了什麼

| 範圍 | 修正 | 負責的檔案 |
|---|---|---|
| 設計 token | 單一來源：顏色、字型、圓角、半透明材質、停用狀態 | `swsi-calm-learning-ui-v3`（兩個 HTML） |
| 字級 | 閱讀字級與介面字級改成大字基準 | `40.mobile-reading-polish`、`10.font-size-control`、`75.learning-font-scale` |
| 圖示 | 全站一套 SVG `swsiIcon()`，移除文字符號與表情符號 | `15.layout-foundation`、`71`、`zzzz_product_v1_lock`、`00.part`（考點頁） |
| 首頁 | 大標題＋一顆按鈕＋兩組分組清單；今天已練題數（讀既有紀錄） | `20.product-philosophy` |
| 答題 | 白色選項列、選中填色字母、答對／答錯標示移到選項文字下方；結果列固定在底部並帶唯一的「下一題」 | `00.part`、`30.focused-quiz-style` |
| 我的 | 大標題、分組清單、統計列、考試倒數列 | `71`、`73`、`75` |
| 考點／法規／理論／搜尋 | 彩色大卡改成分組清單；小字（10–13px）提高到 14–18px；系統字 | `00.part`、`80.knowledge-path`、`88.theory-trust-ui`、`40` |
| 模擬考 | 舊綠色與襯線字改用 token | `mk_grading_contract` |
| 答題回饋（考生視角修正） | 選中改用深墨色，不再用主色；答錯紅改為玫瑰紅 `#C0283F`，和陶土色分開；答錯後自動捲動，讓官方答案露在結果列上方 | `swsi-calm-learning-ui-v3`、`30`、`00.part` |
| 解析區（Owner 手機實測回饋） | 手機上結果列縮成一行（約 77px，鼓勵文字只留給讀屏）；「題目來源與解析」改成標題＋一行小字，舊綠色標籤改用 token | `30`、`zzzz_product_v1_lock` |
| 上線前補看（申論／模擬考／錯題本） | 申論作答頁移除表情符號（AI 區塊的 🔒🤖📷 除外：`99z.essay-trust-layer` 受 AI 回饋合約保護，改動需重新擷取並人工評分模型輸出，本 PR 不動）、舊綠色與襯線字改 token；模擬考選中改深墨色（舊核心先建立 `#mk-style`，owner 另補 `#mk-style-system` 小區塊）；「今天到期」為 0 時不用紅色 | `40`、`00.part`、`99_p0`、`99z`、`80`、`mk_grading_contract`、`70.learning-loop` |
| A／A／A 字級（Owner 手機回報無效） | 首頁、考點清單、法規／理論頁改用 `--fs-*` 變數，三段字級都會跟著放大（首頁標題 32→35→38px） | `20`、`80`、`40`、`swsi-calm-learning-ui-v3` |
| 申論作答頁（Owner 回饋） | 拍照請 AI 看改為實心主按鈕、打字為次要淺色按鈕（只用 CSS，不動 AI 合約層）；「清空」移到儲存字數那一行，遠離層級按鈕（原本就會再次確認） | `40`、`99_p0` |
| 時事庫、讀書指南 | 移除標題與分頁表情符號；小字（約 11–13px）改用 `--fs-s`；分頁、按鈕、卡片改用 token。內容與文字不變（「目前 3 個國考重點」仍保留給上線檢查）；同步更新 `install_current_affairs_ui.py`，避免建置時被舊版蓋回 | 兩個 HTML、`scripts/install_current_affairs_ui.py` |
| 頁尾與資訊視窗 | 字級 14–16px、連結改主色、按鈕 44px | `89.public-branding-info`、`zzzz_product_v1_lock` |
| 測試 | `launch_readiness_smoke` 改讀 token：首頁主按鈕＝`--brand`、停用按鈕＝`--off-bg`／`--off-ink` | `scripts/launch_readiness_smoke.js` |

沒有新增後置覆寫層；都改在原本負責的 owner 裡。`swsi-calm-learning-ui-v3` 的 id 保留給 release／live parity 檢查。

## 歷史比較

`images/four-styles.webp`：先前讓 Owner 挑選的四種風格。`styles/*.css` 只是當時的預覽覆寫，不會被網站載入。

## Taste Skill

人工參照官方 repo（Leonxlnx/taste-skill v2.5.1）的 `references/system.md`、`motion.md`、`copy-tells.md`，採用其中的單一系統、可讀字級與對比、單一強調色、按壓與 reduced-motion 準則。它的形象網站規則（一屏一區、大量照片、hero 進場特效、WebGL）不適用於刷題產品，因此沒有採用。Plugin 未安裝，也不宣稱通過官方 gate。

## 驗證（本機）

- static：cloudflare_release_artifact、maintainability、monthly_frontend、student_home_ia、window_global_inventory、progressive_explanation、learning_loop_closed、p0 preflight、review_analysis_quarantine、runtime_owner、learning_flow、learning_loop_action 全部 OK。
- Playwright（預裝 Chromium）：launch_readiness、layout_foundation、prelaunch_deadend、browser_interaction、storage_degradation、slow_network、pwa_resilience 全部 OK。
- 本機無法跑：prelaunch_webkit（未安裝 WebKit）；error_states、accessibility_touch、axe 在未修改的 main 上本機也失敗（環境問題）。以上交給 CI。
- 截圖：390／768／1024／1440px（`images/four-widths.webp`），console 無錯誤。

## 邊界

Draft，未合併、未部署。未修改正式站、Netlify、Supabase、官方題庫、判分規則或安全設定。
