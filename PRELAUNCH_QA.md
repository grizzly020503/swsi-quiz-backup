# SWSI 社工師國考平台 — 公開前 QA

最後更新：2026-08-25

> 原則：目前 **不修改會觸發 Netlify production deploy 的學生端檔案**。依既定策略，`index.html / manifest.json / sw.js` 等學生端修改留到月更一次套用；後端安全問題可即時修。

## QA 目標

公開前只看四件事：

1. 免費核心功能是否真的好用
2. 陌生使用者能否在 10 秒內知道怎麼開始
3. 公開後是否安全、穩定、成本可控
4. 手機／PWA／無障礙是否不會卡住考生

---

## P0 — 公開前必修

### 1. 選擇題 AI 解析文字需 escape，避免 stored XSS

**狀態：待月更修正**

目前 `renderQuiz()` 直接把下列資料插入 `innerHTML`：

- `item.exp.why`
- `item.exp.others`
- `item.exp.trap`
- `item.mnemonic`
- `item.law`

這些欄位部分由後台 AI 產生並存入 Supabase。即使目前 prompt 要求純文字，也不應把 AI／資料庫文字當可信 HTML。

**月更修法：** 所有上述欄位輸出前統一 `esc()`；需要換行時採安全的 escape 後再將換行轉 `<br>`。

驗收：測試內容含 `<img onerror=alert(1)>` 時只能顯示成文字，不可執行。

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

### 3. PWA 離線冷啟動仍依賴外部 CDN

**狀態：待驗證／待修**

`sw.js` 只快取同網域檔案，並明確不攔截跨網域；但 `index.html` 仍從：

- Google Fonts
- jsDelivr 的 `@supabase/supabase-js@2`

載入資源。

這代表「曾經正常載入過」的瀏覽器可能靠 HTTP cache 撐住，但真正無網路冷啟動時，若 Supabase JS 沒有瀏覽器快取，頁面可能在初始化前就失敗。

**建議：** 將必要 runtime（尤其 supabase-js）vendor 到同網域；字型則可接受系統字型 fallback，不應影響功能。

驗收：清除一般 HTTP cache、保留 PWA Cache Storage，切飛航模式後重新開 PWA，首頁／離線題庫仍能進。

### 4. 首頁沒有把「完全免費公開」的核心使命說清楚

**狀態：待月更修**

目前新版首頁主視覺是：

> 社工師國考 / 今天要練什麼？

使用流程很清楚，但第一次進站的人看不出這是「免費、公開、不鎖題」的平台。

**建議首頁保留行動導向，同時補一句：**

> 免費社工師國考學習平台｜歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。

不要把首頁變成長篇理念頁。

### 5. SEO／分享 metadata 不完整

**狀態：待月更修**

目前 `<head>` 有 title、PWA meta，但沒有完整的：

- meta description
- canonical
- Open Graph title / description
- 分享圖片 metadata

且 `title` 仍是「社工師國考題庫」，沒有「免費」定位。

**建議 title：** `社工師國考免費題庫｜SWSI`

---

## P2 — 公開後持續改善

### 6. 可點擊卡片大量使用 `<div onclick>`，鍵盤／輔具語意不足

**狀態：待改善**

首頁 `ux-link-card`、搜尋結果、部分 `gcard` 是可點 div；手機觸控沒問題，但鍵盤 Tab、Enter／Space 與 screen reader 語意不完整。

建議逐步改成 `<button>`／`<a>`，或至少加入 `role="button" tabindex="0"` 與鍵盤事件。

### 7. 時事雷達 `source_url` 應限制為 http/https

**狀態：防禦性改善**

目前文字有 escape，但 href 直接使用資料中的 `source_url`。來源由後台自動化產生，仍建議加入 URL scheme allowlist，只允許 `https:`／必要時 `http:`，避免日後資料污染導致 `javascript:` 類 URL。

### 8. 目前全平台 AI 每日閥門偏保守，需以 100 人 pilot 觀察

**目前 Worker：**

- 每 client 文字：10 次／日
- 每 client 照片：3 次／日
- 全站文字：50 次／日
- 全站照片：10 次／日

這能很好保護免費 API，但 100 人班級若大量同時試 AI，全站上限可能比個人上限更早觸發。

**暫不直接調高。** 先觀察 D1 一週使用量與 Groq 429，再決定公平性配置。AI 額度不足時，刷題、錯題、申論骨架仍必須完全免費可用。

### 9. 圖片數量上限需做一次真實 API 驗證

目前前端／Worker 可接受最多 4 張，UI 文案建議 1–3 張。Groq 不同官方文件對 Qwen 3.6 的圖片數上限描述目前不完全一致，因此公開前應用 1、3、4 張真實照片各測一次；若 4 張不穩，統一收斂為最多 3 張。

---

## 已驗收完成，不要重做

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
- [x] 最新考題同步／法規監測／時事雷達

---

## 下一輪 QA 順序

1. 刷題流程：選題 → 作答 → 解析 → 錯題入庫 → 下一題 → 結算
2. 間隔複習：1 → 3 → 7 → 14 → 30 日狀態轉移
3. 申論：拆題 → 草稿 → 文字 AI → 照片 AI → 額度錯誤訊息
4. 搜尋／理論／法規／時事雷達
5. iPhone PWA／離線冷啟動／更新快取
6. 無障礙與小螢幕（320–370px）
7. SEO／分享卡片
8. 最後才做 Netlify 月更部署與正式站 smoke test
