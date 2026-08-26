# SWSI Release Guide

本檔定義「什麼時候可以 merge main / deploy production」。開發、測試、preview 與正式發布必須分離。

## 1. Branch policy

- `main`：production source of truth。
- 修復／功能工作：使用獨立 branch。
- 目前 P0/P1 修復：`fix/code-health-p0-20260826`。

Agent 可以在修復 branch 自行修改、測試、commit；沒有使用者明確授權，不得自動 merge `main`。

## 2. Release gates

正式 merge 前必須全部滿足：

### Code
- 所有 P0 已修完或不存在未解 blocker。
- P1 若未完成，必須確認不會造成資料錯誤、安全風險或正式站不可用。
- changed files 已人工／AI reviewer 檢視。
- 無 secrets / token / service-role key。

### Tests
- syntax checks 全綠。
- P0 frontend preflight 全綠。
- grading regression 全綠。
- 模擬考 smoke 全綠。
- shard SHA integrity smoke 全綠。
- Service Worker/cache smoke 全綠。
- essay duplicate-key / builder smoke 全綠。
- Unified Question QA 全綠。
- MOEX parser/health tests 全綠。
- Cloudflare Worker syntax / contract 全綠。
- production-shaped static smoke 全綠。
- Chromium/browser smoke 全綠。

### Data
- latest exam Official Core health 正常。
- Supabase production schema 與 repo migrations/recovery SQL 無未解 P0 drift。
- 歷史題／法規版本沒有因新改動被 current-state 倒灌。

### PWA
- Service Worker version / cache invalidation 符合本次 mutable asset 變更。
- 舊裝置能拿到新 runtime。

## 3. Preview

正式部署前優先使用 Cloudflare / Netlify deploy preview 驗收：
- 首頁
- 刷題
- 多答案／特殊給分
- 模擬考
- 錯題／複習
- 申論
- AI 回饋錯誤訊息
- iPhone / 小螢幕
- PWA update

Preview failure 不得用「正式站應該沒問題」略過。

## 4. Merge review

Merge 前至少產生一份摘要：

- base：`main`
- head：修復 branch
- commits
- changed files
- P0/P1 completed
- remaining risks
- CI / smoke results
- 是否建議 merge

Reviewer 應看「行為與 contract」，不只看 CI 綠燈。

## 5. Production deploy

只有使用者明確說「可以上架／部署正式站」後才執行。

部署時：
1. 確認 main HEAD 是剛驗收版本。
2. 確認 deploy workflow / Netlify trigger 指向正確 commit。
3. 部署後做 production smoke。
4. 檢查舊 Service Worker / cache update。
5. 若 production smoke 失敗，優先 rollback，不要直接在線上長時間 debug。

## 6. Rollback

發布前必須知道：
- 上一個 stable main commit。
- 如何回退前端資產。
- Supabase migration 是否可逆／如何 forward-fix。
- Cloudflare Worker 上一版本來源。

不可逆資料庫操作沒有 rollback / forward-fix 計畫時不得直接執行。

## 7. Agent 權限界線

AI/Agent 可自行：
- 開修復 branch
- 寫 code
- commit
- 跑 CI
- preview
- 讀 logs
- 修 regression

需本人明確批准：
- merge main
- production Netlify deploy
- production secrets 修改
- 破壞性 DB migration
- 付費／帳務操作
- 不可逆 production 操作

## 8. 發布後 handoff

成功發布後更新：
- `PROJECT_HANDOFF.md`
- `KNOWN_ISSUES.md`
- 必要時 `DECISIONS.md`

記錄：production HEAD、發布日期、smoke 結果、下一批工作。