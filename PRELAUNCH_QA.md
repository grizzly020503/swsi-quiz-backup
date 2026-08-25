# SWSI 社工師國考平台 — 公開前 QA

最後更新：2026-08-25（刷題／複習／模擬考／AI／法規鏈第一輪完成）

> 原則：目前 **不修改會觸發 Netlify production deploy 的學生端檔案**。依既定策略，`index.html / manifest.json / sw.js` 等學生端修改留到月更一次套用；後端安全問題可即時修。

## QA 目標

公開前只看四件事：

1. 免費核心功能是否真的好用
2. 陌生使用者能否在 10 秒內知道怎麼開始
3. 公開後是否安全、穩定、成本可控
4. 手機／PWA／無障礙是否不會卡住考生

---

## P0 — 公開前必修

### 1. 選擇題解析文字需 escape，避免 stored XSS

**狀態：待月更修正**

目前 `renderQuiz()` 直接把下列資料插入 `innerHTML`：

- `item.exp.why`
- `item.exp.others`
- `item.exp.trap`
- `item.exp.raw`
- `item.mnemonic`
- `item.law`
- `item.topic / item.major`
- `item.mistake`

這些欄位部分由後台 AI 產生並存入 Supabase。即使 prompt 要求純文字，也不應把 AI／資料庫文字當可信 HTML。

**現況掃描：**

- 目前正式 DB 未發現 `<script>`、`<img>`、`<iframe>`、`javascript:`、`onerror=`、`onload=` 等可疑內容。
- 有 18 題包含 `<` 字元，抽查皆為「溝通<合作<夥伴」、「平均數<中位數」等比較符號，**目前沒有已知 exploit 資料**。

**月更修法：** 所有上述欄位輸出前統一 `esc()`；需要換行時，先 escape 再將換行轉 `<br>`。

驗收：測試資料含 `<img src=x onerror=alert(1)>` 時只能顯示成文字，不可執行。

### 2. 前端需送穩定 `X-SWSI-Client-ID`

**狀態：待月更修正；Worker 已支援**

Cloudflare Worker 已接受 `X-SWSI-Client-ID`，並要求格式 `[A-Za-z0-9_-]{16,128}`；但目前 `index.html` 的文字 AI／照片 AI fetch 仍只送 `Content-Type`。

因此目前 D1 client quota 會 fallback 成 `IP + User-Agent` hash。多人共用學校 Wi‑Fi、宿舍或電信 NAT 時，可能互相吃到同一個人的每日額度。

**月更修法：**

- 第一次使用 AI 時用 `crypto.randomUUID()` 產生匿名 UUID
- 存 `localStorage`，例如 `swsi_ai_client_id_v1`
- 文字與照片 AI request 都帶 `X-SWSI-Client-ID`
- 不存姓名、Email、原始 IP

驗收：同一瀏覽器重開後 client key 不變；不同瀏覽器／裝置應不同。

---

## P1 — 月更前強烈建議修

### 3. 模擬考「未作答」沒有進錯題本／科目統計

**狀態：真實功能 bug，待月更修**

`MK.grade()` 現在：

- 未作答會被算進總分錯題（分母是 `Q.length`）
- 未作答也會出現在結果頁「錯題與詳解」
- **但只有 `picked != null` 才呼叫 `record()`**
- 各科 `bySubj` 也只計算已作答題

因此手動提早交卷或時間到時：

1. 未作答題降低總分，卻不進錯題／1→3→7→14→30 複習；
2. 各科正確率會排除未作答，可能看起來比總分漂亮；
3. 結果頁寫「這場的作答已記錄，去錯題本重練錯的題」，對未作答題並不完全成立。

**月更修法：** 模擬考交卷時把未作答視為 incorrect，同樣進 `record()` 與各科分母；picked 可保留 null 供 UI 顯示「未作答」。

### 4. AI 每日額度的錯誤訊息被前端吃掉

