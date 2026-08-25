# SWSI 社工師國考平台 — 公開前 QA

最後更新：2026-08-25（Cloudflare 題庫 CDN production/runtime 驗收完成；學生端仍留月底一次修改）

> 原則：目前 **不修改會觸發 Netlify production deploy 的學生端檔案**。`index.html / manifest.json / sw.js` 等學生端修改留到月底一次套用。Supabase／Cloudflare 後端已完成的項目不要重做。

## QA 目標

公開前只看四件事：

1. 免費核心功能是否真的好用
2. 陌生使用者能否在 10 秒內知道怎麼開始
3. 公開後是否安全、穩定、成本可控
4. 手機／PWA／無障礙是否不會卡住考生

---

# P0 — 公開大量使用前必修

## 1. 前端題庫 loader 切到 Cloudflare CDN shard

**狀態：CDN 後端已完成；學生端切換待月底。**

目前正式 Netlify 舊版仍會直接從 Supabase 下載整套題庫；公開大量使用前，最後需要把學生端 loader 切到已上線的 Cloudflare Static Assets。

已完成的後端架構：

> Supabase = 後台 source of truth  
> GitHub Actions = 產生／驗證 exam-session shard  
> Cloudflare Static Assets = CDN cache  
> Netlify 前端 = 月底改成依需要載入 shard

目前 production：
- 4,800 題
- 24 個 baseline shard（104-1 ～ 115-2）
- 每 shard 200 題
- dataset revision：`8dafaf049f5200b54cd8`
- 未壓縮總量約 6.84 MB
- 單 shard 約 193–301 KB
- 24 題 `accepted_answers`、16 題一律給分皆保留

Cloudflare runtime 已驗：
- manifest HTTP 200
- 115-2 shard HTTP 200／200 題
- `CF-Cache-Status: HIT`
- `Access-Control-Allow-Origin: *` 單一值
- `Cache-Control: public, max-age=300, must-revalidate`
- `X-Content-Type-Options: nosniff`
- AI root no-Origin POST 仍為 403，證明 Static Assets 沒吃掉原 AI API

自動化：
- `scripts/build_question_shards.py`
- `.github/workflows/question-shards-build.yml`
- `.github/workflows/question-shards-publish.yml`
- 台灣時間每日約 11:10 比對
- dataset/header 不變不 commit
- 新考次資料不完整時 fail closed，不發布半套
- 未來 116、117…完整考次自動新增 shard
- 116-1 模擬已驗：5,000 題／25 shard／`116-1.json`

月底前端驗收：首頁不再先下載 4,800 題整包；指定歷屆只下載需要的考次；Supabase public egress 明顯下降；斷線時既有 IndexedDB/PWA fallback 不被破壞。

---

## 2. 24 題官方多答案的前端判題

**狀態：DB 已正確，前端 P0 待月底。**

Historical MOEX Answer Audit 已逐題核對 24 考次／4,800 題：

- 官方題數：4,800
- Supabase 題數：4,800
- 非完全一致：**0**

其中 **24 題**有 `accepted_answers`。

目前 DB：
- `accepted_answers` 已存在
- importer 已驗證多答案
- 主 `answer` 必須包含於 accepted set
- 24 題故意 `analysis_status='review'`

前端所有判題入口都要改成：

- 有 `accepted_answers` → 任一 accepted answer 都算對
- 無 → 沿用 `answer`
- `answer='一律給分'` → 全部給分

需驗：一般刷題、指定歷屆、錯題本、間隔複習、模擬考、正確率／弱點統計、結果頁正解顯示。

---

## 3. 選擇題動態文字需 escape，避免 stored XSS

**狀態：待月底 Netlify。**

目前 `renderQuiz()` 等處仍有資料直接進 `innerHTML`。包含題幹、選項、AI 解析、law、topic、major、mistake 等。

正式 DB 目前未發現 `<script>`、`<img>`、`javascript:`、`onerror=` 等已知惡意 payload，但這不能取代輸出 escape。

月更：所有動態文字先 `esc()`；需要換行時 escape 後再轉 `<br>`。

驗收：`<img src=x onerror=alert(1)>` 只能顯示文字，不執行。

---

## 4. 前端需送穩定 `X-SWSI-Client-ID`

**狀態：待月底 Netlify；Worker 已支援。**

目前舊前端未送 client ID，因此 D1 client quota fallback 成 IP + User-Agent hash。多人共用學校 Wi-Fi／宿舍／電信 NAT 可能互相吃額度。

