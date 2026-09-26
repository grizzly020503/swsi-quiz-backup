# SWSI 全平台健康檢查 — 2026-09-26

## 結論

本輪以 GitHub `main`、現行 build/runtime contract、QA workflow、production monitoring contract 與已完成的 Netlify controlled deploy cutover 為基礎做全平台稽核。

**目前沒有發現需要立即停站的 P0 runtime defect。**

核心學生端（題庫、判題、模擬考、錯題／複習、申論、本機儲存）、題庫資料契約、時事 V2、AI public guard、PWA、feedback/admin source contract 與 Cloudflare primary monitoring 都已有相當完整的 fail-closed / regression 保護。

本輪主要發現是：

1. Netlify 改成受控手動 release 後，Public Uptime 原本只驗「備援站可開」，沒有驗「備援站版本與 main 一致」。
2. MOEX workflow 的每日排程與 repo 自己的零成本營運政策衝突。
3. 多份歷史文件仍把已完成的 frontend/monthly patch 與 Netlify release 寫成 pending，會誤導後續維護。
4. Cloudflare primary 仍刻意保留 public soft-launch `noindex`；這是產品發布決策，不是本輪偷偷變更的 bug。
5. 自動無障礙掃描、真實 admin auth E2E、完整 disaster-recovery restore drill 仍屬 coverage / operations debt。

## 本輪直接修正

### 1. Netlify fallback release parity

`scripts/public_uptime_smoke.py` 新增 opt-in `--fallback-parity`：

- 從 repo root `index.html` 讀取 `swsi-netlify-release` marker。
- Netlify fallback 必須回傳同一 marker。
- fallback `/sw.js` 必須是 v7。
- fallback `/auto/current_affairs.json` 必須：
  - schema v2
  - 至少 17 sources
  - 0 feed errors
  - items 非空

`.github/workflows/public-uptime.yml` 在 main / scheduled / manual run 會使用：

`--monitoring-v2 --fallback-parity`

PR 本身仍只驗現有 production baseline，避免 feature branch 尚未 release 時造成假紅燈。

### 2. MOEX 常態 polling 降頻

`.github/workflows/moex-social-worker-sync.yml`：

- 原本：每天台灣時間 10:35。
- 調整：每週一台灣時間 10:35。
- `workflow_dispatch` 保留，官方放榜／答案更正窗口可人工加跑。
- current-affairs 已由 Public Monitoring Feed 每 6 小時處理，不需要依賴 MOEX workflow 每日掃。
- legal watch 自身仍有 min-days 節流。

`question-shards-publish.yml` 的每日 11:10 目前**保留**，因 shard 內還含可能非同步變化的 enrichment；且 workflow 已有 deterministic revision check，沒有變更就不 commit。

## 區塊健康狀態

| 區塊 | 狀態 | 稽核重點 |
| --- | --- | --- |
| Cloudflare primary | GREEN / DECISION | production uptime、SW v7、4800/24、AI/feedback preflight 有 sentinel；但 public HTML 仍是 deliberate soft-launch noindex |
| Netlify fallback | GREEN | controlled GitHub Actions deploy 已切換完成；本輪補 release parity sentinel |
| 題庫資料 | GREEN | 4,800 題、24 shards、每 shard 200；manifest SHA/bytes integrity 有 QA |
| 官方給分 | GREEN | 4,784 standard / 12 all_credit / 4 any_answer；24 multi-answer；統一 grading contract + browser smoke |
| 刷題／模擬考 | GREEN | round canonical、blank grading、各模式判分與 browser interaction regression |
| 錯題／間隔複習 | GREEN | common grading contract、review owner/regression；storage schema guard |
| 本機學習紀錄 | GREEN | 8,000 cap、schema validation、corrupt backup/quarantine、QuotaExceeded 可見警告 |
| CDN loader / 離線 | GREEN | manifest/shard integrity、WebCrypto SHA、IndexedDB provenance、full-bank fail closed、SW v7 |
| 申論 | GREEN | essay builder、duplicate-key guard、draft durability、AI trust/error boundary |
| AI public path | GREEN | Origin allowlist、rate/IP limits、client ID、image JPEG/max-3 guard、quota error contract |
| 時事 V2 | GREEN | 17 sources / 0 feed errors；11-class current snapshot baseline；event clustering、history-v2.2、trend radar |
| 法規 | GREEN | legal-watch snapshot + public contract；官方來源 URL guard |
| Feedback | GREEN | CORS/API safety smoke、context state、cluster/admin UI source contract |
| Admin | GREEN / AMBER COVERAGE | source/build auth hardening完整；真實登入/recovery E2E 主要仍為人工 |
| PWA | GREEN | SW v7、mutable assets no-store network-first、upgrade smoke |
| 無障礙 | AMBER COVERAGE | ARIA / aria-live / Escape / focus trap 已存在；未找到 axe/contrast 自動 gate |
| Disaster recovery | AMBER COVERAGE | migrations/recovery source/rebuild policy 有保存；未找到完整空環境 restore drill |
| Actions 成本 | IMPROVED | MOEX 常態 daily → weekly；current affairs 仍 6h；shards daily 目前保留 change-only publish |