**狀態：待月更修**

Worker 已能分辨：

- `CLIENT_DAILY_QUOTA`
- `GLOBAL_DAILY_QUOTA`
- 短時間 rate limit / Groq 429

而且會回友善、精確的 `error.message`。

但目前文字／照片 AI 前端只看 HTTP status，429 一律顯示：

> 現在用的人比較多、或今天的免費額度用完了，等一下再試。

如果其實是「今天 10 次／3 次已用完」，叫使用者「等一下再試」會誤導。

**月更修法：** 非 2xx 時先安全解析 JSON；若有 `error.message` 就顯示後端訊息。`CLIENT_DAILY_QUOTA`／`GLOBAL_DAILY_QUOTA` 不顯示立即重試按鈕。

### 5. 首頁沒有把「完全免費公開」的核心使命說清楚

**狀態：待月更修**

新版首頁第一屏目前是：

> 社工師國考 / 今天要練什麼？

使用流程很清楚，但第一次進站的人看不出這是「免費、公開、不鎖題」的平台。Footer 雖已有「免費公開學習工具」，但太晚才看到。

**建議首頁保留行動導向，同時補一句：**

> 免費社工師國考學習平台｜歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。

不要把首頁變成長篇理念頁。

### 6. SEO／分享 metadata 不完整

**狀態：待月更修**

目前 `<head>` 有 title、PWA meta，但沒有完整的：

- meta description
- canonical
- Open Graph title / description
- 分享圖片 metadata

且 `title` 仍是「社工師國考題庫」，沒有「免費」定位。

**建議 title：** `社工師國考免費題庫｜SWSI`

### 7. 核心作答介面的鍵盤／輔具支援不足

**狀態：待月更改善；優先級高於一般卡片**

不只首頁卡片，連真正的作答選項也大量使用 `<div onclick>`：

- 一般刷題 `.opt`
- 模擬考 `.mk-opt`
- 首頁 `ux-link-card`
- 搜尋結果、部分 `gcard`

手機觸控可用，但鍵盤 Tab、Enter／Space 與 screen reader 語意不足。

**月更優先：** 先修一般刷題與模擬考選項，改 `<button>` 或至少 `role="radio" / tabindex="0" / aria-checked`＋鍵盤事件；換題後把 focus 放到新題題幹／題組。

### 8. 色彩對比有幾個地方不足 WCAG AA

**狀態：待月更視覺 QA**

靜態色碼估算：

- `--pine #4F7E76` 在淺底約 4.38:1，略低於一般文字 AA 4.5:1
- `--ink-soft #757A75` 在 `#EFF3F0` 約 3.91:1
- `--ink-3 #A9AFA9` 約 2.1:1
- 白字在 `--gold #95988A` 約 2.94:1，明顯不足

**建議：** 一般小字改更深的 muted 色；一般 pine 文字可用 `--pine-deep`; 金色實心卡若配白字需把背景加深。

---

## P2 — 公開後持續改善／月更一起驗證

### 9. 法規監測「未來變動」鏈完整，但既有解析仍需現行性抽查

**狀態：監測功能正常；不是 456 題失控**

確認後的完整流程：

> `moj_law_watch.py` → GitHub workflow → `sync-legal-watch` Edge Function → `legal_reference_registry` / `legal_watch_hits` → 依 `legal_canonical_names` 把受影響題目重設 `legal_status='unreviewed'`

因此從 2026-08-25 baseline 之後，只要監測法規官方修正日期改變，相關題目會被標回待檢查；**這條鏈是有接上的。**

既有資料現況：

- ready + unreviewed：1,028 題
- 解析疑似帶真正法條引用：約 458 題
- 其中 456 題已有 canonical law mapping
- 僅 2 題沒有 mapping，兩題都是「社會工作倫理守則」題，解析順帶引用《社會工作師法》第 17 條；不適合粗暴自動當成一般 MOJ 法規題

