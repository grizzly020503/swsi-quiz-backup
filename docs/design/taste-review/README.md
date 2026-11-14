# SWSI UI/UX review candidate — not approved for release

This branch is a design review only. No merge or deployment is authorized.

## Design diagnosis and direction

Observed on the hosted homepage and quiz on 2026-11-14: several similar card boundaries compete for attention; serif question text and sans navigation are inconsistent; small labels are difficult to scan; desktop navigation floats separately to the right; legacy V2, V3 and component styles overlap. The student route is accessible without signing in; administrator authentication is a separate boundary and has not been tested with credentials.

Open `directions.html` for **three static homepage + quiz concepts**. These are visual concepts, not functional alternatives, and use an explicitly labelled invented demonstration question.

| Direction | Design | Assessment |
|---|---|---|
| A — 暖白閱讀室 | Warm neutral canvas, deep green actions, unboxed welcome, clear reading rows | Selected for implementation: retains the green identity, reduces surfaces, supports prolonged reading |
| B — 冷灰學習工作台 | Blue-grey canvas, compact panel hierarchy, square controls | Useful for dense work, but feels more administrative |
| C — 深綠書院 | Dark green welcome, serif editorial headings, warm paper | Strong identity, but the heavy welcome and mixed typography compete with study text |

## Shared system

- Canvas `#F7F6F2`; surface white; ink `#25332F`; secondary `#58645F`; action `#214D43`.
- Success/error retain distinct colours and existing answer markers; official answers remain untouched.
- System Traditional Chinese sans font: no external font request required. Reading text 16px default; question text 18.67px; labels 13px. Existing A/A/A controls retained.
- Spacing 8/12/16/24/32/40px; control radius 10px, surface 12px; 48px action targets and 44px font controls.
- 800px reading shell; existing bottom navigation on smaller displays; coherent left-side navigation from 1100px. Quiz retains distraction-free navigation behavior.
- Visible keyboard focus, skip-to-content link, reduced motion, existing form labels and modal focus guards.

## Implementation ownership

The shared stylesheet replaces the former V2 + V3 visual layers, retaining the V2 identifier as a compatibility anchor. No new late `zz` patch or stylesheet is added. Homepage styling stays in `20.product-philosophy.part`; shell geometry in `15.layout-foundation.part`; question rows in `30.focused-quiz-style.part`; font scaling in existing typography owners. The compiled CDN patch is rebuilt byte-for-byte from parts. Live-parity tests are updated to enforce the consolidated system instead of requiring two historical layers.

Changes also remove the homepage's misleading claim of handwriting upload while its OCR candidate remains an unmerged PR. No OCR functionality is removed or introduced.

## 驗收與前後對照