## 核心資料／Runtime Evidence

### Question corpus

現行 `cdn/question-shards/manifest.json`：

- dataset revision：`1477c32ba7454a23fb1d`
- generated_at：`2026-09-15T14:48:02Z`
- total_questions：4,800
- shard_count：24
- baseline 104-1 ～ 115-2
- 每 shard 200 題

不要把 revision 當永久 invariant；題目 enrichment 改變時 revision 可正常變化。

### Grading

現行防回歸鏈包含：

- `gradingMode()`
- `acceptedAnswers()`
- `isCorrectAnswer()`
- `answerLabel()`
- `scripts/grading_contract_smoke.js`
- `scripts/p0_frontend_preflight.js`
- Monthly Frontend QA Chromium interaction

特殊給分缺 metadata 走 fail closed，不從「一律給分」字樣或 legacy ID 猜 mode。

### Storage

`Storage Durability QA` 已覆蓋：

- history retention cap = 8,000
- invalid write preservation
- corrupt payload quarantine
- corrupt backup failure → block overwrite
- history/review QuotaExceeded visible warning
- `record()` chain 不吞掉前段 storage error

### Current affairs

現行 production contract：

- sources >= 17
- feed errors = 0
- signals questions_loaded = 4,800
- signal matching = `event-evidence-v2.2`
- event aggregation = `max-quality-member-plus-year-union-v2.2`
- trend method = `deterministic-v2.2`
- same-topic / same-law 分離
- weighted historical evidence 不得超過 raw same-topic count
- 每個 public event/trend 可追溯 evidence

Reuters / AP / BBC 未接入是授權政策決定，不是 defect。

## 需要 owner 明確決策

### Cloudflare noindex

目前 `cdn/index.html` 與 Cloudflare soft-launch release workflow 明確保留：

`<meta name="robots" content="noindex,nofollow,noarchive">`

workflow 註解也明確說 first public soft launch 要先阻止搜尋引擎索引。

因此：

- 直接網址使用不受影響。
- 但若目標是正式讓 Google 等搜尋引擎自然搜尋到 SWSI，必須另做一次「soft launch → indexed public release」決策與 release PR。
- 本輪健康檢查**不自行移除 noindex**。

## 尚未發現，但應持續防回歸

- 不得讓 AI 改官方題幹／答案／grading_mode。
- 不得因新聞來源數增加就放寬 relevance。
- 不得讓 Netlify fallback 靜默落後 main release。
- 不得重新開 Supabase public write 或高權限 SECURITY DEFINER execute。
- 不得把跨域 question shards 硬塞進 SW shell cache。
- 不得重新接回 Netlify 獨立 Git build，避免兩套 build path 漂移。

## Evidence 限制

本輪聊天環境無法直接對 workers.dev / Netlify 做任意外部 HTTP/browser 探測，因此：

- production health 依據 repo 現行 CI/sentinel contract、既有成功 production evidence，以及本次使用者確認的 Netlify controlled deploy 全綠。
- 本輪新增 parity sentinel 會在 merge 到 main 後由 GitHub Actions 對真實 public endpoints 執行。
- 若 main post-merge sentinel 失敗，應以該真實 run 作為最高優先級證據，不得宣稱本輪已通過 production parity。

## 下一階段

建議順序：

1. 合併本輪 health hardening，讓 main sentinel 開始驗 Netlify parity。
2. 觀察一次 main / scheduled sentinel。
3. 由 owner 決定 Cloudflare 是否解除 soft-launch noindex。
4. 後續低風險加強：axe/contrast accessibility gate。
5. 建立一次可重現的 disaster-recovery restore drill（不碰 production、使用隔離環境）。
6. patch-over-patch 模組化維持 P2，不為了漂亮而大改目前已穩定 runtime。
