# SWSI Admin & Monitoring v1 規劃

## 目的

SWSI 已有題庫、模擬考、錯題複習、申論、AI 回饋、法規／理論與使用者回報等功能，也已有大量工程層 QA 與監測。

下一階段的重點不是再增加更多工程畫面，而是建立一個**非工程背景管理者也能使用的管理中心**。

核心原則：

> 管理者只需要知道「現在是否正常、哪裡需要處理、該做什麼」，不需要理解 GitHub Actions、SQL、JSON、SHA、runtime owner 等工程細節。

本規劃屬於 Round 8 之後的新階段，不得為了實作本規劃而修改已封版的 Round 8 production artifact。

---

## 1. 管理中心入口

建議未來建立受保護的管理入口，例如：

`/admin`

要求：
- 一般學生不可看到或存取。
- 必須有管理者身分驗證。
- 不可把 Supabase service-role key、Netlify token、Cloudflare token 或其他 production secret 放進前端。
- 管理頁只顯示必要資訊；進階工程資訊另放「詳細資料」區。

---

## 2. Admin v1 四個主要頁面

### A. 總覽

管理者打開後第一眼只需要看到：

- 網站：正常 / 注意 / 異常
- 題庫：例如 4,800 / 4,800
- Supabase：正常 / 異常
- AI：正常 / 使用量過高 / 暫停
- Service Worker 版本
- production 版本與最近部署時間
- 今日使用者數
- 今日作答題數
- 今日模擬考次數
- 今日申論練習數
- 今日 AI 批改次數
- 待處理使用者回報數

最上方增加：

### 「現在需要我做什麼？」

正常時：

> 🟢 目前不需要處理任何事情。

有問題時：

> 🔴 AI 異常流量增加。建議暫停 AI 批改，基本刷題功能仍可使用。

避免只顯示 HTTP 429、500、Supabase error 等工程訊息；應翻成中文管理語言。

---

### B. 使用者回報

目前回報資料已存於 Supabase：

`public.swsi_feedback_reports`

Admin v1 應讓管理者直接在網站後台處理，不必進 Supabase Table Editor。

主要顯示欄位：
- `report_no`：回報編號
- `created_at`：回報時間
- `status`：待處理 / 處理中 / 已解決
- `category`：回報類型
- `context_type`：選擇題 / 申論 / 法規 / 理論 / 網站
- `context_title`：回報發生位置
- `subject`
- `exam_year`
- `exam_round`
- `question_no`
- `message`：使用者內容
- `contact`：選填聯絡方式
- `reviewer_note`：管理者處理備註
- `resolved_at`：完成時間

管理功能：
- 篩選「待處理」
- 篩選回報類型
- 依題號／法規／理論搜尋
- 標記「處理中」
- 標記「已解決」
- 填寫處理備註
- 多人重複回報同一題時提高優先級

未來可顯示：

> #1042 題目解析疑問｜待處理  
> 115 年第 2 次／第 37 題  
> 「這題引用的法規是不是已經修正？」

---

### C. 系統監測

管理者版本的監測應簡單，不直接展示大量 logs。

#### 網站健康
- 首頁是否可開啟
- production 是否在線
- 最近一次成功部署
- production commit / version
- Service Worker version

#### 題庫健康
- question shard 數量
- 題目總數
- manifest 是否一致
- shard load failure 次數
- 題庫 integrity 最後檢查時間

#### AI 健康
- 今日文字 AI 次數
- 今日照片 AI 次數
- 429 次數
- timeout 次數
- 其他 AI error 次數
- 近一段時間 error rate

#### Supabase 健康
- API 是否可連線
- 回報是否可寫入
- 重要資料表是否正常
- Edge Function 是否有大量錯誤

#### 瀏覽器／PWA
- Service Worker 更新狀態
- v5 → v6 等 upgrade 是否異常
- 前端重大 JS error 次數

顯示方式建議：

> 🟢 網站正常  
> 🟢 題庫 4,800 / 4,800  
> 🟢 Supabase 正常  
> 🟡 AI：最近 10 分鐘 6 次 timeout  
> 🟢 Service Worker v6

---

### D. 安全狀態

目的不是讓管理者自己分析攻擊，而是讓系統先自動判斷異常。

應監測：
- 429 rate-limit 次數突然增加
- 單一 IP 或 client 大量請求
- AI request 短時間暴增
- feedback spam
- request size 異常
- API 5xx 暴增
- Edge Function error rate 暴增
- 可疑大量照片上傳

管理者只需要看到：

> 🟢 正常流量

或：

> 🔴 可能遭到異常流量攻擊  
> 最近 5 分鐘 AI request 明顯超過平常值。

---

## 3. 緊急保護模式

建議 Admin v1 增加一個簡單的「緊急保護模式」，但必須安全設計，不能讓公開前端直接控制 production。

可考慮的保護開關：
- 暫停 AI 文字批改
- 暫停 AI 照片批改
- 暫停匿名 feedback
- 保留選擇題刷題
- 保留模擬考
- 保留錯題複習
- 保留法規／理論閱讀
- 保留申論題目與本地草稿

