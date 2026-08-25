# SWSI 社工師國考平台 — 公開前 QA

最後更新：2026-08-25（第二輪：申論／搜尋／PWA／解析品質／AI 排程完成）

> 原則：目前 **不修改會觸發 Netlify production deploy 的學生端檔案**。依既定策略，`index.html / manifest.json / sw.js` 等學生端修改留到月更一次套用；後端／資料庫行為若要修改，先審核再另行套用。

## QA 目標

公開前只看四件事：

1. 免費核心功能是否真的好用
2. 陌生使用者能否在 10 秒內知道怎麼開始
3. 公開後是否安全、穩定、成本可控
4. 手機／PWA／無障礙是否不會卡住考生

---

## P0 — 公開前必修

### 1. 選擇題動態文字需 escape，避免 stored XSS

**狀態：待月更修正**

目前 `renderQuiz()` 直接把題幹、選項與部分資料插入 `innerHTML`，包含：

- `item.q`
- `item.options[A-D]`
- `item.exp.why`
- `item.exp.others`
- `item.exp.trap`
- `item.exp.raw`
- `item.mnemonic`
- `item.law`
- `item.topic / item.major`
- `item.mistake`

其中解析欄位部分由後台 AI 產生並存入 Supabase。即使 prompt 要求純文字，也不應把 AI／資料庫文字當可信 HTML。

**現況掃描：**

- 目前正式 DB 未發現 `<script>`、`<img>`、`<iframe>`、`javascript:`、`onerror=`、`onload=` 等可疑內容。
- 題目／解析出現 `<` 的案例目前都是「溝通<合作<夥伴」、「平均數<中位數」等比較符號，**目前沒有已知 exploit 資料**。

**月更修法：** 所有動態文字輸出前統一 `esc()`；需要換行時，先 escape 再將換行轉 `<br>`。

驗收：測試資料含 `<img src=x onerror=alert(1)>` 時只能顯示成文字，不可執行。

### 2. 前端需送穩定 `X-SWSI-Client-ID`

**狀態：待月更修正；Worker 已支援**

Cloudflare Worker 已接受 `X-SWSI-Client-ID`，並要求格式 `[A-Za-z0-9_-]{16,128}`；但目前 `index.html` 的文字 AI／照片 AI fetch 仍只送 `Content-Type`。

因此目前 D1 client quota 會 fallback 成 `IP + User-Agent` hash。多人共用學校 Wi-Fi、宿舍或電信 NAT 時，可能互相吃到同一個人的每日額度。

**月更修法：**

- 第一次使用 AI 時用 `crypto.randomUUID()` 產生匿名 UUID
- 存 `localStorage`，例如 `swsi_ai_client_id_v1`
- 文字與照片 AI request 都帶 `X-SWSI-Client-ID`
- 不存姓名、Email、原始 IP

驗收：同一瀏覽器重開後 client key 不變；不同瀏覽器／裝置應不同。

---

## P1 — 月更／公開前強烈建議修

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

### 4. AI 每日額度的精確錯誤訊息被前端吃掉

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

### 5. 已確認兩筆 AI 解析需要修正，並應建立自動品質閥門

**狀態：真實內容品質問題；目前官方答案本身沒有被改動**

對 4,625 題 `ready` 解析做規則掃描：

- 2,097 題的 `exp_why` 可直接辨識開頭 `(A)/(B)/(C)/(D)`
- 只有 2 題開頭字母與官方答案不一致
- 其中兩題都值得修正文案

**已確認：**

1. `SP113-1-30`（113-1 社政法 Q30，官方答案 D）
   - 目前 `exp_trap` 誤寫成「官方答案有瑕疵，D 其實為真」。
   - 題目 D 的完整敘述其實是把通常保護令有效期限說成 **5 年**；現行／當時規定並非 5 年，因此官方 D 沒問題。
   - **這是解析錯誤，應刪掉錯誤的『答案有瑕疵』判斷並重寫。**

2. `SP105-1-31`（105-1 社政法 Q31，官方答案 B）
   - 目前解析殘留模型自我修正文字：「(A)是錯的——其實是對的描述被當成錯選？不……」。
   - B 的問題是把「**以提供到宅托育為限**」寫反成「**不得提供到宅托育**」。
   - 應直接清楚說明 B 為何錯，不讓學生看到模型思考殘渣。

**建議新增自動品質檢查：**

