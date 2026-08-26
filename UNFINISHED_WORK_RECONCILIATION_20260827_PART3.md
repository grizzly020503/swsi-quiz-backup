# SWSI 未完成工作證據核對 — Part 3

日期：2026-08-27

本附錄延續 `UNFINISHED_WORK_LEDGER.md`、Part 1、Part 2。只記錄已重新核對 source / workflow logs 的項目。

## 1. history / review-state

### history 無上限
狀態：`STILL_OPEN`

`index.html` 目前核心：
- `loadHist()` 直接讀整個 `swsi_v2_history`。
- `record()` 每次 `h.push(...)` 後 `saveHist(h)`。
- 沒有 cap、rolling window、compaction 或 IndexedDB migration。

後置 code-health guard 已讓 `saveHist` / `saveReviewState` 寫入失敗時顯示可見警告，因此「靜默失敗」已有部分修復；但長期累積把 localStorage 撐大的根因仍存在。

結論：A11 不可標 DONE。應拆為：
- visible quota/write warning：IMPLEMENTED
- history bounded retention / migration：OPEN
- review-state size / cleanup policy：OPEN/PENDING DESIGN

## 2. partial-bank / review gate

狀態：`MOSTLY_IMPLEMENTED / NEEDS UI-SCOPE VERIFY`

monthly patch 已覆寫 `startDueReview`：若 `QB.allComplete` 為 false，會先 `await ensureAllQuestionsLoaded()`，再計算 `reviewSummary()`。因此「按開始到期複習時，partial bank 把舊錯題誤判不存在」這條主要路徑已被防住。

但 `reviewSummary()` 本身仍以當下 `ALL` 建立 `exists` set；若其他 UI 在 bank 未全載入時直接呼叫它，仍可能得到 partial view。需確認首頁/進度頁所有 summary call 是否也先 full-bank，或把 `reviewSummary` 本身改成明確只在 full bank 使用。

## 3. 申論 placeholder：『參考骨架整理中』

狀態：`LIKELY_SUPERSEDED / VERIFY COVERAGE`

repo code search 已找不到字面 `參考骨架整理中`。代表舊 placeholder 文案至少已不再以原字串存在。

但「找不到 placeholder 文案」不等於每一題 guide coverage 100%。仍應用 builder/registry 實際比對 ESSAYS IDs vs ESSAY_GUIDES IDs，列出缺 guide 題數；若為 0 才可正式標 DONE。

## 4. 選擇題 placeholder：『解析生成中』

狀態：`LIKELY_SUPERSEDED / VERIFY STATUS UX`

repo code search 已找不到字面 `解析生成中`。舊 placeholder 文案應已被後續 pending/review/AI analysis UX 取代。

仍需驗證前端是否能區分：
- analysis pending
- review
- special-credit / grading metadata abnormal
- truly no analysis

不要把「字串消失」誤當內容狀態模型已完整。

## 5. SEO / OG / canonical

狀態：`STILL_OPEN`

目前 `index.html` head 可見：
- `<title>社工師國考題庫</title>`
- manifest/icons/theme/mobile metadata

但目前核對段落未看到完整：
- meta description
- canonical URL
- Open Graph title/description/image/url
- Twitter card

因此舊 audit 的 SEO/OG 項目仍不能標 DONE。這是 P2，不應跟 P0 code-health 混同一施工批。

## 6. accessibility / aria

狀態：`PARTIAL`

現有 code 已有部分 aria，例如首頁考次 selector 使用 `aria-label="考試考次"`，部分 select 也有 aria-label；但不能據此宣告整站 keyboard/aria 完成。

需後續做：
- buttons/interactive div keyboard reachability
- focus states
- dialog/modal semantics
- aria-expanded for expandable cards
- screen-reader labels for icon-only controls

P2，獨立 accessibility pass。

## 7. GitHub Actions — Cloudflare preview 真實 failure 原因

狀態：`STILL_OPEN / WORKFLOW DESIGN ISSUE`

Branch `fix/code-health-p0-20260826` run `32983511775`：
- build current monthly frontend：PASS
- static smoke：PASS
- mark isolated preview：PASS
- publish preview files：FAIL

log 顯示 workflow 做法是：
1. 在修復 branch 建 `cdn/preview` 產物。
2. `git commit -m '發布 Cloudflare 新版前端預覽'`。
3. `git fetch origin main`。
4. `git rebase origin/main`。
5. `git push origin HEAD:main`。

失敗點：rebase 到最後 preview commit 時，`cdn/preview/monthly_patch.js` 與 main 發生 content conflict。

重要：這不是 runtime regression；是 preview workflow 把 derived preview artifact 從 feature branch rebase/push 回 main 的設計造成高衝突。

建議後續修法（由 code-health branch/Work 決定）：
- preview 不應從 feature branch直接 rebase + push main；
- 可改為 artifact/deployment branch，或讓 preview workflow 不持久化 derived files 到 main；
- 至少避免 `cdn/preview/monthly_patch.js` 這類生成物成為 feature/main rebase 衝突源。

因此目前不能說「GitHub Actions 全綠」。Monthly Frontend QA 在同一 SHA `bf597c5c...` 已 success，但 Cloudflare Preview workflow 仍 failure。

## 8. round / deep-link / photo / client ID / PUA（承接 Part 2）

這批 source evidence 維持：
- round DOM final contract `all/1/2`：IMPLEMENTED，需 browser smoke
- theory/law deep-link index normalization：IMPLEMENTED，需 click smoke
- photo >3 explicit reject：IMPLEMENTED
- stable `X-SWSI-Client-ID` through `swsiFetchWithTimeout`：IMPLEMENTED，需 network smoke
- PUA `E129/E12A/E12B -> （一）（二）（三）`：IMPLEMENTED

## 9. 本輪真正仍開著的工作

截至本輪，最明確仍未完成的不是大量功能，而是：

1. Supabase recovery SQL drift (`grading_mode` reset clause missing in repo recovery source)
2. history 無上限 / localStorage 長期膨脹
3. reviewSummary 的 full-bank contract 尚未完全封裝
4. Stored XSS 仍需完整 sink audit 收尾
5. Cloudflare preview workflow 會 feature -> rebase main -> push main，且目前真實紅燈
6. essay guide coverage 要用 ID 集合實測，不只搜尋 placeholder 文案
7. analysis pending/review UX 狀態模型需 browser verify
8. SEO / OG / canonical
9. accessibility / keyboard / aria 完整 pass

## 10. 不應重做的項目

以下已有明確 implementation evidence，不應再從零重寫：
- fail-closed runtime guard
- actual shard SHA-256 network byte verification
- mock-exam unified grading implementation
- Service Worker v6 mutable-asset network-first
- 107-1 essay guide normalization builder
- stable anonymous AI client ID
- photo 1–3 explicit frontend limit
- round all/1/2 final DOM normalization
- theory/law deep-link name -> index normalization
- Worker temperature=0 preservation
- server-message-based daily quota UI override
