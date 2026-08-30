# SWSI Architecture

本檔描述「現在實際存在的架構」與重要邊界，讓新 AI／工程師不用從頭 reverse engineer。

## 1. 系統分層

### A. 學生端前端
- `index.html`：legacy 單頁主程式與主要 UI。
- `monthly_patch.js`：由 `monthly_patch_parts/*.part` 組合出的後置 runtime patch。
- `essay_guides.js`：申論 guide registry；歷史上有 duplicate-key 技術債。
- `sw.js`：PWA Service Worker。
- `manifest.json`：PWA manifest。

目前前端屬「legacy core + 後置 patch」架構。**判斷現行行為時必須看最後載入順序，不可只看 `index.html` 前段舊碼。**

### B. 題庫來源與 CDN
- Supabase `questions`：正式選擇題 source of truth。
- `auto/questions_auto.json`：考選部增量同步／本地快照。
- `auto/essays_auto.json`：申論增量資料。
- `cdn/question-shards/manifest.json`：shard manifest 與 SHA metadata。
- `cdn/question-shards/*.json`：考次 shard，每完整考次 200 題。

學生端目標載入順序：優先 CDN shard，必要時 Supabase／本地備援；離線由 IndexedDB 保存最近完整 shard。

### C. Supabase
Production project：`Swsi` / `yumjtrdctaxyczpspuyo`。

主要責任：
- 4,800 道正式選擇題與官方 metadata。
- AI 解析狀態。
- legal watch / current affairs 相關資料。
- feedback reports。
- Edge Functions / cron / database triggers。

重要資料契約：
- `accepted_answers`
- `grading_mode`
- `analysis_status`
- official-change trigger 清理過期 AI 解析。

### D. Cloudflare
- Worker：`cloudflare/wandering-wave-4418/worker.js`
- AI proxy：Groq request、模型限制、CORS、大小限制、rate limit、每日 quota。
- D1：AI quota accounting。
- Static Assets：`cdn/`。

### E. GitHub Actions / CI
主要類型：
- MOEX 考選部同步／parser／health check。
- Unified Question QA。
- Monthly Frontend QA。
- Cloudflare Frontend Preview。
- 法規監測。
- production-shaped static smoke。
- 各類安全／grading／browser smoke。

正式發布 gate 以 `RELEASE.md` 為準。

## 2. 題庫資料層

### Official Core
官方核心資料只包含：
- 年度
- 考次
- 科目
- 題號
- 題幹
- A/B/C/D
- 官方主答案
- `accepted_answers`
- `grading_mode`
- 官方來源／考次識別

Official Core 可以由機器完整性驗證自動通過，不必每題人工審。

### Enrichment Layer
加值層包含：
- AI 選擇題解析
- 法規對照
- 申論考點／作答架構
- 時事連結
- 學習標籤

加值層可以 pending，不應因此阻擋官方題目發布；高風險內容再進人工 review queue。

## 3. 統一 QA 狀態機

目標不是「每題人工審」，而是 exception-based review：

- `passed`：官方核心機器檢查通過。
- `warning`：可發布，但有加值內容需注意。
- `needs_review`：需要人工快速確認。
- `blocked`：不得發布。

AI 解析／申論 guide pending 應進 generation backlog，不等於 human review queue。

## 4. Grading Contract

### standard
- 只有 `accepted_answers` 內答案正確。
- 未作答不得分。

### all_credit
- 官方一律給分。
- A/B/C/D 任一作答得分。
- **未作答也得分。**

### any_answer
- A/B/C/D 任一作答得分。
- **未作答不得分。**

任何特殊給分缺 mode 或 metadata 不一致：**fail closed。**

此 contract 必須同時用於：
- 一般刷題
- 計時模擬考
- 複習／錯題
- 分數統計
- smoke tests

## 5. 申論架構

歷史 `essay_guides.js` 曾以大量 generic template 救援，造成：
- 題目錯配
- 歷史政策倒灌
- duplicate key

目前逐題 verified audit 放在 `audit/essay_guide_audit_batch*_verified_*.md`。

長期目標：
- 一題一份唯一 guide。
- source registry 不允許 duplicate key。
- builder 產出唯一 key 的 deploy artifact。
- `guideMust / guideMustNot` 進 smoke。

## 6. PWA / Cache

Service Worker 必須遵守：
- HTML：network-first / no-store，離線才 fallback。
- `monthly_patch.js` / `essay_guides.js` / mutable manifest：network-first。
- Cloudflare shard / Supabase / AI：Service Worker 不攔截。
- 題庫離線版本一致性由 IndexedDB + manifest SHA contract 負責。

