# SWSI Known Issues

本檔只列「目前仍需要處理或持續防回歸」的問題。已確認修好的舊問題不要長期留在 Active 區，避免下一個 AI 重做。

## Active P0

### P0-1 Grading contract 必須持續統一
狀態：`in progress on fix/code-health-p0-20260826`

風險：一般刷題、模擬考、錯題／複習若使用不同判分邏輯，會在多答案、all_credit、any_answer、未作答時出現不一致。

完成條件：
- 共用 grading helper。
- 五種核心情境 browser smoke 全綠。
- 特殊給分缺 metadata fail closed。

### P0-2 特殊給分不得 legacy inference
狀態：`in progress`

禁止從 ID／「一律給分」「送分」等文字猜 `grading_mode`。

完成條件：P0 preflight + browser smoke + loader validation 全部依 metadata 判定。

### P0-3 Essay duplicate key / deploy artifact
狀態：`in progress`

已知歷史問題：`essay_guides.js` 曾有同題號重複定義並被 JavaScript 靜默覆蓋。

完成條件：
- source lint 能偵測 duplicate。
- deploy artifact 唯一 key。
- verified override 不被後續覆蓋。

### P0-4 Release gate 必須真正攔 P0
狀態：`in progress`

歷史上 P0 preflight、essay source、某些 mutable asset 沒有被所有 relevant workflow 觸發／執行。

完成條件：學生端／guide／grading 改動無法在 P0 gate 紅燈時進正式 release。

## Active P1

### P1-1 Service Worker / mutable asset cache
狀態：`v6 修復中`

目標：避免 GitHub 已更新，但舊學生裝置仍長期執行舊 `monthly_patch.js` / `essay_guides.js`。

### P1-2 CDN shard 真實 SHA-256 驗證
狀態：`修復中`

下載 bytes 要實算 SHA；不得只把 manifest hash 寫入 cache。

### P1-3 AI 429 分類
狀態：`修復中`

前端需區分：
- 每分鐘太快
- 個人每日額度用完
- 全站每日額度用完

優先顯示 Worker 實際 error message / code。

### P1-4 Cloudflare Worker temperature zero
狀態：`branch 已修，需持續 CI 驗證`

`temperature: 0` 不得因 `Number(x) || 0.4` 變成 0.4。

### P1-5 Supabase recovery SQL drift
狀態：`open`

Production trigger 已比 repo recovery SQL 新；目前正式 DB grading_mode 異動能清解析，但 recovery/source SQL 需同步，避免災難復原時 regression。

### P1-6 localStorage/history 長期容量與可見錯誤
狀態：`open`

歷史／複習資料持續增長，需：
- 明確容量／壓縮／上限策略。
- 寫入失敗對使用者可見。
- 不可默默停止記錄學習進度。

### P1-7 Patch 疊 patch 的載入順序風險
狀態：`architectural debt`

現在部分正確行為依賴最後載入 override。短期以 regression 保護，長期拆模組。

## P2 / 長期重構

- 將 `index.html + monthly_patch_parts` 逐步拆為 grading、loader、storage、simulation、essays、AI 等模組。
- 讓 QA dashboard 成為真正管理端資料接口。
- 將 legacy essay template source 遷移成唯一 registry。
- 建立跨 AI 任務分工／review 流程，避免多人同改高衝突檔。

## 已確認正常／不要重查

除非新 regression 出現，以下不列 Active Bug：
- Supabase 正式題庫 4,800 題年度／考次一致性。
- `accepted_answers` DB constraint。
- Production official-change trigger 已包含 `grading_mode`。
- AI request 已有穩定匿名 `X-SWSI-Client-ID`。
- 手寫照片前端限制已收斂到 1–3 張。
- 主要刷題輸出 escape / XSS 防護已大幅補強。
- 申論草稿 localStorage 失敗已有可見提示。
- 高權限 Supabase `SECURITY DEFINER` functions 未開給 anon/authenticated/PUBLIC。

## 維護方式

每次 P0/P1 修好：
1. 在本檔改狀態或移到「已確認正常」。
2. 更新 `PROJECT_HANDOFF.md`。
3. 附上 commit / test 結果。

不要讓本檔成為永遠不清理的歷史垃圾桶；歷史細節放 `audit/`。