- `ready` 題若解析開頭選項字母與官方答案不一致 → 報告／人工複查
- 解析含「答案有瑕疵／官方答案／題庫正解／建議複查」 → 進人工 review queue
- AI 可以說「此題有爭議」，但必須有可核對來源；不得只靠模型自行推翻官方答案

目前 4,625 題 ready 中沒有任何「空殼 ready」：`exp_why`、topic、mistake 均有內容。

### 6. 最新考次 AI 解析排程目前「一科做完才換下一科」

**狀態：後台排序策略問題；不增加成本即可改善**

目前 4,800 題：

- ready：4,625
- pending：175

175 題 pending 全部屬於最新 `115100` 考次。該考次 200 題目前已完成 25 題，而這 25 題**全部集中在人類行為與社會環境**：

- 人類行為與社會環境：25 ready / 15 pending
- 其餘四科：各 40 pending

原因是 `claim_pending_ai_questions()` 現行排序：

> `source_exam_code → subject → qno → id`

因此會把同一科吃完再換下一科。

**建議改為：**

> `source_exam_code → qno → subject → id`

每日 25 題上限不變，但大致可分成五科各 5 題，讓最新考次的解析更平均地提供給不同科目的學生。

目前沒有 attempts ≥ 2、卡在 analyzing、或其他異常狀態的題目。

### 7. 全域搜尋點「理論／法規」不會自動展開內容

**狀態：真實 UX bug，待月更修**

目前：

- `openTheory(name)` 把 `theoryOpen` 設成理論名稱字串
- `renderTheories()` 卻用 `theoryOpen === gi`（數字 index）判斷展開
- `openLawCard(name)` / `renderLaws()` 有相同問題

結果是從搜尋結果點某理論／法規後，會成功跳頁並篩到那一筆，**但不會自動展開內容**，使用者還要再點一次。

**月更修法：** `openTheory()` / `openLawCard()` 先找實際陣列 index，或統一用 name 當 open key。

### 8. 本機草稿／學習紀錄寫入失敗時完全靜默

**狀態：資料可靠性 UX 問題，待月更修**

目前：

- 申論草稿每次輸入會寫 `localStorage`
- `visibilitychange` / `pagehide` 會再強制存一次，這部分很好
- 但 `saveDraft()`、`saveHist()`、`saveReviewState()` 對 localStorage 錯誤都是 catch 後不提示

若 Safari 私密模式、網站儲存空間異常或 quota 滿，畫面可能仍讓學生以為「已經儲存」。

另外「備份我的申論草稿」目前匯出的是 TXT：

- 人可以閱讀、另存沒問題
- **但平台沒有匯入功能，不能一鍵還原**

**月更最低修法：** 顯示「已儲存／儲存失敗，請立即備份」狀態。

**後續較完整方案：** 增加 JSON 備份／還原，包含申論草稿、刷題歷史、間隔複習與字級設定；並限制／壓縮無限成長的原始刷題 history。

### 9. 申論 AI 的可信度文案需要收斂，照片隱私要更透明

**狀態：待月更修文案**

目前 AI prompt 寫：

> 「校過骨架（已人工核對的正確考點／破題／必踩大標／關鍵字）」

但 `essay_guides.js` 目前能確認的是從已部署版本救援重建，沒有證據顯示約 230 題每一題都完成逐題人工審核。

**建議改成：**

> 「請優先依平台提供的參考骨架與關鍵字評估。」

不要過度宣稱「全部已人工核對」。

照片流程目前會：

- 前端 canvas 縮圖
- 轉成 JPEG data URL
- 送到 Cloudflare Worker → 外部 AI 服務處理
- 前端程式沒有把照片存入 Supabase、D1 或 localStorage

**建議隱私文案再明講：**「照片會送至外部 AI 服務進行辨識與回饋，請勿包含可識別真實個案或個人資料。」

### 10. 照片 AI 公開版統一最多 3 張

**狀態：規格決策已收斂，待月更 + Worker 同步**

目前前端／Worker 實際可接受最多 4 張，UI 文案本來就建議 1–3 張。

Groq 官方文件目前有衝突：Vision 指南寫較高上限，但 Qwen 3.6 模型頁明確標示 `MAX INPUT IMAGES = 3`。先前以測試圖打 API 得到 502，但 Worker 隱藏 upstream 細節，因此不能拿該測試證明 4 張一定不支援。

**公開版採保守規格：最多 3 張。**

理由：

- 符合模型頁最保守限制
- 與 UI 原本建議一致
- 降低學生一次吃掉過多照片額度
- 避免因官方文件差異造成偶發失敗