**結論：** 不要把 458 題當成錯題，也不要自動標 `verified_current`。後續應設「高風險解析抽查」：法條條號／期限／金額／比例優先核對現行官方法規。

### 10. PWA 離線冷啟動要做真機測試，但目前程式已有 fallback

**狀態：待 iPhone／Chrome 真機驗證，風險比初判低**

`index.html` 仍載入 Google Fonts 與 jsDelivr Supabase JS；`sw.js` 不快取跨網域。

但 `init()` 已有：

- Supabase SDK 有載入 → SDK 查題庫
- SDK 沒載入 → 直接 REST fallback
- 網路也失敗 → IndexedDB 完整題庫 fallback

因此外部 CDN 掛掉**不代表整站一定打不開**。Google Fonts 失敗更只是外觀 fallback。

驗收仍要做：清一般 HTTP cache、保留 PWA Cache Storage／IndexedDB，飛航模式重新開 PWA，確認首頁與離線題庫能進。

### 11. 時事雷達 `source_url` 應限制為 http/https

**狀態：防禦性改善**

目前文字有 escape，但 href 使用資料中的 `source_url`。來源由後台自動化產生，仍建議前端再加 URL scheme allowlist，只允許 `https:`／必要時 `http:`，避免日後資料污染導致 `javascript:` 類 URL。

### 12. 目前全平台 AI 每日閥門偏保守，需以 100 人 pilot 觀察

**目前 Worker：**

- 每 client 文字：10 次／日
- 每 client 照片：3 次／日
- 全站文字：50 次／日
- 全站照片：10 次／日

這能保護免費 API，但 100 人班級若同時試 AI，全站上限可能比個人上限更早觸發。

**暫不直接調高。** 先觀察 D1 一週使用量與 Groq 429，再決定。AI 額度不足時，刷題、錯題、申論骨架仍必須完全免費可用。

### 13. 圖片數量上限需做一次真實 API 驗證

目前前端／Worker 可接受最多 4 張，UI 文案建議 1–3 張。Groq 對 Qwen 3.6 的圖片上限文件描述曾出現差異，因此公開前應用 1、3、4 張真實照片各測一次；若 4 張不穩，統一收斂為最多 3 張。

---

## 已驗收完成，不要重做

- [x] 一般刷題：選題 → 作答 → `record()` → 下一題 → 結算，主流程正常
- [x] 間隔複習狀態：錯→1 日；答對→3→7；第三次答對掌握→14→30 長期確認；再錯則重置
- [x] 模擬考已確認「已作答題」會走同一個 `record()`／錯題排程
- [x] Supabase `questions` / `essays` 公開唯讀
- [x] 危險 SECURITY DEFINER RPC 公開 execute 已撤銷
- [x] Cloudflare Origin allowlist
- [x] 無 Origin／外站 → 403
- [x] `AI_RATE_LIMIT` 3/60s
- [x] `AI_IP_LIMIT` 30/60s
- [x] D1 `swsi-ai-quota`
- [x] `ai_daily_client_usage`
- [x] `ai_daily_global_usage`
- [x] D1 client / global 真實記帳驗收
- [x] Supabase `analyze-pending-questions` v6 正常
- [x] 後台 AI 解析 30 秒 pg_net timeout
- [x] 24 小時後台 AI 25 題上限
- [x] 最新考題同步
- [x] 法規監測：MOJ → Edge Function → question-level change reset 鏈確認
- [x] 時事雷達

---

## 下一輪 QA 順序

1. **申論流程**：拆題 → 草稿 → 本機保存 → TXT 備份 → 文字 AI → 照片 AI → 額度／斷線／錯誤訊息
2. 搜尋／理論／法規／時事雷達
3. iPhone PWA／離線冷啟動／更新快取
4. 小螢幕 320–370px＋字級 A/A/A
5. 月更 patch：P0/P1 一次修完
6. 最後才做 Netlify 月更部署與正式站 smoke test