使用者端顯示友善訊息，例如：

> AI 批改目前暫時維護，其他學習功能仍可正常使用。

禁止提供「一鍵刪資料庫」「重設 production」「清空資料」等破壞性按鈕。

---

## 4. 網站遭攻擊時的簡化 SOP

### 第一層：自動擋

由現有與未來防護處理：
- IP rate limit
- client rate limit
- CORS / allowed origin
- request size limit
- honeypot / spam protection
- Cloudflare WAF / bot protection（若可用）

### 第二層：告警

管理中心顯示：
- 異常流量
- 429 暴增
- 5xx 暴增
- AI / Supabase 服務異常

### 第三層：降低攻擊面

必要時開啟緊急保護模式，只暫停高成本或容易被濫用的功能，例如 AI / 照片／匿名回報，不影響基本刷題。

### 第四層：重大事件

如果出現 credential 外洩、資料庫異常寫入、網站內容遭竄改：

> 先封鎖／停用受影響功能 → 保留證據與 logs → 查明原因 → 修復 → 驗證後恢復。

不要第一時間亂改 production code。

---

## 5. 外部監測必須獨立存在

不能只做 `/admin` 內部監測。

原因：如果 SWSI 整站掛掉，`/admin` 也會一起掛掉。

因此未來應增加獨立 uptime monitoring：
- 每 1～5 分鐘檢查 production URL
- 網站正常時不通知
- 無法連線或連續失敗時通知管理者
- 恢復時再通知一次

外部監測不需要複雜，只需要回答：

> SWSI 現在是否在線？

---

## 6. 使用統計（需重視隱私）

未來可統計：
- 每日活躍使用者約數
- 每日作答題數
- 每日模擬考數
- 每日申論數
- 每日 AI 文字／照片使用次數
- 主要功能使用比例
- 錯誤率趨勢

原則：
- 不應蒐集不必要的敏感個資。
- 非必要不要儲存原始 IP。
- client identifier 應使用匿名化／雜湊方式。
- 後台顯示以平台營運需要為主，不做使用者監控或追蹤個人行為。

---

## 7. 內容管理（Admin v1 後可擴充）

未來可逐步加入：
- 被多人回報的題目排行
- 題目答案／解析待確認
- 法規可能過期清單
- 理論內容疑問
- MOEX 匯入狀態
- 新年度題庫匯入狀態
- 內容修正歷史

不要一開始就做大型 CMS；先從「看得到問題、能標記狀態」開始。

---

## 8. 目前已有的底層能力

目前 repo 已有多項工程層保護與 QA，可作為 Admin Monitoring 的資料來源或健康依據：
- Runtime Owner QA
- Monthly Frontend QA
- Chromium interaction smoke
- Storage Durability QA
- Knowledge Runtime Snapshot
- Unified Question QA
- MOEX Importer Integrity QA
- Cloudflare Worker smoke/build
- Service Worker update / upgrade smoke
- P0 frontend preflight
- grading contract regression
- question shard SHA / manifest integrity
- Supabase contract smoke
- 使用者回報 `swsi_feedback_reports`

Admin v1 的目標不是取代這些 QA，而是把最重要的結果翻譯成管理者看得懂的狀態。

---

## 9. 建議開發順序

### Phase 1：最小可用 Admin
1. 管理者登入／授權
2. 總覽
3. 使用者回報列表
4. 回報狀態與 reviewer note
5. 基本網站／AI／Supabase 健康狀態

### Phase 2：監測
1. AI 429 / timeout / error 統計
2. 題庫完整性狀態
3. production / SW version
4. 外部 uptime monitoring
5. 異常流量警告

### Phase 3：安全操作
1. 緊急保護模式
2. AI 暫停開關
3. feedback 暫停開關
4. 安全事件記錄

### Phase 4：內容管理
1. 多人回報題目排行
2. 法規／理論待確認
3. 題庫維護流程
4. 新年度資料匯入狀態

---

## 10. 不做的事情

Admin v1 不應：
- 暴露 production secrets
- 把 service-role key 放前端
- 提供任意 SQL console
- 提供任意 GitHub command console
- 提供一鍵刪資料庫
- 提供一鍵 force push / reset main
- 為了後台重構已穩定的 Round 8 runtime
- 把 GitHub Actions 原始 logs 全部丟給非工程管理者

---

## 11. 成功標準

完成後，非工程背景管理者應能在 30 秒內回答：

1. 網站現在正常嗎？
2. 題庫完整嗎？
3. AI 現在正常嗎？
4. 今天有多少人／多少次使用？
5. 有幾件使用者回報需要處理？
6. 是否有異常流量或攻擊跡象？
7. 如果有問題，我現在應該做什麼？

如果仍然需要管理者去 GitHub、Supabase、Netlify 三個後台翻 logs 才能回答，代表 Admin v1 還沒有完成。
