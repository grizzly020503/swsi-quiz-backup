# SWSI UI 改版候選（2026-11-22）— 未核准、不得合併或部署

這次直接改在**真網站**上，題目也是正式題庫的真題，不是示意稿。Owner 之前否決過幾輪，主要原因有四個：顏色、看起來像模板、只是示意稿、不夠好用。這一輪就是針對這四點重做。

## 這個分支實際改了什麼（目前程式＝風格 3「活力學習」）

| 問題 | 修正 | 負責的檔案 |
|---|---|---|
| 圖示有三套：文字符號、表情符號、SVG | 全站只用一套 SVG 圖示 `swsiIcon()`；三個導覽 owner 輸出相同 markup，不再互相覆寫 | `15.layout-foundation`、`71`、`zzzz_product_v1_lock` |
| 字體混用：題目是襯線粗體 | 改用系統無襯線字（PingFang／Noto Sans／微軟正黑），不需下載字型 | `swsi-calm-learning-ui-v3` |
| 答題沒有回饋感 | 結果列固定在畫面底部（答對／答錯＋唯一的「下一題」）；進度條在作答後前進 | `00.part`、`30.focused-quiz-style` |
| 解析有 6 種區塊樣式 | 統一成一種卡片和一種展開樣式；保留既有 DOM 結構與測試 hook | `30.focused-quiz-style` |
| 答題時頂部太雜 | 精簡答題列：關閉、進度、題號 | `00.part` |
| 標籤字只有約 10px | 字級縮放 owner 改成最小 13px；正文 16px | `75.learning-font-scale` |
| 學生看到工程用語 | 模擬考說明改成「都依考選部公布的答案計分」；移除表情符號標籤 | `mk_grading_contract` |
| 新手提示名稱與分頁不一致 | 改成「刷題」「申論」「我的」 | `73` |
| 首頁 | 品牌主卡、今天已練題數（讀取既有紀錄，未新增儲存）、統一的入口卡片 | `20.product-philosophy` |

沒有新增後置覆寫層。全部改在原本負責的 owner 檔案裡（maintainability smoke 通過）。`swsi-calm-learning-ui-v3` 的 id 保留，讓既有的 release／live parity 檢查繼續有效，內容則改寫為唯一的設計 token 來源。

## 風格比較（等 Owner 選擇）

`images/four-styles.webp`：四種風格都套在同一個真網站上，由上到下為首頁、選好答案、答錯後。

| 風格 | 檔案 | 說明 |
|---|---|---|
| 1 溫暖陪伴 | `styles/1-warm.css` | 米白紙感、深藍字、芥末黃按鈕、柔和陰影 |
| 2 清爽專業 | `styles/2-clean.css` | 白底細線、黑色主按鈕、沒有立體效果 |
| 3 活力學習 | 已實作在程式中 | 藍色主卡、立體按鈕 |
| 4 簡單大字 | `styles/4-simple-large.css` | 題目 21px、選項 18px、首頁改成單欄清單、無裝飾；依 Owner 回饋「字大、簡單」製作 |

`styles/*.css` 只是預覽用的覆寫，不會被網站載入。Owner 選定後，會把選定的風格正式寫進上表的 owner 檔案，再擴充到其他頁面。

## Taste Skill

人工參照官方 repo（Leonxlnx/taste-skill v2.5.1）的 `references/system.md`、`motion.md`、`copy-tells.md`，採用其中的單一系統、可讀字級與對比、單一強調色、按壓與 reduced-motion 準則。它的形象網站規則（一屏一區、大量照片、hero 進場特效、WebGL）不適用於刷題產品，因此沒有採用。Plugin 未安裝，也不宣稱通過官方 gate。

## 驗證（本機）

- static：cloudflare_release_artifact、maintainability、p0 preflight、monthly_frontend、learning_flow、learning_loop 全部 OK。
- Playwright 預裝 Chromium：grading_contract、shard_integrity、browser_interaction、knowledge_path、theory_trust ×3、feedback、service_worker_upgrade 全部 OK。
- 截圖寬度 390 與 1440px。768／1024px、申論詳細頁、法規與時事頁尚待完成。

## 邊界

Draft，未合併、未部署。未修改正式站、Netlify、Supabase、官方題庫、判分規則或安全設定。