月更：
- 首次 AI 使用產生匿名 UUID
- 存 localStorage
- 文字／照片 AI 都送 `X-SWSI-Client-ID`
- 不存姓名、Email、原始 IP

---

# P1 — 月更強烈建議一起修

## 5. 模擬考未作答沒有進錯題本／各科分母

**狀態：真 bug，待月底。**

目前總分會把未作答算錯，但只有 `picked != null` 才 `record()`，各科統計也只算已作答。

後果：
- 未作答降低總分卻不進錯題／間隔複習
- 各科正確率可能比總分漂亮
- 結果頁「錯題都已記錄」不完全成立

月更：未作答視為 incorrect，同樣進 record 與各科分母；UI 保留「未作答」。

---

## 6. AI quota 精確錯誤訊息被前端吃掉

**狀態：待月底。**

Worker 已分辨：
- `CLIENT_DAILY_QUOTA`
- `GLOBAL_DAILY_QUOTA`
- rate limit
- upstream 502/503

舊前端 429 幾乎都顯示同一句「等一下再試」，每日額度用完時會誤導。

月更：非 2xx 安全解析 JSON，優先顯示 `error.message`；daily quota 不顯示立即重試。

---

## 7. 全域搜尋點理論／法規不會自動展開

**狀態：真 UX bug，待月底。**

`openTheory(name)` / `openLawCard(name)` 用 name，但 render 判斷使用 index，造成跳到頁面後仍要再點一次。

月更：統一 open key 或先找 index。

---

## 8. 本機草稿／學習紀錄寫入失敗時完全靜默

**狀態：待月底。**

已有：
- oninput 儲存
- visibilitychange / pagehide 再儲存

問題：localStorage 寫失敗時 catch 後不提示。

最低修：顯示「已儲存在這台裝置」／「⚠ 無法儲存，請立即備份」。

現有 TXT 只可閱讀，不是一鍵還原；按鈕應明寫「匯出申論草稿（TXT）」。JSON 備份／還原可放後續。

---

## 9. 申論 AI 可信度與照片隱私文案

**狀態：待月底。**

不要再寫「已人工核對的正確骨架」這類沒有逐題證據的承諾。

建議：

> 「請優先依平台提供的參考骨架與關鍵字評估。」

照片／文字另補：

> 「會送至外部 AI 服務處理；請勿輸入或上傳可識別真實個案或個人的資料。」

保留「AI 回饋非官方評分」。

---

## 10. 照片 AI 公開版統一最多 3 張

**狀態：Worker 已完成；前端待月底。**

正式 Worker production 已：
- 最多 3 張
- 第 4 張拒絕
- 公開 image URL 只接受 JPEG data URL

Cloudflare production build 已 success；但「第 4 張 400／遠端 URL 400」仍應在合法 SWSI Origin 下做專項 runtime smoke，才可宣稱每條規則都實測。

月底前端：files > 3 直接提示「一次最多 3 張」，不要默默截斷。

---

## 11. 首頁沒有把「完全免費公開」說清楚

**狀態：待月底。**

保留「今天要練什麼？」的行動導向，但第一屏補：

> **免費社工師國考學習平台**  
> 歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。

不要做長篇理念頁。

---

## 12. SEO／分享 metadata 不完整

**狀態：待月底。**

補：meta description、canonical、Open Graph title/description/type；有正式分享圖才加 og:image。

建議 title：`社工師國考免費題庫｜SWSI`。

---

## 13. 核心作答介面鍵盤／輔具支援不足

**狀態：待月底。**

優先：
- 一般刷題 `.opt`
- 模擬考 `.mk-opt`
- 字級按鈕 aria-label
- select/input label

作答選項至少可 Tab、Enter/Space，並具 radio/selected 語意。

---

## 14. 色彩對比

**狀態：待月底視覺 QA。**

不用推翻整套配色；重點加深小字 muted、pine 小字、白字＋gold 實心背景。

---

## 15. 最新申論題 PDF 私用字元

**狀態：待月底同包。**

`E-115-2-R-1` 還有 `  `，部分手機／字型可能顯示方框。

改成 `(一)(二)(三)` 或穩定 Unicode，並補 parser 清理規則、auto payload、Service Worker cache version。

---

# P2 — 公開後／Pilot 觀察

## 16. AI 全站每日閥門目前偏保守

目前：
- 每 client 文字：10／日
- 每 client 照片：3／日
- 全站文字：50／日
- 全站照片：10／日