### 11. 首頁沒有把「完全免費公開」的核心使命說清楚

**狀態：待月更修**

新版首頁第一屏目前是：

> 社工師國考 / 今天要練什麼？

使用流程很清楚，但第一次進站的人看不出這是「免費、公開、不鎖題」的平台。Footer 雖已有「免費公開學習工具」，但太晚才看到。

**建議首頁保留行動導向，同時補一句：**

> 免費社工師國考學習平台｜歷屆試題、解析、錯題複習與申論練習，不鎖題、不賣解答。

不要把首頁變成長篇理念頁。

### 12. SEO／分享 metadata 不完整

**狀態：待月更修**

目前 `<head>` 有 title、PWA meta，但沒有完整的：

- meta description
- canonical
- Open Graph title / description
- 分享圖片 metadata

且 `title` 仍是「社工師國考題庫」，沒有「免費」定位。

**建議 title：** `社工師國考免費題庫｜SWSI`

### 13. 核心作答介面的鍵盤／輔具支援不足

**狀態：待月更改善；優先級高於一般卡片**

不只首頁卡片，連真正的作答選項也大量使用 `<div onclick>`：

- 一般刷題 `.opt`
- 模擬考 `.mk-opt`
- 首頁 `ux-link-card`
- 搜尋結果、部分 `gcard`

手機觸控可用，但鍵盤 Tab、Enter／Space 與 screen reader 語意不足。

另有：

- A/A/A 三個字級鈕對 screen reader 都只會讀成「A」，應給不同 `aria-label`
- 部分 select／input 只靠周邊文字或 placeholder，應補可程式識別的 label／aria-label

**月更優先：** 先修一般刷題與模擬考選項，改 `<button>` 或至少 `role="radio" / tabindex="0" / aria-checked`＋鍵盤事件；換題後把 focus 放到新題題幹／題組。

### 14. 色彩對比有幾個地方不足 WCAG AA

**狀態：待月更視覺 QA**

靜態色碼估算：

- `--pine #4F7E76` 在淺底約 4.38:1，略低於一般文字 AA 4.5:1
- `--ink-soft #757A75` 在淺底約 3.9–4.2:1
- `--ink-3 #A9AFA9` 約 2.1:1
- 白字在 `--gold #95988A` 約 2.9:1，明顯不足

**建議：** 不用推翻整套配色；只把小字 muted／gold 文字加深一級，一般 pine 小字改用 `--pine-deep`，金色實心卡若配白字則把背景加深。

---

## P2 — 公開後持續改善／月更一起驗證

### 15. 法規監測「未來變動」鏈完整，但既有解析仍需現行性抽查

**狀態：監測功能正常；不是數百題失控**

確認後的完整流程：

> `moj_law_watch.py` → GitHub workflow → `sync-legal-watch` Edge Function → `legal_reference_registry` / `legal_watch_hits` → 依 `legal_canonical_names` 把受影響題目重設 `legal_status='unreviewed'`

因此從 2026-08-25 baseline 之後，只要監測法規官方修正日期改變，相關題目會被標回待檢查；**這條鏈是有接上的。**

目前 registry：52/52 皆可匹配官方來源、0 missing、目前狀態皆 unchanged。

既有資料現況：

- ready + unreviewed：約 1,028 題
- 解析疑似帶真正法條引用：約 458 題
- 其中 456 題已有 canonical law mapping
- 僅 2 題沒有 mapping，兩題都是「社會工作倫理守則」題，解析順帶引用《社會工作師法》第 17 條；不適合粗暴自動當成一般 MOJ 法規題

**結論：** 不要把 458 題當成錯題，也不要自動標 `verified_current`。後續設「高風險解析抽查」：法條條號／期限／金額／比例優先核對現行官方法規。

### 16. PWA 離線已有 fallback；真正要防的是 cache version 沒跟月更走

**狀態：待 iPhone／Chrome 真機驗證**

`index.html` 仍載入 Google Fonts 與 jsDelivr Supabase JS；`sw.js` 不快取跨網域。

但 `init()` 已有：

- Supabase SDK 有載入 → SDK 查題庫
- SDK 沒載入 → 直接 REST fallback
- 網路也失敗 → IndexedDB 完整題庫 fallback

因此外部 Supabase JS CDN 掛掉**不代表整站一定打不開**；Google Fonts 失敗更只是外觀 fallback。把 supabase-js 搬回自己網域不是公開前硬阻塞。

