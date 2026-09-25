# SWSI Known Issues

本檔只列「目前仍需要處理或持續防回歸」的問題。已確認修好的舊問題不要長期留在 Active 區，避免下一個 AI 重做。

## 2026-09-25 現行狀態（優先於下方歷史紀錄）

- **時事命題訊號發布缺口已完成修復並正式上線。** #77 已合併，兩份 signal snapshot 會進 repo/CDN；production sentinel 已驗 `signals-6/4800`。
- **學生端時事命題 UI 已正式發布到 Cloudflare primary。** #78 已合併，正式 `cdn/index.html` 為新版，`cdn/sw.js` 為 v7。
- **Cloudflare preview 舊 v6 assertion 已修正。** #77 後 preview 與 source bytes 對齊；不再把歷史 v6 檢查當 active bug。
- **公開監測盲點已補。** #79 讓 Public Uptime Sentinel 驗 SW v7、6 筆時事來源、6 筆命題訊號／4,800 題、52/52 法規與其他主要 public contracts；main run `36141787784` PASS。
- Cloudflare 本輪 release blocker = **0**；本次收尾時 open PR = 0、open issue = 0。
- **Netlify fallback 仍已知為 SW v2。** 這是非阻塞 release/維運事項，不是 Cloudflare primary bug；沒有明確授權與額度確認不要自行部署。
- scanner 仍只有衛福部＋中央社共 6 feeds；Reuters/AP/BBC/CNN/UN/WHO 等是產品擴充方向，不列為 active defect。
- 下方 v6、24 多答案、8 月 branch/release 敘述均為歷史證據；若衝突，以 `PROJECT_HANDOFF.md` 最上方最新節與遠端真實狀態為準。

## P0（已完成，持續防回歸）

### P0-1 Grading contract 必須持續統一
狀態：`完成；Monthly Frontend QA #91（33030671962）static / Chromium interaction 全綠`

目前 branch 已有共同 grading contract，並由 `scripts/grading_contract_smoke.js` 覆蓋：
- standard 單答案
- standard 多答案 `accepted_answers`
- `all_credit` 未作答也得分
- `any_answer` 未作答不得分、A-D 任一作答得分
- 特殊給分缺 metadata → `invalid / fail closed`
- 普通 legacy 題缺 mode → 安全 default `standard`

計時模擬考已改走同一 contract，不再直接猜 `q.answer`。

### P0-2 特殊給分不得 legacy inference
狀態：`完成；preflight + grading browser smoke 持續防回歸`

最終 runtime guard 會覆蓋早期 compatibility inference；特殊給分題若缺 `grading_mode`，不得從 ID／「一律給分」「送分」等文字猜模式，直接暫停判分。

### P0-3 Essay duplicate key / deploy artifact
狀態：`完成；source 與 deploy artifact 都禁止 duplicate key`

`essay_guides.js` 已無 107-1 duplicate；`scripts/build_essay_guides_runtime.js` 與 synthetic preflight 會拒絕任何 duplicate key。verified 107-1 三理論修正版由 builder 固定套用，所有 release path 都必須經 builder。

### P0-4 Release gate 必須真正攔 P0
狀態：`完成；Monthly Frontend QA #91、Essay Audit #7 與 production-shaped static/browser gate 全綠`

目前：
- Monthly Frontend QA 先跑 `p0_frontend_preflight.js` 再建 production-shaped site。
- Netlify release package workflow 先跑 P0 preflight，再產正式 ZIP。
- `essay_guides.js` / grading / SW / browser interaction 都已納入 relevant QA path。
- 最新新增 Service Worker v5→v6 真實升級 smoke 也已接進 Monthly Frontend QA。

## P1（完成項目與剩餘技術債）

### P1-1 Service Worker / mutable asset cache
狀態：`完成；Monthly Frontend QA #91 的真實 Chromium v5→v6 upgrade smoke 全綠`

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
狀態：`完成；legacy payload-only cache 已 fail closed`

已完成：
- CDN response 原始 bytes 以 WebCrypto 實算 SHA-256，通過後才 decode / 使用 / 寫入 IndexedDB。
- cache 保存原始 bytes、實算 hash 與 `2026-08-26.sha256.v2` provenance；每次離線讀取都重新雜湊。
- 舊 payload-only／自稱 `verified_sha256` 但沒有 v2 source bytes 的 row 一律拒絕。
- `2026-08-27.full-bank.v1` 驗 manifest 題數總和、loaded files、每考次題數、全庫 unique IDs 與 `ALL.length`。
- Monthly Frontend QA #91：24 shards artifact SHA、tampered-byte browser case、legacy offline cache rejection 與 full-bank smoke 全綠。

### P1-3 AI 429 分類
狀態：`完成；Worker/source smoke 與 Chromium grading/AI contract 綠燈`

前端需區分：
- 每分鐘太快
- 個人每日額度用完
- 全站每日額度用完

目前最後 runtime layer 會優先讀 Worker 實際 error message / code，避免每日額度用完仍顯示「稍後再試」。

### P1-4 Cloudflare Worker temperature zero
狀態：`完成；explicit 0、null fallback 與 Worker contract smoke 綠燈`

`temperature: 0` 不得因 `Number(x) || 0.4` 變成 0.4。

### P1-5 Supabase recovery SQL drift
狀態：`source 已修；production 契約已只讀驗證一致`

Production trigger 已包含 `grading_mode`。GitHub 新增 `20260827031000_align_recovery_reset_with_grading_mode.sql`，將 recovery/source-of-truth 的 `reset_ai_analysis_on_official_change()` 與 trigger columns 對齊 production，避免災難復原時 grading-mode change 不清舊解析。

2026-08-27 production read-only check 已確認：
- function body 有 `new.grading_mode is distinct from old.grading_mode`
- trigger columns 有 `grading_mode`

### P1-6 localStorage/history 長期容量與可見錯誤
狀態：`完成；Storage Durability QA #7（33030671919）Chromium 綠燈`

目前 branch：
- history 保留最近 8,000 筆；history / review-state 讀寫前都做 schema 驗證。
- 損壞 payload 先保留 `*_corrupt_backup_*` 再建立乾淨狀態；若備份失敗，後續 write fail closed，禁止覆寫原始資料。
- history / review 寫入失敗有可見警告，且 review 成功不會蓋掉先前 history 失敗警告。
- `scripts/storage_durability_smoke.js` 覆蓋 cap、invalid-write preservation、quarantine、backup failure、QuotaExceededError 與完整 `record()` 鏈。
- `.github/workflows/storage-durability-qa.yml` 最新成功 run：`33030671919`。

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

MOEX Importer Integrity QA #1（33003892890）已成功；Monthly Frontend QA #91 亦再次執行 importer source contract、Deno check 與 recovery drift smoke。


## 尚未執行的 release operation

- Netlify production deploy 與 `Verify Netlify Production Release` 未執行：本輪沒有部署授權；這是 merge 後的人工 release 步驟，不是未修程式 bug。
- `main` 比 branch 多一筆只修改 `cdn/preview/monthly_patch.js` 的 preview artifact commit；合併必須走一般 PR/merge 並保留該 commit，不可 force 覆蓋。

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