先不要直接調高。公開 pilot 後看 D1 usage 與 Groq 429。AI 額度不足時，刷題、錯題、申論骨架仍必須完全免費可用。

---

## 17. PWA 離線已有 fallback；月更要避免 cache version 沒跟著走

Supabase SDK 失敗有 REST fallback；網路也失敗有 IndexedDB 題庫 fallback。

真正風險：月更改 `essay_guides.js`、題庫 shard 或其他 cache-first 檔案時，忘記 bump `sw.js` VERSION。

真機驗收：在線完整載入 → 飛航模式 → 重開 PWA → 恢復網路 → 確認新版內容更新。

---

## 18. 時事雷達 URL scheme 防禦

目前 source URL 全為 HTTPS。前端仍建議只允許 `https:`（必要時 `http:`），防未來資料污染。

---

# 已驗收完成，不要重做

- [x] 一般刷題主流程正常
- [x] 1→3→7→14→30 間隔複習邏輯存在
- [x] 申論草稿 oninput + visibilitychange + pagehide 保存鏈存在
- [x] 歷屆申論 + 最新 auto essays 合併
- [x] 時事 Radar 使用既有 UI hook
- [x] 正式 DB 未發現已知惡意 HTML payload
- [x] Supabase `questions` / `essays` 公開唯讀
- [x] 危險 SECURITY DEFINER RPC 公開 execute 已撤銷
- [x] Cloudflare Origin allowlist；無 Origin／外站 → 403
- [x] `AI_RATE_LIMIT` 3/60s
- [x] `AI_IP_LIMIT` 30/60s
- [x] D1 `swsi-ai-quota`
- [x] `ai_daily_client_usage`
- [x] `ai_daily_global_usage`
- [x] D1 client/global 記帳已實測
- [x] Cloudflare public/internal 分流；internal 不吃學生 quota
- [x] 後台 AI pg_net timeout 30 秒
- [x] 24 小時 AI 完成上限 25 題
- [x] AI queue 排序已改 `qno → subject`
- [x] `analyze-pending-questions` production v7
- [x] GitHub analyzer source 已對齊 production v7
- [x] AI ready answer-meta DB 品質 trigger 已上線；ready meta 污染=0
- [x] 24 官方多答案已存 `accepted_answers`
- [x] 16 一律給分題刻意 review 隔離
- [x] Historical MOEX audit：**4,800 / 4,800，非完全一致 0**
- [x] MOEX sync 支援 M 更正答案／多答案／一律給分；解析不了 fail closed
- [x] 115030／115100 最新 workflow 全綠，目前皆 S、multi=0
- [x] importer production v3，GitHub source 已對齊
- [x] 法規監測 52/52 found、0 missing
- [x] legal mapping 改讀題幹＋四選項＋AI law
- [x] 題面直接出現 monitored law 卻漏 mapping：0
- [x] 目前 646 題已有 canonical mapping
- [x] `sync-legal-watch` production v2，GitHub source 已對齊
- [x] production QA migration delta 已備份到 `20260825094110_production_qa_consolidation.sql`
- [x] Cloudflare Static Assets 已掛 `cdn/`
- [x] 4,800 題已產生 24 個 exam-session shards
- [x] CDN manifest/shard production HTTP 200、CF cache、CORS/cache headers runtime 驗收完成
- [x] CDN 上線後 AI root no-Origin POST 仍 403
- [x] shard 每日自動同步、資料不變零 commit、資料不完整 fail closed
- [x] 未來考次自動擴充測試：116-1 → 5,000 題／25 shards success

---

# 下一步

不要再擴功能，也不要重做 Supabase／答案 audit／Cloudflare CDN。

下一階段依 `MONTHLY_PATCH_PLAN.md`，**等約定月底再一次動學生端**：

1. 前端題庫 loader 切到已上線的 Cloudflare shard，並讓 `normalize(r)` 帶 `accepted_answers`
2. 同包修：XSS、多答案、Client-ID、mock 未作答、quota 訊息、deep-link、storage、AI 文案、3 張、首頁免費定位、SEO、無障礙、申論私用字元
3. bump `sw.js` VERSION
4. diff review
5. Netlify production deploy **一次**
6. iPhone Safari / Android Chrome / 桌面 Chrome + PWA smoke test
7. 公開前做一輪真實學生 7 天 pilot，再決定是否新增功能

**目前仍未修改正式學生端。**