真正的更新陷阱是：`essay_guides.js` 屬於 cache-first 靜態檔。若月更改了 `essay_guides.js`，卻沒有更新 `sw.js` VERSION／讓新 Service Worker 安裝，已安裝 PWA 的學生可能一直看到舊骨架。

**月更 checklist：只要 `essay_guides.js` 有變，就檢查／提高 `sw.js` cache VERSION。**

真機驗收：先在線上完整載入一次 → 關網路／飛航模式 → 重開 PWA → 確認首頁與離線題庫可進；再恢復網路確認新版骨架能更新。

### 17. 時事雷達 `source_url` 應限制為 http/https

**狀態：防禦性改善；目前資料乾淨**

目前 Supabase／snapshot 的時事來源均為 HTTPS，沒有危險 scheme；但 href 使用資料中的 `source_url`。

建議前端再加 URL scheme allowlist，只允許 `https:`／必要時 `http:`，避免日後資料污染導致 `javascript:` 類 URL。

### 18. 目前全平台 AI 每日閥門偏保守，需以 pilot 觀察

**目前 Worker：**

- 每 client 文字：10 次／日
- 每 client 照片：3 次／日
- 全站文字：50 次／日
- 全站照片：10 次／日

這能保護免費 API，但若 100 人班級同時試 AI，全站上限可能比個人上限更早觸發。

**暫不直接調高。** 先觀察 D1 一週使用量與 Groq 429，再決定。AI 額度不足時，刷題、錯題、申論骨架仍必須完全免費可用。

---

## 已驗收完成，不要重做

- [x] 一般刷題：選題 → 作答 → `record()` → 下一題 → 結算，主流程正常
- [x] 間隔複習狀態：錯→1 日；答對→3→7；第三次答對掌握→14→30 長期確認；再錯則重置
- [x] 模擬考已確認「已作答題」會走同一個 `record()`／錯題排程
- [x] 申論草稿：oninput + visibilitychange + pagehide 本機保存鏈存在
- [x] 歷屆申論 + 最新 auto essays 合併到同一 `window.ESSAYS`
- [x] 時事 Radar 是 hook 原本 `NL.open()`，不是重複第二套時事 UI
- [x] 目前題目／解析資料未發現惡意 HTML payload
- [x] 4,625 題 ready 無空殼解析；175 pending 全屬最新 115100
- [x] 後台 AI queue 目前無 attempts ≥ 2／卡住 analyzing 題
- [x] Supabase `questions` / `essays` 公開唯讀
- [x] 危險 SECURITY DEFINER RPC 公開 execute 已撤銷
- [x] Cloudflare Origin allowlist
- [x] 無 Origin／外站 → 403
- [x] `AI_RATE_LIMIT` 3/60s
- [x] `AI_IP_LIMIT` 30/60s
- [x] D1 `swsi-ai-quota`
- [x] `ai_daily_client_usage`
- [x] `ai_daily_global_usage`
- [x] D1 client / global 原子式記帳邏輯驗收
- [x] Supabase `analyze-pending-questions` v6 正常
- [x] 後台 AI 解析 30 秒 pg_net timeout
- [x] 24 小時後台 AI 25 題上限
- [x] 最新考題同步
- [x] 法規監測：MOJ → Edge Function → question-level change reset 鏈確認
- [x] `legal_reference_registry` 52/52 正常
- [x] 時事雷達現有 source URL 全部 HTTPS

---

## 下一步：先做「月更 Patch 設計」，再動正式站

下一階段不再擴功能，先把以上問題整理成可一次套用、可回滾的 patch：

1. `index.html`：XSS escape、Client-ID、mock 未作答、quota 訊息、搜尋 deep-link、儲存狀態、AI 文案、3 張限制、首頁免費定位、SEO、無障礙、對比
2. `worker.js`：照片最大 3 張，並補公開圖片格式／文字 payload 的防禦性驗證
3. Supabase migration 候選：AI queue 排序由 `subject → qno` 改成 `qno → subject`，每日 25 題上限不變
4. 解析品質：先修 `SP113-1-30`、`SP105-1-31`，再增加自動 quality report
5. `sw.js`：跟學生端月更一起 bump VERSION，避免舊 PWA 吃舊 `essay_guides.js`
6. 月更前做 diff review；套用後才進 Netlify production smoke test

**目前仍未修改正式學生端／正式題目資料／AI queue 排序。**