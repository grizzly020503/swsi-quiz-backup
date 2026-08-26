# SWSI 未完成工作證據核對 — Part 2

日期：2026-08-27

本附錄延續 `UNFINISHED_WORK_LEDGER.md` 與第一輪 reconciliation。只記錄本輪已找到的 repo / production evidence，不以 AI 口頭摘要作完成依據。

## 1. 指定歷屆 round canonical regression

狀態：`IMPLEMENTED / FINAL_SMOKE_PENDING`

`monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_final_runtime_contract.part` 已在最後生效層重包 `renderHome()`，把考次 selector 固定為：

- `all`
- `1`
- `2`

顯示文字才是「全部考次／第一次／第二次」。

因此早期 `第一次/第二次` 被當作內部 value 的 regression 已有 runtime 修正。仍需 browser smoke 驗證真 DOM 與指定歷屆抽題。

## 2. theory / law search deep-link

狀態：`IMPLEMENTED / FINAL_SMOKE_PENDING`

`monthly_patch_parts/00.part` 已改為 name -> index：

- `openTheory(name)` 使用 `THEORIES.findIndex(...)` 後寫入 `theoryOpen`
- `openLawCard(name)` 使用 `LAWS.findIndex(...)` 後寫入 `lawOpen`
- 搜尋結果透過 index wrapper (`swsiSearchOpenTheory` / `swsiSearchOpenLaw`) 開啟

這已修正舊版「state 放 name、render 卻拿 numeric index 比對」的問題。仍需真實搜尋點擊 smoke。

## 3. 照片 AI 1–3 張契約

狀態：`IMPLEMENTED / FINAL_SMOKE_PENDING`

`99_p0_mobile_ai_guardrails.part`：

- UI 明示一次選 1–3 張
- `files.length > 3` 直接拒絕並要求重新選擇
- 不再默默截掉第 4 張

Cloudflare Worker 也維持 `imageCount > 3 -> 400` 的後端第二層保護。

因此前後端契約已對齊；仍需 browser runtime smoke 驗 1、3、4 張。

## 4. X-SWSI-Client-ID

狀態：`IMPLEMENTED / FINAL_SMOKE_PENDING`

`zz_p0_stable_ai_client_id.part` 已建立 stable anonymous client ID：

- 優先 `crypto.randomUUID()`
- fallback `crypto.getRandomValues()`
- 儲存在 `localStorage` 的 `swsi_ai_client_id_v1`
- `swsiFetchWithTimeout()` 統一加入 `X-SWSI-Client-ID`

文字與照片 AI 都走 `swsiFetchWithTimeout()`，因此 contract 已實作。仍需 Network smoke 確認 header 實際送出。

## 5. E-115-2-R-1 PDF 私用字元

狀態：`IMPLEMENTED AT RUNTIME / SOURCE_NORMALIZATION_VERIFY_PENDING`

`00.part` 已有 `swsiCleanPUA()`：

- U+E129 -> （一）
- U+E12A -> （二）
- U+E12B -> （三）

`normalize()` 對題幹、選項、解析、mnemonic、extension、law、mistake 套清理；`loadAutoEssays()` 也在 merge 後清理申論題幹。

所以學生端 runtime 已不應顯示三個 PUA 字元。是否要在 source JSON 本身永久正規化可另外處理，但不是 blocking runtime bug。

## 6. LAW_UPDATED placeholder

狀態：`SUPERSEDED_COMPATIBILITY_STUB`

現行 `index.html` 仍存在：

`const LAW_UPDATED = new Set([ /* 舊版人工清單仍保留相容；正式狀態以 legal_status='changed' 為主 */ ]);`

它目前是空 set，`lawConfirmedChanged()` 優先支援正式 `legal_status==='changed'`，同時保留 legacy `LAW_UPDATED / law_updated` 相容判斷。

結論：這不是「待填半成品」。它已被 canonical legal mapping + official legal watch 架構取代，只剩相容 stub。後續重構可移除，但不應再有人手動往裡面維護法規題 ID。

## 7. Stored XSS

狀態：`PARTIALLY_IMPLEMENTED / NOT YET SAFE TO MARK DONE`

已確認 `00.part` 對主要刷題路徑做了大量 context-safe text escaping：

- subject/year/round -> `swsiEsc`
- question -> `swsiEscLines`
- theory/law deep-link 不再把名稱直接塞進 inline JS，而改用 index wrapper
- `esc()` 被重導到同一文字 encoder

但先前 audit 的 surface 很廣，還包含：

- options
- exp why/others/trap/raw
- topic/major/mistake
- summary/progress/review 聚合字串
- source URL scheme allowlist
- 其他晚載入 override

因此目前只能判「主路徑已有大量修正」，不能只因看到 escape helper 就宣告整站 Stored XSS DONE。需以 production-shaped build 做 sink grep + browser payload smoke。

## 8. Supabase recovery SQL drift

狀態：`CONFIRMED STILL OPEN (P1)`

Production `public.reset_ai_analysis_on_official_change()` 目前明確包含：

`new.grading_mode is distinct from old.grading_mode`

但 repo recovery/source-of-truth consolidation：

`supabase/migrations/20260825094110_production_qa_consolidation.sql`

其中同名 function 的 official-change 條件目前只列：

- question
- opt_a..opt_d
- answer
- accepted_answers

**缺 `grading_mode`。**

因此 schema drift 確認存在：production 是新版本，recovery SQL 是舊版本。

處理原則：更新 GitHub recovery/source-of-truth SQL 使其反映現行 production；不要因這個 drift 再把 consolidation migration 重套到 production。

## 9. Cloudflare Worker temperature=0

狀態：`IMPLEMENTED IN BRANCH / CONTRACT TEST STILL RECOMMENDED`

目前 fix branch `worker.js` 已使用：

`Number.isFinite(Number(body.temperature)) ? Number(body.temperature) : 0.4`

再 clamp 0..上限，因此合法 `temperature: 0` 不再被 `|| 0.4` 吃掉。

## 10. AI 429 classification

狀態：`IMPLEMENTED / FINAL_RUNTIME_SMOKE_PENDING`

最後層 `zzzz..._ai_quota_message.part` 會攔 `swsiFetchWithTimeout` 的 429 response，讀 Worker JSON：

- `error.message`
- `error.code`

`CLIENT_DAILY_QUOTA / GLOBAL_DAILY_QUOTA` 顯示「今日額度提醒」，其他 429 顯示「AI 使用提醒」。文字與照片 feedback 都被包住。

仍應做 browser smoke，確保晚載入 override / concurrent request 不會破壞這個暫時 wrapper。

---

# 本輪分類更新摘要

可從舊 `PENDING_VERIFY` 升級為「已有實作證據」：

- round canonical regression
- theory/law deep-link
- photo 1–3 contract
- X-SWSI-Client-ID
- PUA runtime cleanup
- Worker temperature 0
- AI 429 classification

可明確標 `SUPERSEDED`：

- 手工 `LAW_UPDATED` 待填清單（目前只剩空 compatibility stub）

仍確定未收尾：

- Stored XSS 全 surface 最終驗收
- Supabase recovery SQL drift
- 上述已實作功能的 browser/Chromium/production-shaped final smoke

下一輪應優先查：

1. history / review-state 是否有 cap 與 partial-bank gate
2. `參考骨架整理中` 是否仍有未覆蓋申論
3. `解析生成中` 是否能區分 pending / review / special grading
4. SEO / OG / aria 是否其實後續 commits 已做
5. 最後 GitHub Actions 狀態與哪些 workflow 仍因舊假設紅燈