修改 mutable runtime asset 時必須評估 Service Worker cache version / invalidation。

## 7. Legacy + Patch 技術債

現在最大架構風險不是功能不足，而是同一功能可能存在：

`legacy implementation -> patch -> later patch -> emergency override`

所以：
- Audit 現行 bug 時要看「最後生效版本」。
- 新功能不要再無限新增 `zz/zzz/zzzz` 覆寫層。
- 能安全收斂時，逐步拆成模組：grading / loader / storage / simulation / essays / AI。
- 重構不能在沒有 regression tests 時一次大爆改。

## 8. 產品北極星

核心學習循環：

`做題 -> 發現不會 -> 解析/考點 -> 錯題 -> 間隔複習 -> 弱點 -> 申論 -> AI 回饋`

任何架構改動都應優先提升：
1. 正確性
2. 免費可用性
3. 手機體驗
4. 維護成本
5. 長期可擴充性

## 9. Monthly patch build/order contract

目前學生前端仍屬過渡式架構，不做 release 前的大爆改：

```text
legacy index.html
  -> scripts/monthly_patch_build.py 的 exact / fail-closed transforms
  -> monthly_patch_parts/*.part 依檔名 lexical order 串接
  -> _site/monthly_patch.js
  -> sanitizer / static QA / runtime-owner QA
  -> deployable _site
```

**`.part` 檔名同時是 execution order。** 因此重新命名、重新編號，即使內容沒變，也可能改變 runtime 行為；不得把檔名整理當成純 cosmetic change。

目前歷史晚層已被 grandfather，目標是停止繼續增生，而不是為了好看一次全部改名。結構基線與例外清單由 `config/monthly_patch_structure.json` 管理，`scripts/maintainability_smoke.py` fail-closed 驗證。

## 10. Current runtime ownership navigation map

本表用來讓新維護者快速定位；精確 owner chain 仍以 `scripts/runtime_owner_smoke.js` 的 executable contract 為準。

| Area | Primary / deliberate owner |
| --- | --- |
| Base runtime / normalize / grading helpers | `monthly_patch_parts/00.part` |
| Layout foundation | `15.layout-foundation.part` |
| Home product surface | `20.product-philosophy.part` |
| Focused quiz presentation | `30.focused-quiz-style.part` |
| Mobile reading | `40.mobile-reading-polish.part` |
| Storage durability | `60.storage-durability.part` |
| Review / progress learning loop | `70.learning-loop.part` |
| Learning Center | `71.my-learning-center.part` |
| Launch guidance / countdown | `73.launch-guidance-countdown.part` |
| Knowledge path | `80.knowledge-path.part` |
| Law trust presentation | `86.law-trust-ui.part` |
| Theory trust presentation | `88.theory-trust-ui.part` |
| Public branding / platform info | `89.public-branding-info.part` |
| Feedback core/context/UI/error copy | `90` / `91` / `92` / `93` parts |
| Mobile AI client / timeout / busy utilities | `99_p0_mobile_ai_guardrails.part` |
| Essay AI trust/privacy/error boundary | `99z.essay-trust-layer.part` |
| Essay navigation | `zzz_fix_essay_navigation.part` |
| Quick essay scope | `zzzzz_quick_essay_scope_fix.part` |
| Learning direct route | `zzzzzz_learning-center-direct-route.part` |
| Invalid grading/render fail-closed guards | `zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part` |
| Mock record policy | `zzzzzzzzzzzzzzzzzzzzzzzzzz_mk_record_policy.part` |
| Mock grading contract | `zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part` |
| Complete-question-bank invariant | `zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_question_bank_invariant.part` |

若本表與 executable QA 不一致，先停下來重新讀真實 runtime；不要用新 override 解決理解上的不確定性。

## 11. Human approval and incremental consolidation boundary

AI、automation 或 Draft PR 不得自行決定：
- 修改官方答案、`accepted_answers`、`grading_mode`；
- 弱化 Auth / authorization / RLS / security / CORS / secret handling；
- 建立或套用 production migration；
- merge `main`；
- production deploy。

未來降低歷史 patch 技術債採小步收斂：

`鎖行為 regression -> 搬到 canonical owner -> owner/subsystem tests -> 刪舊 shim -> 再測 -> 更新 architecture/handoff`

不要做 big-bang rewrite，也不要同一 PR 同時搬多個無關 owner。更完整的 scope-control 與 naming 規則見 `MAINTAINABILITY_POLICY.md`。
