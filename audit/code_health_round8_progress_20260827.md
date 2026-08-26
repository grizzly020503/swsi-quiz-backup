# SWSI Code Health — Round 8 Progress (2026-08-27)

狀態：`fix/code-health-p0-20260826 / continuation checkpoint`

本檔只記錄第八輪新增／收斂內容。架構與長期背景仍以 `PROJECT_HANDOFF.md`、`KNOWN_ISSUES.md`、`audit/full_code_health_audit_20260826.md` 為準。

## 本輪已完成

### 1. MOEX importer existing-ID collision fail closed

Production `import-moex-social-worker` 已從 v4 升到 **v5 / ACTIVE**。

新流程在任何 upsert 前先一次讀取全部 incoming IDs：
- 200 選擇題驗 `source_exam_code / year / round / subject / qno`
- 10 申論題驗 `source_exam_code / year / round / subject`
- 任一既有 ID identity 不一致 → 整包拒絕，第一筆 write 前停止

Source：
- `supabase/functions/import-moex-social-worker/index.ts`
- `scripts/moex_importer_integrity_smoke.js`
- `.github/workflows/moex-importer-integrity-qa.yml`

Production deploy 後 read-only health：
- questions = 4,800
- standard = 4,784
- all_credit = 12
- any_answer = 4
- exam identity mismatch = 0

### 2. Supabase recovery SQL drift

新增：
- `supabase/migrations/20260827031000_align_recovery_reset_with_grading_mode.sql`

GitHub recovery source 現在與 production 的 official-change reset contract 對齊：
- function body 比較 `grading_mode`
- trigger columns 包含 `grading_mode`

Production 已是正確狀態，本輪沒有為了 source sync 重複套 migration；只做 read-only contract verification。

### 3. localStorage/history durability

新增：
- `monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_storage_durability.part`
- `scripts/storage_durability_smoke.js`
- `.github/workflows/storage-durability-qa.yml`

目前 contract：
- history 保留最近 8,000 筆
- history / review quota write failure 顯示 visible warning
- history failure 後 review success 不得把 warning 誤清除
- 完整 `record()` 鏈有 browser smoke

已知 Storage Durability QA success run：`33004012894`。

### 4. Service Worker mutable asset upgrade

`sw.js` 已是 v6：
- mutable assets no-store network-first
- 舊 cache activate 時刪除

本輪新增：
- `scripts/service_worker_upgrade_smoke.js`

並接入：
- `.github/workflows/monthly-frontend-qa.yml`
- `scripts/p0_frontend_preflight.js` source contract

Smoke 真實模擬：
1. v5 cache-first 先快取舊版
2. 同 origin 更新到 repo 真實 v6 worker
3. 驗 v5 cache 刪除、v6 cache 建立
4. activation 後重新計數 network request
5. `monthly_patch.js / essay_guides.js / manifest.json` 三個 runtime fetch 都必須真正 hit network 並取得新內容

特別避免一個假陽性：v6 install 本身會 pre-cache mutable assets，所以 request counter 必須在 activation 後才 snapshot。

### 5. Full question-bank invariant

新增：
- `monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_question_bank_invariant.part`

不再只用 `loadedFiles.size` 宣告完整題庫。全庫完成前必須同時成立：
- manifest `total_questions` 合法
- shard `question_count` 總和等於 manifest total
- manifest file 無重複且全部實際 loaded
- `ALL.length == manifest.total_questions`
- 全庫 ID 唯一
- 每一 manifest year/round session 的實際題數等於 metadata
- `ALL` 不得含 manifest 未列出的 session

失敗時：
- `QB.allComplete=false`
- `QB.error` 保留錯誤
- full-bank caller reject，不把 silent partial bank 當完整

`scripts/grading_contract_smoke.js` 已新增 synthetic：
- valid full bank → pass
- 缺一題 / collision-equivalent partial → fail
- manifest total mismatch → fail

`p0_frontend_preflight.js` 也鎖定 full-bank marker，避免 release package 漏掉 guard。

## 本輪仍未完全結案

### A. Legacy IndexedDB shard verified marker

目前 byte-level WebCrypto SHA 驗證已存在，且線上取得新 manifest 後會清掉舊 shard cache再重建。

但 `monthly_patch_parts/00.part` 的歷史 cache schema 仍只有：
- `payload`
- `sha256`

舊版本曾直接把 manifest 的「預期 hash」寫入 cache，因此：

> `rec.sha256 === meta.sha256` 本身不能證明這份舊 cache 的 bytes 曾經被實際驗證。

理想最終 schema：
- 網路 shard 實際 WebCrypto SHA 成功後才寫 `verified_sha256: true`
- offline read 只接受 `verified_sha256 === true && rec.sha256 === meta.sha256`
- 舊 cache 無 marker → 不直接 trusted

這條尚未在 `00.part` source 內完成，因此 P1-2 不得誤標完全結案。

### B. 最新 branch push Actions 結論

GitHub connector 對 private branch push workflow run 的列舉目前不穩定；commit status API 也不會可靠列出這類 Actions。

因此：
- 已知 Storage Durability QA 有 success run，可明確記錄。
- importer integrity / 最新 Monthly Frontend QA（含新 SW upgrade + full-bank invariant）的最新 run 結論目前不要猜。
- 若 connector 恢復列舉能力，下一步先讀最新 run；紅燈就讀 job logs 修到綠。

## 不要重做

除非出現 regression，不要重新查：
- production 4,800 題與 grading-mode 分布
- production official-change trigger 是否含 grading_mode
- importer 是否仍是 v4（已升 v5）
- history 是否仍無上限（branch 已 cap 8,000）
- SW 是否仍是 v5（branch 已 v6）
- shard 是否完全沒有 WebCrypto SHA（已經有；剩 legacy cache provenance marker）

## 下一個真正優先順序

1. 取得最新 Monthly Frontend QA / importer integrity QA 結論；失敗就讀 logs 修復。
2. 收尾 legacy IndexedDB `verified_sha256` provenance marker。
3. 再驗 AI 429 最終 browser UX / Worker temperature production parity。
4. 之後才考慮 patch-ordering 模組化，不要在 P0/P1 gate 未完全穩定前大重構。

## Deployment boundary

本輪沒有部署 Netlify production。

Production backend 唯一主動部署：
- Supabase `import-moex-social-worker` v5

不要把 branch student-facing files 的存在誤寫成 Netlify 已上線。