已完成的完整測試批次：[9f8de4d / Actions](https://github.com/grizzly020503/swsi-quiz-backup/actions/runs/43649084067)；20 個 PR 工作流程全數成功。其後僅補正長選項測試資料的 DOM 容器，未變更產品程式。

本候選版僅供 Owner 審查，尚未核准合併或發布。選定 **A｜暖白閱讀室**；三方向皆保留相同首頁與刷題流程，避免以新增功能製造設計差異。

### 問題與實際改善

| 原有問題 | 改善 |
|---|---|
| V2、V3 與後置樣式重複競爭 | 合併共用設計層；在原有元件擁有者修改，不新增臨時覆寫檔 |
| 首頁卡片邊框、色塊與圖示分散注意力 | 單一主要操作、兩個學習入口、三個輕量工具；同套線條 SVG |
| 題幹、導航與說明字體不一致，部分標籤過小 | 共用系統字體與字級變數；保留三段字級控制 |
| 桌面導航游離，閱讀寬度不穩定 | 800px 閱讀容器；1100px 以上左側導航；手機保留底部導航 |
| 法規／時事等入口採多種飽和底色 | 在原始標記移除色塊，統一為中性閱讀列表 |
| 作答狀態需要更容易辨認 | 清楚的選項界線、文字標示、正誤狀態；修復本次測試發現的停用按鈕背景覆蓋 |
| 首次引導仍使用舊導航名稱 | 對齊「刷題」「申論」「我的」實際名稱 |

### 檢查範圍

四個視窗均為真實 Chromium 瀏覽器截圖：**390、768、1024、1440px**，高度 900px。每個尺寸涵蓋首頁、刷題、答案解析、錯題本、學習中心、申論題庫、資源入口、法規、時事與模擬考設定。前後使用相同 PR base、固定亂數與隔離本機資料；外部寫入和 AI 呼叫被阻擋。長題幹與長選項僅修改測試頁面的 DOM，不改官方題庫。

`evidence/` 保留首頁及刷題前後對照；完整原始 PNG 與 JSON 位於 PR 的 **Taste UI Design Review (NO DEPLOY)** Actions artifact（保存 14 天）。全頁截圖中的固定底部導航位於原始視窗底部，不能用縮小長圖的位置推論實際遮擋。

| 驗收項目 | 證據／界限 |
|---|---|
| 四尺寸版面 | 各尺寸無瀏覽器 pageerror；刷題與長題幹無橫向溢出；已目視首頁與刷題 |
| 題目切換、作答、解析、判分 | 既有 browser interaction、grading contract、完整題庫與漸進解析 QA |
| 模擬考與申論流程 | launch readiness、dead-end、error-state 測試；AI 成功／失敗採測試回應，不宣稱真實模型品質已驗收 |
| 觸控、鍵盤、無障礙 | touch smoke、axe gate；axe 在首頁／公開資訊／回報／考試日期視窗為 0 violations，仍有人工判斷 incomplete 項目 |
| WebKit | 既有 WebKit smoke 與 interaction 測試；不能替代真機 iPhone Safari |
| 資料保存與離線 | storage degradation、Storage Durability、PWA resilience、SW 更新、離線 shard integrity、慢網路測試 |
| 產物與功能保護 | CDN/root 樣式一致、patch 重建一致、240 份申論指引、官方題庫保護、runtime owner、完整題庫 QA |

本機 Chromium 因環境限制無法啟動，瀏覽器證據來自隔離的 GitHub Actions 容器；沒有宣稱本機或正式站已套用此設計。正式站／備援站的唯讀比對以 PR base 為基準，避免把尚未發布的候選版誤當成正式版本要求部署。

### 尚未驗收／發布前風險

- 真機 iPhone／Android、作業系統字型差異及輔助科技人工測試尚未完成。
- 未使用學生或管理員憑證進行真實登入；沒有修改登入或安全設定。
- 未呼叫正式 AI 或寫入正式 Supabase；真實 AI 品質與跨裝置同步不屬於本次隔離測試證明。
- 保留既有核心與部分功能樣式，並非宣稱全部 legacy CSS 債務已清除。
- 未改 SW 快取版本；隔離離線測試通過仍不能取代未來獲准發布後的真實升級驗收。
- 未增加知識卡，也未移除既有核心小辭典。未修改官方題庫、判分規則、正式資料或站台設定。

## Taste Skill provenance and limits

Official source: https://github.com/Leonxlnx/taste-skill at `f6b76575f949707b4e3c37cd86cb44b0b98643e8`, version 2.5.1, MIT. Read README, SKILL.md, plugin manifest and installer behavior. CLI supports plugins, but the actual marketplace install failed because its installation directory is read-only. **Not installed; no new-session automatic loading claimed.** Used the retrieved instructions as design guidance, specifically one system, readable hierarchy, real-browser checks and restrained interaction. Did not copy or run third-party executable scripts or enable hooks. The reviewed plugin manifest declares a skills directory, not a remote MCP service.

Per Owner brief, marketing-only prescriptions (full-screen sections, mandatory moments, WebGL, photograph quotas and randomized palettes) do not apply to this education product. The official marketing-page finish gate was not run; no Taste `GATE: PASS` is claimed.

## 截圖索引

每張左側為改版前，右側為候選版。原始視窗寬度保留；WebP 僅為審查檔案壓縮。

| 尺寸 | 首頁 | 刷題 |
|---|---|---|
| 390px | [前後對照](evidence/home-390.webp) | [前後對照](evidence/quiz-390.webp) |
| 768px | [前後對照](evidence/home-768.webp) | [前後對照](evidence/quiz-768.webp) |
| 1024px | [前後對照](evidence/home-1024.webp) | [前後對照](evidence/quiz-1024.webp) |
| 1440px | [前後對照](evidence/home-1440.webp) | [前後對照](evidence/quiz-1440.webp) |

[三方向首頁與刷題設計比較](evidence/three-directions.webp) · [可開啟的靜態設計稿](directions.html)
