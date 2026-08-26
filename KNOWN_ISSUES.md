# SWSI Known Issues

本檔只列「目前仍需要處理或持續防回歸」的問題。已確認修好的舊問題不要長期留在 Active 區，避免下一個 AI 重做。

## Active P0

### P0-1 Grading contract 必須持續統一
狀態：`branch 實作完成；release 前仍以最新 Monthly Frontend QA 綠燈為必要條件`

目前 branch 已有共同 grading contract，並由 `scripts/grading_contract_smoke.js` 覆蓋：
- standard 單答案
- standard 多答案 `accepted_answers`
- `all_credit` 未作答也得分
- `any_answer` 未作答不得分、A-D 任一作答得分
- 特殊給分缺 metadata → `invalid / fail closed`
- 普通 legacy 題缺 mode → 安全 default `standard`

計時模擬考已改走同一 contract，不再直接猜 `q.answer`。

### P0-2 特殊給分不得 legacy inference
狀態：`branch 實作完成；持續由 preflight + browser smoke 防回歸`

最終 runtime guard 會覆蓋早期 compatibility inference；特殊給分題若缺 `grading_mode`，不得從 ID／「一律給分」「送分」等文字猜模式，直接暫停判分。

### P0-3 Essay duplicate key / deploy artifact
狀態：`branch migration path 已封住；release artifact 必須經 builder`

已知歷史 source `essay_guides.js` 仍保留一個已知 107-1 duplicate 作為 migration source，但：
- `scripts/p0_frontend_preflight.js` 會拒絕任何額外 duplicate 或已知 duplicate shape 漂移。
- `scripts/build_essay_guides_runtime.js` 會輸出唯一 key 的 deploy artifact。
- verified 107-1 三理論修正版會在 build 時固定套用。

正式 release 不得直接 copy raw `essay_guides.js` 當 runtime artifact。

### P0-4 Release gate 必須真正攔 P0
狀態：`branch 已接線；等待最新整包 QA 驗收`

目前：
- Monthly Frontend QA 先跑 `p0_frontend_preflight.js` 再建 production-shaped site。
- Netlify release package workflow 先跑 P0 preflight，再產正式 ZIP。
- `essay_guides.js` / grading / SW / browser interaction 都已納入 relevant QA path。
- 最新新增 Service Worker v5→v6 真實升級 smoke 也已接進 Monthly Frontend QA。

## Active P1

### P1-1 Service Worker / mutable asset cache
狀態：`v6 source 已修；真實升級 smoke 已加入，待最新 Monthly Frontend QA 結論`

目前 `sw.js`：
- cache version = `v6`
- HTML / auto / `monthly_patch.js` / `essay_guides.js` / `manifest.json` 採 no-store network-first
- 舊 cache 在 activate 時清理

`scripts/service_worker_upgrade_smoke.js` 會模擬：
1. v5 cache-first 先黏住舊資產
2. 原 origin 升級成 repo 真實 v6 worker
3. 驗證 v5 cache 被刪除、v6 cache 建立
4. `monthly_patch.js` / `essay_guides.js` / `manifest.json` 三個 runtime fetch 都必須真正重新打網路並拿到新版本

測試特別把 request counter 放在 v6 activation 後，避免被 install pre-cache 造成假陽性。

### P1-2 CDN shard / 全題庫完整性
狀態：`主要 runtime guard 已完成；legacy IndexedDB verified-marker 邊界仍需收尾`

已完成：
- CDN shard response bytes 以 WebCrypto 實算 SHA-256，與 manifest 比對後才使用。
- manifest hash 格式異常直接 fail closed。
- 線上取得新 manifest 後會清除舊 shard cache，讓新 cache 經 verified fetch path 重建。
- 新增 `2026-08-27.full-bank.v1` 全庫 invariant：manifest 題數總和、loaded shard files、每考次題數、全庫 unique IDs、`ALL.length == manifest.total_questions` 必須全部一致。
- `scripts/grading_contract_smoke.js` 已加入 synthetic full-bank / collision / manifest-total regression 測試。

仍需收尾：舊 `00.part` IndexedDB row 只有 `sha256` 欄位，歷史版本曾把 manifest 預期 hash 直接寫入，尚未有獨立 `verified_sha256` marker。線上重建路徑已會清舊 cache，但純離線 legacy cache 的可信度仍低於新 verified path；不要把這條誤標成完全結案。

### P1-3 AI 429 分類
狀態：`branch 已修，需持續 browser/CI 驗證`

前端需區分：
- 每分鐘太快
- 個人每日額度用完
- 全站每日額度用完

目前最後 runtime layer 會優先讀 Worker 實際 error message / code，避免每日額度用完仍顯示「稍後再試」。

### P1-4 Cloudflare Worker temperature zero
狀態：`branch 已修，需持續 CI 驗證`

`temperature: 0` 不得因 `Number(x) || 0.4` 變成 0.4。

### P1-5 Supabase recovery SQL drift
狀態：`source 已修；production 契約已只讀驗證一致`

Production trigger 已包含 `grading_mode`。GitHub 新增 `20260827031000_align_recovery_reset_with_grading_mode.sql`，將 recovery/source-of-truth 的 `reset_ai_analysis_on_official_change()` 與 trigger columns 對齊 production，避免災難復原時 grading-mode change 不清舊解析。

2026-08-27 production read-only check 已確認：
- function body 有 `new.grading_mode is distinct from old.grading_mode`
- trigger columns 有 `grading_mode`

### P1-6 localStorage/history 長期容量與可見錯誤
狀態：`branch 已修；Storage Durability QA 已成功`

目前 branch：
- history 保留最近 8,000 筆，避免無上限成長。
- review state 本身以題目 ID 為 key，總量受題庫規模天然限制。
- history / review 寫入失敗會顯示可見警告，不再只留 console / hidden flag。
- 修正 history 寫入失敗後，後續 review 成功誤把警告清掉的鏈式問題。
- `scripts/storage_durability_smoke.js` 驗證 retention cap、QuotaExceededError visible warning 與完整 `record()` 鏈。
- `.github/workflows/storage-durability-qa.yml` 已有成功 run：`33004012894`。

### P1-7 Patch 疊 patch 的載入順序風險
狀態：`architectural debt`

現在部分正確行為依賴最後載入 override。短期以 regression 保護，長期拆模組。

## 已完成並需防回歸

### MOEX importer existing-ID identity guard
狀態：`production v5 / ACTIVE`

2026-08-27 已將 `import-moex-social-worker` 從 production v4 升級到 v5：
- 200 選擇題與 10 申論題先一次讀取所有既有 ID。
- 逐筆驗 `source_exam_code / year / round / subject`，選擇題另驗 `qno`。
- 任一 identity collision 會在第一筆 upsert 前整包 fail closed。
- source guard：`scripts/moex_importer_integrity_smoke.js`
- CI：`.github/workflows/moex-importer-integrity-qa.yml`

部署後 production read-only health：
- questions = 4,800
- standard = 4,784
- all_credit = 12
- any_answer = 4
- source_exam_code / year / round identity mismatch = 0

目前 connector 對 branch push Actions run 的列舉不穩定，因此 importer CI 未取得可重述的最新 run 結論；不要因 production v5 正常就虛構 CI 綠燈。

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
- MOEX importer production v5 已有 existing-ID identity preflight。
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
