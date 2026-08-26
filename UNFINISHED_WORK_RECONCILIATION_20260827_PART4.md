# SWSI 未完成工作證據核對 — Part 4

日期：2026-08-27

本附錄延續 `UNFINISHED_WORK_LEDGER.md` 與前三份 reconciliation，記錄本輪對申論 guide、AI 解析狀態與 Stored XSS 的查證結果。

## 1. 申論 guide：coverage 與 verified 不能混為一談

狀態：`COVERAGE_EXISTS / VERIFIED_SCOPE_PARTIAL`

目前平台有大量 `ESSAY_GUIDES`，但 repo 中真正具備逐題來源查證 + browser audit registry 的正式批次，目前明確只有：

- `data/essay_guide_audit_batch1_20260826.json`
- `verified_count = 5`
- workflow `.github/workflows/essay-guide-audit.yml` 也硬性驗證這 5 題。

因此：

- 「有 guide」不代表「已逐題人工查證」。
- 不能把全部申論骨架標成 verified。
- UI/AI prompt 應只對有正式 evidence 的題目使用 verified / 已查證等級；其餘應標 SWSI 自製整理、待複核或一般參考架構。

這也解釋為什麼早期曾出現 generic cluster template 對錯題的情況。

## 2. 目前 5 題 verified audit 是真的有找出錯誤並修正

已核對 registry：5 題不是形式審查，而是都曾發現原 guide 與題幹不符，例如：

- generic 倫理模板沒回答三個服務階段
- 福利混合模板誤答社會安全網計畫
- 把訪談/焦點團體列成非反應性研究方法
- 用量化/質化比較誤答科學方法五特性
- 福利混合模板誤答 Le Grand 五個平等面向

因此這套 per-question audit 模式值得保留並擴充，但目前還不是全題完成。

## 3. AI 解析 production 真實狀態

Production Supabase 只讀查詢結果（2026-08-27）：

- ready: 4537
- pending: 221
- review: 42
- total: 4800
- `exp_why` 空白：263（剛好 pending + review）

這代表 production 資料狀態本身是一致的：ready 題有解析；pending/review 題沒有把半成品解析當 ready 發布。

## 4. review 42 題的原因

Production `analysis_status='review'`：

- 24 題：`官方多答案題：等待前端 accepted_answers 判題支援後重新解析`
- 16 題：`一律給分題：等待 analyzer 明確支援 A-D 全部計分後再生成解析`
- 2 題：`AI 回傳找不到 JSON array`

前兩類原因是舊 contract 留下來的 quarantine。現在 branch 已經有 accepted_answers / grading_mode frontend 支援，因此後續應重新評估是否可以安全 requeue 這 40 題，而不是永遠留在 review。

但這是 production data workflow 決策，不應由本內容 branch直接改資料。

## 5. 『解析生成中』舊 placeholder 的真正結論

狀態：`SUPERSEDED_TEXT / STATUS_UX_STILL_NEEDS_VERIFY`

舊字串已不存在，但 production 仍有 221 pending + 42 review，因此前端仍需要清楚呈現這些狀態。

正確 UX 應區分至少：

- 正常 ready 解析
- pending：解析尚未完成
- review：資料/特殊給分/AI 結構需人工或流程確認
- invalid grading metadata：不可猜判分

不能把所有沒有 exp_why 的題都顯示成同一個模糊 placeholder。

## 6. Stored XSS：目前不是 audit-only，但也還不能標 DONE

狀態：`PARTIALLY_IMPLEMENTED`

舊 `FRONTEND_XSS_AUDIT.md` 建立時註記「只做 code audit」。但之後 `monthly_patch_parts/00.part` 已有實際修正：

- `swsiEsc()` 處理 `& < > " '`。
- `swsiEscLines()` 先 encode 再把換行轉 `<br>`。
- 一般刷題 subject/year/round/question 已走 escape。
- `renderSummary()` weak topic 已用 `swsiEsc(t)`。
- theory/law deep-link 已用 index wrapper 避免把外部名稱直接塞進 inline JS。
- legacy `esc()` 被導向 `swsiEsc`。

因此 XSS 不能再標 `AUDIT_ONLY`。

但仍未完成的驗收：

- 全部 options / exp / topic / major / mistake / progress / review 的最後 runtime sink
- source URL scheme allowlist（repo search 尚未找到正式 `safeHttpUrl` helper）
- 所有晚載入 override
- browser payload smoke（IMG/SVG/attribute/JS-string payload）

所以最終狀態仍是 `PARTIALLY_IMPLEMENTED / FINAL_SECURITY_PASS_OPEN`。

## 7. Essay AI prompt 的可信度措辭要特別注意

`99_p0_mobile_ai_guardrails.part` 較早版本 prompt 仍可看到「校過骨架」等強烈措辭；另一方面 Cloudflare preview workflow 已經有 guard，禁止 Essay Trust Layer 再出現這種 overclaim。

結論：

- 不應假設所有 guide 都「已人工校過」。
- AI 批改 prompt 最終 production-shaped runtime 必須依 guide 的 review_status / source level 決定措辭。
- 只有正式 verified registry/metadata 題目才可使用強查證標籤。

## 8. Cloudflare preview workflow 再確認

Part 3 的判定維持：這支 workflow 目前設計真的會把 feature branch 生成的 `cdn/preview` commit 後 rebase `main`、再 push `main`。

這不是單純一次 merge conflict，而是高衝突發布設計。應由 code-health branch 修 workflow，而不是繼續靠重跑碰運氣。

## 9. 本輪更新後仍真正開著的核心項目

目前可進一步收斂為：

1. Supabase recovery SQL drift（production 有 grading_mode reset，repo recovery 缺）
2. history 無上限
3. reviewSummary full-bank contract
4. Stored XSS 最後 security pass + URL allowlist + browser payload smoke
5. Cloudflare preview workflow 不應 feature -> rebase/push main
6. 申論 guide 全量 ID coverage 與可信度分級
7. 申論逐題 verified audit 目前只正式完成 5 題，需後續批次擴充
8. 221 pending + 42 review 的解析狀態 UX / requeue policy
9. SEO / OG / canonical
10. accessibility / keyboard / aria 完整 pass

## 10. 不應誤判的事項

- 4537/4800 ready 不等於剩下 263 題是 bug；其中大部分是正常 queue/review 狀態。
- 有 ESSAY_GUIDES 不等於每題都 verified。
- 找不到舊 placeholder 字串不等於狀態 UX 已完整。
- 有 `swsiEsc` 不等於 Stored XSS 全面完成。
- Cloudflare Preview 紅燈目前主要是 workflow 發布設計，不是 Monthly Frontend static smoke 失敗。
