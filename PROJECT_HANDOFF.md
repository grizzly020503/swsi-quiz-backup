# SWSI 社工師國考平台 — 專案交接／續聊清單

## 2026-09-26 時事來源 17-source 正式上線（READ FIRST）

> 本節優先於下方所有 6／8／11／12／13／14／15／16 sources 的歷史敘述。接手仍先重新讀 main、open PR/issues、Actions 與 production sentinel，不把 SHA 當永久最新。

### 已完成

- #125 已合併：加入 **ILO Newsroom** 作為第 17 個來源。
- ILO 使用專用 `ilo_news_html` adapter：
  - 官方 newsroom listing
  - 只保存必要 metadata／來源連結，不複製全文
  - bounded retry
  - 英文來源沿用既有 bilingual taxonomy 與 cross-language event dedupe
  - source / adapter / relevance regression
- #125 exact-head／main 驗證後 accepted topics 只從 10 → 11，沒有因來源量增加而灌水。
- #126 已合併：發布 17-source snapshot，並強制 Cloudflare static assets rebuild。
- #128 已合併；merge commit：`31fb0a3d725bf51985cfec4889357a0e7dc38c73`，production uptime 永久要求至少 **17 sources** 且 **0 feed errors**。
- Public Uptime Sentinel run `36169824564`：**success**。
- production log：
  `primary-home, pwa-sw-v7, questions-4800-24, sources-17/errors-0, news-11, signals-11/4800, events-11, trends-11, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 目前 17 sources

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿
13. 法務部新聞發布
14. UN News English
15. WHO Newsroom
16. UNICEF Press Releases
17. ILO Newsroom

### 最新 main snapshot

- `source_feed_count=17`
- `feed_error_count=0`
- accepted topics=11
- signals=11，questions_loaded=4,800
- events=11、trends=11
- legal-watch=52/52
- ILO 新增的高關聯 accepted topic：
  `ILO project improves social protection coverage for over nine million people`，分類為「社會救助與居住」。

### 現在不要重做

- 不要再把來源現況寫成 16 sources。
- 不要重做 #125／#126／#128。
- 不要為了來源數量放寬 relevance；來源數不是 KPI。
- 不要讓 source_count 單獨提高 trend score；event/trend contract 已鎖定。
- MOEX 不擁有 public current-affairs snapshots；ownership 邊界以 #116 為準。
- 官方 4,800 題、答案、grading 仍維持唯讀。

### Issue #84 接下來仍未完成

1. **社家署**：#103 probe 仍未找到可直接上線的穩定官方 RSS/XML endpoint；不要猜 URL。
2. **Reuters／AP／BBC**：進入「合法／穩定 feed 與 metadata 使用範圍」評估階段。優先挑有清楚官方 feed、可穩定程式化取得、又不需複製全文的來源做 pilot。
3. **trend quality refinement**：累積跨日 evidence 後再調權重；新 false positive 先加 regression 再修。
4. 國際新聞來源仍要先走 bilingual taxonomy → event dedupe → 4,800 題關聯 → trend，再 production；不得繞過既有 fail-closed contract。

---


## 2026-09-26 時事來源 16-source 正式上線（READ FIRST）

> 本節優先於下方所有 6／8／11／12／13／14／15 feeds 的歷史敘述。接手仍先重新讀 main、open PR/issues、Actions 與 production sentinel，不把 SHA 當永久最新。

### 已完成

- #118 已合併：加入 **UNICEF Press Releases** 作為第 16 個來源。
- UNICEF 不是 RSS；目前使用專用 `unicef_press_html` adapter：
  - 抓官方 press-release 頁面
  - 只接受 `/press-releases/` 連結
  - 相對 URL 正規化
  - 英文日期解析
  - bounded retry
  - adapter／retry regression
- #118 exact-head 真實監測：
  - UNICEF entries=12
  - sources=16/16
  - fetched=713
  - accepted=10
  - feed errors=0
  - signals=10 / questions=4,800
  - events=10 / trends=10
  - laws=52/52
- 新增 UNICEF 後 accepted 仍維持 10，沒有因來源增加而灌水；雙語 taxonomy 與跨語言 event dedupe regression 均 PASS。
- #119 已合併：發布 16-source snapshot，並以 `wrangler.jsonc` rebuild marker 強制 Cloudflare static assets 重建。
- #119 Cloudflare Workers production build：**success**。
- 部署完成後重跑 Public Uptime Sentinel attempt 2：**success**，實際 production 已回 `sources-16/errors-0`。
- #122 已合併；merge commit：`4f601ab080cb7356074199fcb54598984f2b119c`，production uptime 永久要求至少 **16 sources** 且 **0 feed errors**。
- #122 main push Public Uptime Sentinel run `36167992640`：**success**。
- production log：
  `primary-home, pwa-sw-v7, questions-4800-24, sources-16/errors-0, news-10, signals-10/4800, events-10, trends-10, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 目前 16 sources

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿
13. 法務部新聞發布
14. UN News English
15. WHO Newsroom
16. UNICEF Press Releases

### 現在不要重做

- 不要再把現況寫成 15 sources。
- 不要重做 #118／#119／#122。
- 不要把 UNICEF Press Releases 當 RSS；目前是專用 HTML adapter。
- 不要因國際來源增加而放寬 relevance 或讓 source count 單獨提高 trend score。
- Cloudflare build success 仍不是唯一 production 證據；正式基線是 Public Uptime Sentinel 的 `sources-16/errors-0`。
- MOEX 不擁有 public current-affairs snapshots；ownership 邊界以 #116 為準。
- 官方 4,800 題、答案、grading 仍維持唯讀。

### Issue #84 下一步

1. **ILO**：下一個國際官方來源。先找官方、穩定、可程式化取得的 RSS／API／頁面 endpoint，逐一做 entries／errors／false-positive pilot；通過後才 production。
2. **社家署**：#103 probe 仍未找到可直接上線的穩定官方 RSS/XML endpoint；不要猜 URL。
3. **Reuters／AP／BBC**：優先級低於官方來源；接入前確認合法／穩定 feed、版權 metadata 範圍與跨來源去重。
4. **trend quality refinement**：累積跨日 evidence 後再校正權重；新 false positive 先加 regression 再修。

---


## 2026-09-26 MOEX／Public Monitoring ownership 衝突已修復（READ FIRST）

> 本節是營運穩定性補充；時事來源數以文件最上方最新的 **16-feed** 章節為準。接手先重新讀 main 與 Actions，不把 SHA 當永久最新。

### 問題根因

- 先前 `MOEX Social Worker Exam Sync` 與 `Public Monitoring Feed` 同時修改／提交 `auto/current_affairs.json`。
- MOEX 本身的官方考題抓取、法規同步、Supabase、4,800 題健康檢查都成功，最後才在 `git rebase origin/main` 與 monitoring bot 的 snapshot commit 發生衝突。
- 這不是官方題庫內容錯誤，也不是 Supabase/grading 故障，而是 workflow 檔案 ownership 重疊。

### #116 已完成

- #116 `fix: separate MOEX and monitoring snapshot ownership` 已合併；merge commit：
  `cf366a0ce56f0e25c0d3746ce374281426ff4189`。
- 新增 `scripts/moex_workflow_ownership_smoke.py`，fail-closed 禁止：
  - `git add incoming/ auto/`
  - MOEX 生成／stage `auto/current_affairs*.json`
  - MOEX stage Public Monitoring 的 CDN current-affairs snapshots。
- MOEX 現在只 stage 自己擁有的：
  - `incoming/`
  - `auto/questions_auto.json`
  - `auto/essays_auto.json`
  - `auto/sync_state.json`
  - `auto/health.json`
  - `data/legal_watch_state.json`
  - `data/legal_watch_report.json`
  - `data/legal_watch_attempt.json`
- MOEX 仍會掃 current affairs 並把候選資料送 Supabase，但只使用 `/tmp/current_affairs_payload.json`；**public current-affairs snapshots exclusively 由 Public Monitoring Feed 產生／提交**。

### 正式驗收

- MOEX Importer Integrity QA（main）：**success**。
- MOEX Social Worker Exam Sync run `36165725787`：**success**。
- 該 run 實際證據：
  - `MOEX WORKFLOW OWNERSHIP OK`
  - official 115030／115100 內容未變
  - local health OK
  - remote Supabase：questions=4,800、essays=10
  - grading modes：all_credit=12 / any_answer=4 / standard=4,784
  - 最後 `Commit verified official payloads and owned state`：**success**
  - bot commit：`be9e42f556b1abfeadbe6d4b2c0dd8054aa011ab`
  - push main：**success，無 current_affairs rebase conflict**
- 後續 Public Monitoring Feed run `36166135020`：**success**：
  - sources=15/15
  - fetched=701、accepted=10、errors=0
  - events=10 / trends=10
  - laws=52/52
  - questions=4,800
  - snapshot push main 成功。

### 現在不要重做

- 不要讓 MOEX 再生成／提交 public `auto/current_affairs*.json`。
- 不要改回 broad `git add incoming/ auto/`。
- 不要用 conflict resolver 掩蓋 ownership；現在已有明確 owner 與 regression。
- 官方題目、答案與 grading 語意未因本修補變更。

---


## 2026-09-26 時事來源 15-feed 正式上線（READ FIRST）

> 本節優先於下方所有 6／8／11／12／13／14 feeds 歷史敘述。接手仍先重新讀遠端 main、open PR/issues、Actions 與 production sentinel；不要把本節 SHA 當永久最新。

### 正式狀態

- #112 已合併：加入 **WHO Newsroom**，使用獨立 JSON adapter，不把 WHO API 硬塞進 RSS parser。
- #112 仍沿用 #104 的中英雙語 taxonomy 與跨語言 event dedupe；英文來源先做社工考點分類，再參與事件聚類。
- WHO pilot 已加入 retry／adapter regression 與 public monitoring contract。
- #113 已合併：將 verified 15-source snapshot 發布到 Cloudflare production asset root。
- #113 Cloudflare Workers production build：**success**。
- #114 已合併；merge commit：`d44b73a5ce14186a8a8fc274e0d391b0305c549a`，production uptime 永久要求至少 **15 feeds** 且 **0 feed errors**。
- main push Public Uptime Sentinel run `36164946253`：**success**。
- production log：
  `primary-home, pwa-sw-v7, questions-4800-24, sources-15/errors-0, news-10, signals-10/4800, events-10, trends-10, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 目前 15 feeds

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿
13. 法務部新聞發布
14. UN News English
15. WHO Newsroom

### 最新驗證基線

- main snapshot：**15 feeds / 0 errors / 10 topics**。
- signals=10，questions_loaded=4,800。
- events=10、trends=10。
- legal-watch=52/52。
- WHO 目前貢獻 1 個高關聯事件：
  `From competencies to action: strengthening refugee and migrant health`，分類為「移工與新住民」。
- 新增 WHO 後沒有用來源數灌高 accepted/trend；production 仍只保留 10 個高關聯議題。

### 現在不要重做

- 不要再把來源現況寫成 14 feeds。
- 不要重做 #104／#107／#109／#110／#112／#113／#114。
- 不要把 WHO Newsroom 當 RSS；目前使用專用 JSON adapter。
- 不要因國際來源文章量增加而放寬 relevance 或用 source count 單獨提高 trend score。
- Cloudflare build success 不是唯一上線證據；仍以 Public Uptime Sentinel 的 `sources-15/errors-0` 為正式 production 證據。
- 官方 4,800 題、答案與 grading 繼續維持唯讀。

### Issue #84 接下來

1. **國際官方下一批**：UNICEF／ILO。逐一找官方、穩定、可程式化取得的 RSS／API；每個來源先做 entries／錯誤／false positive pilot，再進 production。
2. **社家署**：#103 probe 未找到穩定可上線的官方 RSS/XML endpoint；仍然不要猜 URL。
3. **國際新聞媒體**：Reuters／AP／BBC 仍屬後續，優先級低於官方來源；接入前要確認合法／穩定 feed、版權 metadata 範圍與跨來源去重。
4. **trend quality refinement**：等跨日 evidence 累積後再校正權重；任何新 false positive 先加 regression 再修。

---


## 2026-09-26 時事來源 14-feed 正式上線（READ FIRST）

> 本節優先於下方所有 6／8／11／12／13 feeds 歷史敘述。接手仍先重新讀遠端 main、open PR/issues、Actions 與 production sentinel；不要把本節 SHA 當永久最新。

### 正式狀態

- #104 已合併：建立 **中英雙語 current-affairs taxonomy** 與 **跨語言 event dedupe**；英文來源不再只是塞進中文 keyword scanner。
- #107 已合併：加入 **UN News English** 官方 RSS：
  `https://news.un.org/feed/subscribe/en/news/all/rss.xml`
- #107 exact-head 真實監測：
  - UN News English entries=30
  - 14/14 sources
  - fetched=601
  - accepted=9
  - feed errors=0
  - questions=4,800
  - events=9 / trends=9
  - bilingual source regression PASS
  - cross-language event dedupe regression PASS
- #109 已合併：發布 14-source snapshot 到 Cloudflare production。
- Cloudflare Workers Build（#109 head）已 **success**。
- #110 已合併；merge commit：`b3775b11b27262be1aca9011b33b2fba906f0143`，production uptime 永久要求至少 **14 feeds** 且 **0 feed errors**。
- #110 production verification attempt 3：**success**。
- main push Public Uptime Sentinel run `36163347909`：**success**。
- production log：
  `primary-home, pwa-sw-v7, questions-4800-24, sources-14/errors-0, news-9, signals-9/4800, events-9, trends-9, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 目前 14 feeds

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿
13. 法務部新聞發布
14. UN News English

### 重要品質結論

- 新增 UN News 30 entries 後，accepted 仍維持 9，**沒有因來源擴充而灌水**。
- 跨語言事件必須有獨立 anchor 才能合併；相似度不足時仍 fail-closed。
- source count 不能單獨提高 trend score。
- 4,800 題官方題庫、答案、grading 仍維持唯讀。

### Issue #84 接下來

1. **國際官方第二批**：WHO／UNICEF／ILO。沿用 #104 雙語 taxonomy + cross-language dedupe，逐一做真實 feed pilot；每一個來源都要先驗 entries、feed errors、false positives，再進 production。
2. **社家署**：#103 probe 未得到可直接上線的穩定官方 RSS/XML endpoint；不要猜 URL。
3. **國際新聞媒體**：Reuters／AP／BBC 等仍屬後續；優先級低於官方來源，而且需處理授權／feed 穩定性與同事件去重。
4. **trend quality refinement**：等跨日 evidence 累積後再調權重；任何新 false positive 先加 regression 再修。

### 現在不要重做

- 不要再把來源現況寫成 13 feeds。
- 不要重做 #104／#107／#109／#110。
- 不要因國際 feed 文章量增加就提高 accepted 數或 trend 分數。
- 不要把「Cloudflare build success」單獨當 production 上線；仍以 Public Uptime Sentinel 的 `sources-14/errors-0` 為正式證據。

---


## 2026-09-26 時事來源 13-feed 正式上線（READ FIRST）

> 本節優先於下方所有 6／8／11／12 feeds 歷史敘述。接手時仍先重新讀遠端 main、open PR/issues、Actions 與 production sentinel。

### 正式狀態

- #97 已合併；merge commit：`f949e3e23494eff4a49ff63c5835e3c70de77761`：
  - 新增 **法務部新聞發布 RSS** `https://www.moj.gov.tw/2204/2795/2796/rss`。
  - 新增「**司法保護與修復式司法**」分類與 exam-signal／歷屆題 mapping。
  - 新增 `犯罪被害人權益保障法` 法規抽取。
  - RSS 相對連結使用 `urljoin` 正規化。
  - 外部 feed 瞬斷最多重試 3 次；最終 public contract 仍要求 `feed_error_count=0`。
  - 依真實資料排除揭牌、聯展、音樂會、媒體澄清等法務部 activity/press noise。
- monitoring bot 13-source snapshot commit：`ecde4df3042542379383884b452352cc24fff000`。
- #98／#100 已完成 Cloudflare 13-source 靜態資產發布與強制 rebuild。
- #101 已合併；merge commit：`09ccdab35d4ae8ad6871f397cf89add99ad85a8b`，production uptime 永久要求至少 **13 feeds** 且 **0 feed errors**。

### 目前 13 feeds

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿
13. 法務部新聞發布

### 最新 production 基線

- 法務部 RSS：**264 entries**。
- 13/13 sources。
- fetched=571，accepted=9，feed errors=0。
- signals=9，questions_loaded=4,800。
- events=9、trends=9。
- legal-watch=52/52。
- Production Uptime Sentinel run `36159777534`：**success**。
- production log：
  `primary-home, pwa-sw-v7, questions-4800-24, sources-13/errors-0, news-9, signals-9/4800, events-9, trends-9, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 現在不要重做

- 不要再把來源現況寫成 6／8／11／12 feeds。
- 不要重做 #90／#92／#93／#94／#97／#98／#100／#101。
- 不要因單一大型 feed（如法務部 264 entries）就提高 accepted 數；目前正式結果仍是 9 個高關聯議題。
- 不要放寬 `feed_error_count=0`；瞬斷用 bounded retry，最終失敗仍應紅燈。
- 官方 4,800 題、答案與 grading 維持唯讀。

### Issue #84 接下來

1. **社家署**：先找到並驗證官方穩定 RSS/XML/公開資料 endpoint，找不到就不猜 URL。
2. **國際官方／新聞**：UN、WHO、UNICEF、ILO、Reuters、AP、BBC 等；先建立英文→中文社工考點分類與跨語言事件去重，再接 production。
3. **trend quality refinement**：持續累積跨日 evidence 後調權重；來源數不能單獨決定趨勢。
4. 任何新 false positive 先加 regression 再修。

---


## 2026-09-25 時事來源 12-feed 正式上線（READ FIRST）

> 本節優先於下方所有「6 feeds／8 feeds／11 feeds」的歷史敘述。接手時仍先重新讀遠端 main、open PR/issues、Actions 與 production sentinel。

### 正式狀態

- #90 已合併：加入 **教育部即時新聞、教育部重要政策、移民署新住民政策法規**，並新增每個 feed 的健康 log、12 秒 network timeout、公開 snapshot 的 `source_feed_count`／`feed_error_count`。
- #92 已合併：來源 registry、scanner、event/trend/analyzer 等 pipeline 變更進 main 後，會立即重建 public monitoring snapshots，不必等下一個 6 小時排程。
- #93 已合併；merge commit：`2a59a38b4d7765e3901b63cf5fefbd2ef5fb18b4`：
  - 新增 **勞動部新聞稿 RSS**。
  - 新增「**勞動與社會保障**」「**教育與學生輔導**」考點分類與 exam-signal／歷屆題 mapping。
  - 依真實 production data 收緊 relevance：排除書展／文化幣、醫療衛教、科普論壇、頒獎典禮、模擬投票、成果活動、接見訪問團、評選、補助詐領刑案、防災演練、公益課桌椅等 false positives。
  - 保留兒少／身障需求調查、最低工資、勞保、托育政策、長照補助等制度型訊號。
- monitoring bot 正式 snapshot commit：`ba2282e542bb1c1005ea4f48b3ad3f5557f00499`。
- #94 已合併；merge commit：`4276b1f4bd3c7ae138d61e30fc2b716f048355ad`，用最小 release patch 將 12-source snapshot 推到 Cloudflare production，並將 source health 加入 public uptime contract。

### 目前 12 feeds

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿

### 最新驗證基線

- #93 exact-head 真實掃描：**12/12 Feed OK，fetched=307，accepted=9，feed errors=0**。
- signals=9，questions_loaded=4,800。
- events=9、trends=9。
- legal-watch=52/52。
- Production Uptime Sentinel run `36151156958`：**success**。
- production log：
  `primary-home, pwa-sw-v7, questions-4800-24, sources-12/errors-0, news-9, signals-9/4800, events-9, trends-9, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 現在不要重做

- 不要再把來源現況寫成 6、8 或 11 feeds。
- 不要重做 #90／#92／#93／#94。
- 不要為了新聞數量放寬 relevance；目前策略是 **品質優先、false positive regression 優先**。
- 不要讓同一事件跨來源報導灌高趨勢分數；event clustering 與 trend contract 已存在。
- 官方 4,800 題、答案與 grading 仍為唯讀邊界。

### Issue #84 接下來仍未完成

1. **台灣官方第二批**：法務部、社家署等來源，先找到並驗證穩定 RSS／公開資料 endpoint，再接入；不得猜 URL。
2. **國際官方／新聞**：UN、WHO、UNICEF、ILO、Reuters、AP、BBC 等。英文來源要先建立英文→中文社工考點分類與跨語言事件去重，不能直接丟進目前中文 keyword scanner。
3. **trend quality refinement**：累積跨日 evidence 後再校正權重，避免靠來源數或短期新聞量製造假趨勢。
4. 依 production feedback 再調 relevance；新 false positive 必須先加 regression 再修。

---


## 2026-09-25 時事命題分析鏈 V2 已正式上線（READ FIRST）

> 本節優先於下方舊的「6 feeds／V1 時事區／尚未發布」敘述。接手仍先讀遠端 main、open PR/issues、Actions 與公開監測，不把 SHA 當永久最新。

### 已完成

- Issue #84 V2 第一階段資料鏈已完成：**來源 registry → event clustering → canonical event → 4,800 題歷屆題關聯 → trend snapshot**。
- #85 已合併：新增 `current_affairs_events.json`、`current_affairs_trends.json`、事件 identity／證據日期持續性、趨勢分級與 regression。
- 目前來源 registry 為 **8 feeds**：
  - 衛福部焦點新聞
  - 衛福部公告訊息
  - 中央社社會／生活／政治／國際
  - 內政部新聞發布
  - 行政院本院新聞
- main 真實監測曾抓取 **190 則、接受 7 則、feed errors 0**；events=7、trends=7、signals=7、歷屆題來源=4,800。
- #86 已合併：production uptime 驗證 events/trends contract。
- #87 已合併：學生端單一時事入口升級成 **命題趨勢雷達**，顯示升溫／持續／降溫／單次觀察、trend score、來源數、官方來源、why、申論方向、MCQ focus、歷屆題、多來源 evidence；V2 失敗時保留 V1 fallback。
- #88 已合併並正式發布 Cloudflare production；merge commit：`54b073f4ac115a6fd01f0878b112afb1be53f588`。
- #88 首次 uptime 比 Cloudflare deployment 早約 50 秒而失敗；**Cloudflare Workers Build 完成 success 後重跑 attempt 2 成功**。
- production sentinel 最終 log：
  `primary-home, pwa-sw-v7, questions-4800-24, news-7, signals-7/4800, events-7, trends-7, trend-ui-v2, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。

### 現在不要重做

- 不要再做第二個時事 portal。
- 不要再把 V1 單篇 signal 當目前最高層資料模型；V1 只保留 fallback。
- 不要把同一事件的多家報導直接當成多倍熱度。
- 不要重做 #85～#88 的 event/trend/UI/release closeout。
- 官方 4,800 題、答案、grading 仍是唯讀邊界。

### Issue #84 尚未完成的部分

1. **來源擴充**：台灣官方再加入勞動部、教育部、法務部、社家署、移民署等高相關來源。
2. **國際來源**：UN／WHO／UNICEF／ILO 與 Reuters／AP／BBC 等；接入前需處理英文內容與中文考點分類，不能只把英文 RSS 塞進目前中文 keyword scanner。
3. **trend quality refinement**：累積更多跨日 evidence 後再調權重，不以來源數當 KPI。
4. 學生 UI 已上線，後續只依真實 feedback 與監測結果迭代。

### Netlify

- Netlify 仍是 fallback，與本次 Cloudflare V2 release 分開。
- 已有驗證過的 v7 manual deploy artifact，但目前聊天沒有 Netlify 帳號寫入連接器；不要把「artifact 已產生」誤稱「Netlify production 已更新」。

---


## 2026-09-25 Cloudflare 正式發布完成（READ FIRST）

> 本節是目前最高優先級的接手基線；下方 2026-09-25「接手與時事功能收尾」保留為歷史稽核紀錄，當中的「尚未 merge／尚未發布／signal 403／cdn SW v6」已被本節取代。
> 每次接手仍先重新核對遠端 main、open PR/issues、Actions 與公開監測，不把任何 SHA 當永久最新。

### 已完成的正式發布閉環

- #77 `fix: finish current-affairs signals and monthly preview closeout` 已合併；merge commit：`6789c5c502efeec5bcd61277de9da4aaf435bb7b`。
- #77 合併後 8 類 main QA 全部 PASS：Public Monitoring Feed、Cloudflare Frontend Preview、Monthly Frontend、Launch Readiness、Storage、Knowledge、Official Exam Read-Only、Essay Audit。
- #78 `release: publish verified current-affairs UI to Cloudflare` 已合併；merge commit：`19a8100bbae6d78530af0c7770826e157ef4e2e3`。
- #78 只發布 `cdn/index.html` 與 `cdn/sw.js`；Cloudflare production build 成功，Version ID：`12b5178f-ca38-415e-8448-6c900c26fac3`。
- 正式 `cdn/sw.js` 已是 **v7**；正式首頁包含 signal loader、命題訊號／申論方向／選擇題焦點／歷屆相關題 UI。
- #79 `ops: close production uptime blind spots` 已合併；merge commit：`eabfdc3bff49bbbc049a6d432261561aa11500b0`。
- #79 將 uptime sentinel 補成會實際驗證 SW v7 與 `current_affairs_signals.json`，並在 sentinel 自身變更進 main 後自動跑 production monitoring-v2。
- production Uptime Sentinel run `36141787784`：**success**。實際 log：
  `primary-home, pwa-sw-v7, questions-4800-24, news-6, signals-6/4800, laws-52/52, question-health, ai-preflight, feedback-preflight, netlify-fallback`。
- 本次收尾時 open PR = 0、open issue = 0。

### 現在的營運判斷

- **Cloudflare primary 已完成本輪正式發布與線上驗收。**
- 官方選擇題仍為 4,800 題／24 shards；本輪沒有修改官方題幹、答案、grading、Supabase schema、Edge Functions 或 secrets。
- 時事命題訊號目前公開快照為 6 items，分析來源為完整 4,800 題 shards；文案持續明示「不代表命題保證」。
- scanner 目前仍只有 6 feeds：衛福部焦點新聞／公告、中央社社會／生活／政治／國際。Reuters、AP、BBC、CNN、UN、WHO 與其他部會屬後續來源擴充，不是目前 release blocker。
- Netlify 仍是 fallback；2026-09-25 已知 `/sw.js` 為 v2。這不影響 Cloudflare primary 本輪驗收，**不要未經明確授權自行重部署 Netlify**。

### 下一步

1. 若沒有新的監測紅燈或使用者回報，停止 release cleanup；不要再重做 #74～#79。
2. 後續優先依真實 feedback、官方資料更新、監測異常處理；有 bug 先重現、加 regression、PR exact-head、merge、production smoke。
3. 若要擴充時事來源，先維持來源品質、事件去重與命題相關性，不為了增加新聞數量而灌低價值 feed。
4. Netlify fallback 升級另列獨立 release，需先確認部署額度與使用者授權。
5. 8 月 Round 8、舊 v6／舊月底 patch 指令皆屬歷史，不得據此回退架構。

---


## 2026-09-25 接手與時事功能收尾（READ FIRST）

> 本節取代下方歷史「下一步」；仍須重新核對遠端 main、PR、Actions 與公開資產。
> **程式合併、產生資料、公開發布是三種不同證據，不可混稱「已上線」。**

### 實際接手基線

- main：`cd422d8e9a193fe286111c1b6622b7eaf636dc6d`（2026-09-25 monitoring bot）；這是本次查核時間點，非永久 HEAD。
- 接手時 open PR / issue 均為 0。
- #74 時事命題訊號需求已關閉；#75 已於 2026-09-22 合併分析器、公開快照 builder 與 UI installer。
- #76 月底學生端 patch 已於 2026-09-22 合併：`0be1a49b4943e93c25b0dd2416c14b15924bb214`。不要重做 CDN loader／grading／安全修補。
- #76 main 上 Monthly Frontend、Launch Readiness、Storage、Knowledge、Essay Audit 均成功；Cloudflare Frontend Preview run `35744397393` 失敗，尚未被成功 run 取代。
- 本次修復 branch：`fix/monitoring-preview-closeout-20260925`，從上述最新 main 建立；本節所在修正 commit 為本階段 checkpoint，接手時查遠端 branch HEAD。
- 8 月 Round 8 分支已屬歷史，勿因 AGENTS.md／RELEASE.md 的舊分支段落而回到 stale branch。

### 真正發現的遺漏與本次修復

1. **命題訊號未發布**：Public Monitoring Feed 已產生／驗證 `auto/current_affairs_signals.json`，但 `git add` 漏列 source 與 `cdn/auto/` 兩份。main tree 沒有這兩個檔；公開 signal URL 實測 HTTP 403。補齊發布清單，加入暫存 git repo 的 staging regression，確保新檔會發布且不夾帶 index／私人檔。
2. **學生端仍是舊時事區**：root `index.html` 和已提交的 `cdn/index.html` 都沒有 signal loader。installer 一看到 V1 marker 就提早 return，未把 #75 的新內容套到既有區塊。改成精準替換單一既有 script，並將新區塊套回 root source；保留單一時事入口。
3. **Cloudflare preview 錯誤檢查舊 v6**：source `sw.js` 已為 v7，workflow 的 isolated-preview step 卻仍 grep v6，導致發布前退出。改成比對 preview 與 source 實際 bytes；原 P0 preflight／Service Worker contract 仍保留。

### 驗證與範圍

- 三項問題皆已用原始 main 檔案重現後修正。
- 本地：Python／Node syntax、Monitoring V2 contract、Service Worker update smoke、`git diff --check` 通過。
- 發布 regression：漏 source signal、漏 CDN signal、寬泛 `git add .` 均會被拒絕。
- Preview 比對：正確 v7 通過，錯置 v6 被拒絕。
- 新 UI smoke：命題訊號／申論方向／選擇題焦點／歷屆題顯示、signal feed 失敗回退、news 失敗保留原頁、科目篩選與動態字串 escape 均通過。
- Installer 重複執行不改檔，並拒絕重複 marker 或缺失 script 邊界。
- 遠端 exact-head CI 狀態請讀本 branch／PR 的最新 checks；本段本地結果不可冒充遠端 PASS。
- 官方題幹／答案／grading、38 runtime parts、Supabase schema、Edge Functions、secrets 均未修改；未 merge main、未部署正式站。

### 時事來源現況

實際 scanner 只有 6 feeds：衛福部焦點新聞／公告，以及中央社社會／生活／政治／國際。
Reuters、AP、BBC、CNN、UN、WHO 與其他部會仍是 #74 記錄的後續方向，**尚未實作接入**。
最新監測 run `36131125478`：fetched 120、accepted 6、feed errors 0；signal analyzer 對應 4,800 題。不要因 workflow 保留救援 CSV fallback 參數而誤稱目前只分析 4,600 題；builder 實際優先讀現存 shards。

### 正式站／剩餘 blocker

- Cloudflare 是目前 primary；Netlify 是 fallback（以 `scripts/public_uptime_smoke.py` 為準）。
- Cloudflare home 與時事 source feed 實測 HTTP 200；signal feed 實測 HTTP 403。最新 Uptime Sentinel run `36096474754` 成功，但既有 sentinel 尚未驗 signal feed，不能據此聲稱訊號發布成功。
- 2026-09-25 Netlify `/sw.js`（含 no-cache／cache-busting 查核）仍為 **v2**；main source 為 v7。#76 的 merge 不代表 Netlify 已更新。
- main 的 `cdn/sw.js` 仍為 v6、`cdn/index.html` 仍為舊時事區；正式 root frontend 尚需用目前已驗收 source 重建與驗證。
- 本次修正完成後仍須本人批准 main merge／正式發布；不得自動重部署 Netlify 或宣稱 UI 已上線。
- 沒有本輪已確認的新 grading／官方資料 P0；剩餘已確認 blocker 是發布尚未完成、遠端修正 gates 與最終正式驗證。

### 接續順序

1. 核對本修復 PR exact-head 的 Public Monitoring Feed、Cloudflare Preview、Monthly Frontend、Launch Readiness、Storage、Knowledge 等實際觸發 gates；失敗先讀 log。
2. 檢查 diff／secrets，取得 main merge／正式 Cloudflare 發布授權；未獲授權保持修復 branch。
3. Merge 後驗監測 workflow 真正提交兩份 signal JSON、Cloudflare signal URL HTTP 200、schema／題數／非命題保證文案正確。
4. 依既有 release 流程從最新 source 重建正式 Cloudflare frontend，驗證學生端時事區顯示新資料與 feed 缺失回退；preview 成功不能代替 root production smoke。
5. Netlify fallback 是否升級與部署額度另行確認，避免重複部署。
6. 更新此節及 KNOWN_ISSUES 的正式驗收證據後，才處理來源擴充；不為了新聞數量添加低相關來源。

Merge 建議：待本修復 PR exact-head gates 通過並取得明確授權後可合併；不可把本段當作授權。

---

## 2026-09-06 最新營運狀態（READ FIRST）

> **本節是目前最高優先級的接手基線。** 下方 2026-08-27 Round 8 與其他歷史章節保留作稽核紀錄；若 SHA、part 數量、branch、部署狀態或「下一步」與本節衝突，以本節與遠端真實狀態為準。每次接手仍必須先重新讀 `main`、Actions、open PR/issues，不可把任何 SHA 當永久最新。

### 最新基線

- 本 handoff refresh 建於 `main@5ce724fcba9bf9204e2f8c8889ef9cd01d9921c9`；合併本 docs-only handoff 後 `main` 會再前進，接手時務必重新讀遠端 HEAD。
- canonical runtime source：`monthly_patch_parts/*.part`，目前維持 **38 parts 上限**；generated runtime 為 `cdn/monthly_patch.js`。
- 官方選擇題庫仍為 **4,800 題**；官方 shard wording / answer / grading source 不因前端顯示修正而改寫。
- 學生端核心：做題 → 解析 → 錯題／複習 → 弱點 → 申論 → AI 回饋；核心刷題不依賴 AI 額度才能運作。
- Netlify production 本輪沒有被修改；除非使用者明確要求，仍不要把 Netlify 當作這輪的變更目標。

### 2026-09-06 已完成且不要重做

1. **承上題／承前題 standalone context 修復**
   - #57 修復「承上題」類官方題目被單獨抽出時失去前題情境的問題。
   - 官方 shard 保持唯讀；只做 presentation-only context adapter。
   - 初版新增第 39 個 runtime part，main 的 Runtime Owner QA 正確抓到結構回歸。
   - #58 把 adapter 折回既有 `code_health_p0` late `renderQuiz` owner，runtime 回到 38 parts；Dependent Question Context QA 與 Runtime Owner QA 均通過。

2. **Feedback modal accessibility race 修復**
   - #58 同時修掉 feedback modal `setTimeout(...focus(), 30)` 對 Shift+Tab focus trap 的搶焦點 race。
   - 改成 dialog 插入後立即 initial focus；Launch Readiness Chromium/WebKit/mobile/accessibility smoke 已通過。

3. **Monitoring V2 正式上線**
   - 舊 #56 因 #57/#58 後 main 漂移而關閉、不合併。
   - #59 從 post-bugfix main 乾淨 refresh，generated runtime 由最新 38 canonical parts 重建，不複製 stale runtime。
   - Five-radar：時事、法規、題庫、系統、feedback 公開監測；Public Uptime、Knowledge Snapshot、Storage、Usage Analytics、Monthly Frontend、Launch Readiness 等 exact-head gates 通過。
   - #59 merge commit：`e502ddf5fff0b6cec9a1e6526eb6f919c6c56235`（歷史證據；不是永久最新 HEAD）。

4. **MOEX／MOJ 真實同步已驗證**
   - 2026-09-06 正式同步完整通過：時事掃描、MOJ 法規檢查、官方考題 fetch、local question-bank health、Supabase changed-only import、Supabase health、verified payload commit。
   - bot commit `1b6b99eda95d68b7eb589e19c8e9924028bb4abe` 只更新 legal-watch internal state/report，沒有覆蓋 runtime。
   - 真實偵測到 **民法** official modified date `2021-01-20 → 2026-08-17`，52/52 laws matched，`changed_count=1`。

5. **Public legal-watch 即時發布閉環**
   - 上線後發現 internal `data/legal_watch_report.json` 已抓到民法變更，但 public `auto/legal_watch.json` 尚停在舊 snapshot。
   - 根因：Public Monitoring Feed 原本只有 schedule / PR trigger，MOEX bot 更新 main 後不會立即刷新 public legal snapshot。
   - #60 增加 main-only `push` trigger，僅監聽 workflow 本身與 `data/legal_watch_report.json`；**不監聽 `auto/legal_watch.json`**，避免 monitoring bot 自觸發 loop。
   - 第一版 regression 因註解字串造成 false positive；已修為只解析 YAML list entries，不放寬功能條件。
   - production run 真實產生：`Public legal-watch snapshot updated: 52/52 matched, changed=1`，publish step success。
   - monitoring bot commit `79cf778a36914d9751f7b4bbcf767e6441f3d491` 已把 `auto/legal_watch.json` 與 `cdn/auto/legal_watch.json` 對齊，內容含：`民法`、`changed=true`、`2021-01-20 → 2026-08-17`。
   - 該 snapshot commit 沒有再觸發 Public Monitoring Feed，證明無 self-loop；Cloudflare Workers build 亦 success。

6. **Runtime Owner gate 前移到 PR**
   - #57 暴露治理缺口：Runtime Owner QA 原本只有 `push`，第 39 part / extra owner 要到 merge main 後才第一次被抓到。
   - #61 只修改 `.github/workflows/runtime-owner-qa.yml`，加入與 push 相同 paths 的 `pull_request` trigger。
   - #61 exact PR HEAD 已實際觸發並通過：maintainability structure、runtime owner chain、late owner chains、essay metadata enhancer。
   - #61 merge 後 main `push` Runtime Owner QA 也再次完整 PASS。
   - 往後凡修改 `monthly_patch_parts/**`、structure config 或 owner smoke，應在 **PR 合併前** 就被 Runtime Owner QA 阻擋結構回歸。

### 目前營運判斷

- 2026-09-06 本輪收尾時：**沒有 open PR、沒有 open issue、沒有 queued / in-progress main workflow**。
- main 最近真正紅燈皆是已被後續修復 supersede 的歷史 run；不要因 Actions history 還留著 failure 記錄就重開已結案問題。
- Monitoring V2 已經歷一次真實法規變更事件，從 MOJ detection → internal report → public snapshot → Cloudflare build 的鏈路已閉環。
- Runtime layering 維持 38 parts，且現在 PR / main 都有 Runtime Owner gate。
- 不要再做沒有明確收益的 owner-count cleanup、cosmetic refactor 或「為了變綠而放寬 guardrail」。

### 真正的下一步

1. **先讀遠端真實狀態**：`main` HEAD、最新 Actions、open PR/issues、最新 Monitoring snapshots。
2. 若沒有新紅燈／使用者回報，**不要憑空製造 cleanup 任務**；等待真實 feedback、監測異常、官方資料更新或明確產品需求。
3. 若有學生端 bug：先重現 → 找 canonical owner → 加 regression → exact-head PR gates → merge → main post-merge → production/public artifact 驗證。
4. 若有官方題庫／法規更新：保持 official source-of-truth 與 fail-closed；不要用 AI 猜答案或把 presentation workaround 寫回官方資料。
5. Netlify production 仍需使用者明確授權才改；目前 Cloudflare 路徑的 production-facing evidence 已驗證。

---

## 2026-08-27 Round 8 code-health 最新接續狀態（本節優先）

> 本節晚於下方歷史內容；若衝突，以本節與 `PROJECT_HANDOFF_ROUND8_DELTA.md` 為準。

- branch：`fix/code-health-p0-20260826`
- 已驗證的 runtime code HEAD：`08279ab72659c5ba06f09cf77de5402a5d30146a`
- handoff closeout：包含本節的 commit 即目前 branch HEAD；接手時仍須先重新讀遠端 ref，禁止假設這個 SHA 永遠是最新。
- compare snapshot（`08279ab7`）：`main@0712b258`，branch ahead 136 / behind 0。
- 未 merge main、未 force push、未部署 Netlify production、未修改 production secrets、未做不可逆 production 操作。

### 已完成 ownership consolidation

- `renderHome` 收斂至 `20.product-philosophy.part` canonical owner。
- `normalize` 與 grading helpers 收斂至 `00.part`。
- mock answer record policy 移回 MK subsystem。
- AI feedback text/photo owner 收斂至 `99z.essay-trust-layer.part`。
- AI stable client ID / timeout utility 收斂至 `99_p0_mobile_ai_guardrails.part`。
- `85.escape-helper.part` 已刪除，escape helper 私有化至 `86.law-trust-ui.part`。
- `87.new-resident-law-status-ui.part` 已合併至 `86.law-trust-ui.part`。
- obsolete AI copy / final runtime / stable client shims 已移除。
- essay metadata labels 已改為 idempotent MutationObserver enhancer，不再接管 global `render()`。
- essay navigation 已於 `47dfca19` 收斂至 `zzz_fix_essay_navigation.part`：保留 slow/cache reload、tab state、state reset 與 render retry；`50.home-spacing-essay-entry.part` 與 `zzzz_product_v1_lock.part` 不再覆寫 `swsiOpenEssay`。
- Runtime Owner QA 已鎖住上述 ownership 與保留的 fail-closed edge guards。
- `08279ab7` 修正 Runtime Owner QA 對 async `swsiStartEssayNow` 的假陰性；現已正確鎖定唯一 deliberate owner `zzzzz_quick_essay_scope_fix.part`，未修改產品 runtime。

### 明確保留的 deliberate owners

- `70.learning-loop.part` 的 `renderReview`。
- `91.feedback-context.part`。
- `zzz_fix_essay_navigation.part`。
- `zzzzz_quick_essay_scope_fix.part`。
- `zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part` 的 invalid `acceptedAnswers()` 與 invalid-question `renderQuiz()` fail-closed guards。
- `99_p0_mobile_ai_guardrails.part` 的 mobile / draft / timeout / cache / busy utilities。
- `99z.essay-trust-layer.part` 的 AI trust/privacy/error boundary。
- `86.law-trust-ui.part` 與 `88.theory-trust-ui.part` 的 law/theory trust presentation wrappers：它們有獨立產品責任，不為降低 owner 數量而拆除。

### 最新 regression

`34c22f3` essay metadata enhancer：
- Runtime Owner QA #19：success
- Cloudflare Frontend Preview #113：success
- Monthly Frontend QA #134：success；`interaction-qa` 真正安裝並執行 Playwright Chromium
- Storage Durability QA #44：success
- Knowledge Runtime Snapshot QA #36：success

`47dfca19` essay navigation consolidation：
- Runtime Owner QA #22：success
- Cloudflare Frontend Preview #114：success
- Monthly Frontend QA #135：success；static + Chromium interaction 全綠
- Storage Durability QA #45：success
- Knowledge Runtime Snapshot QA #37：success
- Cloudflare Workers Builds：success
- P0 preflight、Service Worker / Worker / Supabase contracts、question shard integrity、knowledge catalog、production-shaped static smoke 均由 Monthly static job驗證成功。

`08279ab7` async quick-essay owner matcher：
- Runtime Owner QA run `33057724634`：success。
- log：`RUNTIME OWNER SMOKE OK`；`swsiStartEssayNow: zzzzz_quick_essay_scope_fix.part`。
- Cloudflare Workers Build：success。
- 本批僅修改 QA matcher/smoke，未改產品 runtime，因此未重跑與行為無關的完整 Chromium/Storage/Knowledge 套件。

### 安全與收尾

- `main...branch` 78 個 changed files；先前 64 個仍存在的 changed 文字檔已做高信心 secret scan。
- 未發現 private key、GitHub/OpenAI/AWS token、JWT 或 production service-role literal。
- 唯一字串命中是 `scripts/cloudflare_worker_smoke.js` 的明確測試 fixture：`internal-secret` / `groq-secret`。
- `build-netlify-package.yml` 與 `verify-netlify-production.yml` 為手動 workflow；package job 只允許 `refs/heads/main`。
- Cloudflare preview publish/wait 只允許 `refs/heads/main`；本 branch 僅 build 驗證。
- 目前仍有 5 個本輪暫存 refs：`tmp-ai-client-owner-20260827-v2`、`tmp-ai-client-owner-20260827`、`tmp-law-status-consolidation-20260827-v2`、`tmp-law-status-consolidation-20260827`、`tmp-swsi-context-owner-20260827`。目前可用 GitHub 連接器未提供 delete-ref；不可用 force/move-ref 代替刪除。取得 delete-ref 權限後可安全移除，這不影響 runtime 或 merge correctness。

### Round 8 Final Audit（2026-08-27）

- audit 起點：`ee77d53c87820a9ece85a6249c57c3749cbce7ec`。
- P1 漏測：Runtime Owner QA 尚未鎖住 full-bank loaders、knowledge/progress owners、mobile draft、versioned AI cache key、feedback context 與 law/theory trust 的精確 chain。
- 修正：`2ebb0a7c81a9a59d1cc57e133c2ca869f73ac5aa`，只擴充 `scripts/runtime_owner_smoke.js`，未修改任何 runtime `.part`。
- Runtime Owner QA run `33059736623`：success，`RUNTIME OWNER SMOKE OK`。
- 27 個 build parts 的 duplicate owner map 已逐項分類；未捕捉項目只剩 DOM property false positive，沒有未知 runtime owner。
- workflow/smoke dependency scan：沒有依賴已刪 build source；唯一 missing part reference 是 Storage QA 的刻意 `test ! -e` regression lock。另有 builder 文件中的未來 synthetic `116-1.json`，不是 runtime dependency。
- preview build 由 root `sw.js v6`、27 parts 與 essay builder 在 `/tmp` 重建；tracked `cdn/preview` 仍是上一個 main 發布的 v5 artifact，branch 上不具權威性，publish/wait 均只允許 main。
- 24 個 question shard 的實際 bytes 全部符合 manifest SHA-256；每 shard 200 題，總量 4,800。
- Service Worker source/cache contract：root v6；mutable `monthly_patch.js / essay_guides.js / manifest.json` 為 no-store network-first；v5→v6 upgrade smoke 已綠。
- compare snapshot（`2ebb0a7c`）：`main@0712b258`，ahead 138 / behind 0，78 changed files。
- Final Audit 後沒有新的未解 P0/P1。

### Round 8 結論

**第八輪可結束。**

最新 owner evidence：
- single owner：`normalize`、grading helpers、`swsiOpenEssay`、`swsiStartEssayNow`、`dissectHTML`、global `render`。
- deliberate chains：`renderHome 00→20`、`renderReview 00→70`、AI feedback/photo `00→99z`。
- independent product wrappers：law `80→86`、theory `80→88`。

目前沒有尚未處理、且收益高於風險的 P0/P1 runtime override、dead shim 或重複 module。繼續縮 owner 數量只會進入 cosmetic cleanup、跨模組大改或破壞獨立產品責任，應停止。不要 merge main；Netlify production deploy 仍需使用者另行明確授權。


最後更新：2026-08-27（官方 grading contract regression + Unified QA 特殊給分 self-test 已補並全綠）

> 下一個 ChatGPT 對話先讀本檔，再接著做：
>
> **「請先讀 GitHub 私人 repo `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，再依『目前真正的下一步』繼續。不要重做已完成項目，也不要改 Netlify，除非我明確要求。」**

---

## 0. 平台核心初衷

SWSI 的成立目的：讓準備台灣社工師國考的人有一個 **免費、公開、低門檻、真的能用** 的學習平台，不用再被題庫／解析訂閱牆卡住。

北極星：

> **「這個改動，有沒有讓考生更容易免費準備社工師國考？」**

學生端核心只抓：

> 做題 → 看解析 → 錯題／間隔複習 → 弱點 → 申論 → AI 回饋

前台做減法，後台自動化。核心刷題／複習／申論不應因 AI 額度不足而失效。

---

## 1. Source of truth / 專案位置

### GitHub
- private repo：`grizzly020503/swsi-quiz-backup`
- `main` = source of truth
- 本檔：`PROJECT_HANDOFF.md`

重要文件：
- `PRELAUNCH_QA.md`
- `MONTHLY_PATCH_PLAN.md`
- `CDN_FRONTEND_MIGRATION_DESIGN.md`
- `FRONTEND_MONTHLY_AUDIT.md`
- `FRONTEND_XSS_AUDIT.md`
- `FRONTEND_SCOPE_AUDIT.md`
- `audit/historical_answer_audit.md`

### Netlify
- production：`https://swsi-quiznetlify.netlify.app`
- **學生端採集中月更。現在不要改 `index.html / sw.js / manifest.json` 等正式前端，除非使用者明確說開始月底學生端 patch。**
- `netlify.toml` 用 `scripts/netlify_ignore.py`：只有學生端相關檔案變更才需要 build。
- README、audit、workflow、後台 test 等變更會 skip Netlify。

### Supabase
- project：`Swsi`
- project id：`yumjtrdctaxyczpspuyo`
- region：`ap-southeast-1`

### Cloudflare
- Worker：`wandering-wave-4418`
- URL：`https://wandering-wave-4418.c022050333.workers.dev`
- source：`cloudflare/wandering-wave-4418/worker.js`
- Wrangler：`wrangler.jsonc`
- Static Assets root：`cdn/`
- question CDN：`/question-shards/*.json`

D1：
- database：`swsi-ai-quota`
- binding：`AI_QUOTA_DB`
- tables：`ai_daily_client_usage`、`ai_daily_global_usage`

秘密只記名稱，不記值：
- `GROQ_KEY`
- `SWSI_INTERNAL_KEY`

---

## 2. 官方題庫／答案／給分模式 — 已完成，不要重查

Supabase 選擇題：
- **4,800 題**
- ROC 104–115
- 24 個考次
- 5 科 × 每考次每科 40 題

最新 115 年第 2 次：
- 200 選擇題
- 10 申論題

Historical MOEX Answer + Grading Mode Audit 已逐題核對官方最終資料：
- official questions：4,800
- Supabase questions：4,800
- answer findings：**0**
- grading-mode mismatches：**0**

### 多答案
- `questions.accepted_answers`
- 正式多答案：**24 題**
- 24 題仍故意 `analysis_status='review'`，避免舊前端／AI 解釋誤導；不是 DB 答案錯。

### grading_mode
Production 固定歷史基準：

| mode | 104–115 題數 | A-D | 未作答 |
|---|---:|---|---|
| `standard` | **4,784** | 依單／多答案集合 | incorrect |
| `all_credit` | **12** | correct | **correct** |
| `any_answer` | **4** | correct | incorrect |

4 題 `any_answer`：
- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

**重要：不得再從 `answer='一律給分'` 猜給分語意。**

12 `all_credit` + 4 `any_answer` 共 16 題仍刻意 `review`，因「官方特殊給分」不代表四個選項在學理上都正確。

Production migration：
- `20260825110853_preserve_official_grading_mode`

---

## 3. MOEX 自動同步 — grading mode 全鏈路已驗收

流程：

> 考選部 → GitHub Actions parser / health → Supabase → AI enrichment → CDN → 前端

Parser：
- `scripts/moex_sync_v2.py`
- 底層沿用成熟 `moex_sync.py`
- 可分 `standard / all_credit / any_answer`
- 多答案寫 `accepted_answers`
- M 更正格式無法安全解析 → **fail closed，不碰 Supabase**

Importer：
- `import-moex-social-worker`
- production v4 / ACTIVE
- fail-closed 驗證 `accepted_answers + grading_mode`

Health：
- `scripts/health_check_v2.py`
- local / remote grading mode 都驗
- 特殊給分缺 mode 不猜
- remote 104–115 grading baseline = 4784 / 12 / 4

Workflow：
- `.github/workflows/moex-social-worker-sync.yml`
- schema-only `standard` backfill 不再被當成官方內容變更
- main 併發更新時會 fetch/rebase/push retry
- 最近完整 run 已 success

不要回到舊「所有一律給分都一種模式」的 parser。

---

## 4. Cloudflare 題庫 CDN — 後端已完成，不要重做

架構：

> Supabase = source of truth  
> `scripts/build_question_shards.py` = build  
> GitHub Actions = verify / publish  
> Cloudflare Static Assets = CDN  
> Netlify = 月底改成按需載入

目前：
- baseline 24 shards：104-1 ～ 115-2
- 每 shard 200 題
- 4,800 題
- `accepted_answers`、`grading_mode` 都完整保留
- manifest / shard production HTTP 200
- `CF-Cache-Status: HIT`
- CORS 單一 `Access-Control-Allow-Origin: *`
- cache-control / nosniff 已驗
- AI root no-Origin POST 仍 403，Static Assets 沒吃掉 AI API route

Builder：
- 歷史 104–115 必須完整
- 新考次不滿 200 題 → fail closed，不發布半套
- 完整 116、117…會自動新增 shard
- 116-1 synthetic：**5,000 題 / 25 shards / `116-1.json`** 已 pass

### revision 注意
`dataset_revision` 與總 bytes **不是固定 contract**，因 shard 還包含 AI 解析／法規等會持續更新的欄位。

不要拿 handoff 裡某個舊 revision 當成「資料漂移」證據；最新 build/publish/smoke CI 才是 runtime source。

---

## 5. 2026-08-27 新增 grading regression — 已全綠

### Question Shards Build Check
commit：`778ee7f`

`.github/workflows/question-shards-build.yml` 現在除了 shard 結構，還鎖定 **104–115 immutable official grading baseline**：

- baseline questions = 4,800
- multi-answer rows = 24
- `standard` = 4,784
- `all_credit` = 12
- `any_answer` = 4
- 4 題 `any_answer` ID 必須精確一致
- special modes 必須 `answer='一律給分'` 且不可帶 `accepted_answers`

並有 executable frontend grading contract：
- `standard` blank → false
- accepted answers → true
- `all_credit` blank → **true**
- `any_answer` blank → **false**
- A-D 對兩種特殊模式都得分

2026-08-27 run：**success**。
實際 log：
- 4,800 questions
- 24 shards
- 24 multi-answer
- 4784 / 12 / 4
- `frontend_grading_contract: pass`
- 116-1 auto expansion 5,000 / 25 pass

### Unified Question QA self-test
commit：`e968e1a`

`scripts/unified_question_qa_selftest.py` 新增：
- 缺特殊 `grading_mode` → blocked
- 合法 `all_credit` → passed
- 合法 `any_answer` → passed
- 特殊 mode 與 answer／accepted_answers 自相矛盾 → blocked + human queue

Unified Question QA workflow run：**success**。
- synthetic invariants pass
- 115-2 snapshot pass
- compact admin dashboard invariants pass

不要再新增第三套 grading 判定；前端月底直接對齊這個 contract。

---

## 6. Unified Question QA / 法規 — 正常

Unified QA：
- `scripts/unified_question_qa.py`
- `scripts/unified_question_qa_selftest.py`
- `scripts/build_question_qa_dashboard.py`
- `.github/workflows/unified-question-qa.yml`

設計原則：
- Official Core 和 AI enrichment 分開
- AI 解析 pending 是 generation backlog，不等於 human review
- grading metadata 不完整 → Official Core fail closed

法規監測：
- 官方逐條查 `law.moj.gov.tw`
- 最近狀態：52/52 found、0 missing、0 changed
- canonical mapping 來源：題幹 + A/B/C/D + AI law
- 約 646 題有 canonical mapping（數字可隨 legacy AI law 清理略變）
- 題面直接出現 monitored law 但漏 mapping：0
- `sync-legal-watch` production v2 / ACTIVE

不要把「法規年代舊」自動當成「官方答案錯」。

---

## 7. AI analyzer / Cloudflare quota / 公開安全 — 已完成主要 P0

### Supabase AI analyzer
- `analyze-pending-questions`
- production v7 / ACTIVE
- scheduler job key 先驗證，再用同一值當 backend internal Cloudflare auth
- draft：Qwen
- audit：GPT-OSS
- internal path 不吃學生 D1 quota
- pg_net timeout 已 30 秒
- 24 小時完成上限 25 題
- queue 排序已讓最新考次跨科較平均

Queue 數字會變，不要把舊 ready/pending 快照當固定值。

### Worker public guard
- public Origin 只允許正式 Netlify SWSI site
- no Origin → 403
- fake Origin → 403
- POST / OPTIONS only
- request 約 4 MB 上限
- public model固定 Qwen
- internal backend 可 Qwen + GPT-OSS
- Groq error 不洩漏內部細節

### Public image guard
production runtime 已測：
- 正式 Origin + 非 JPEG data URL → 400
- 第 4 張 JPEG → 400
- 公開 image URL 只接受 JPEG data URL
- invalid image request 在 quota/Groq 前拒絕

### Rate / D1 quota
- `AI_RATE_LIMIT`：3 / 60 sec
- `AI_IP_LIMIT`：30 / 60 sec
- client daily text：約 10
- client daily photo：約 3
- 全站另有保守 daily gate
- Groq failure refund
- internal backend不吃學生 quota

### Supabase public security
`questions / essays`：
- anon SELECT only
- authenticated SELECT only
- 公開寫入已撤
- 危險 SECURITY DEFINER execute 已收斂

不要把 anon key 當 secret；service-role / Groq / internal key 才是秘密。

---

## 8. 現在真正還沒做的是「月底學生端 patch」

**目前正式 Netlify 舊前端仍沒有套以下修正。不要誤認 audit = production 已修。**

### 8.1 `index.html` 有後置 UIUX override
底部 script 會再次覆寫部分 function，至少包括：
- `renderHome`
- `renderReview`

所以月底不能只改前面同名 function；要看最後實際生效版本，或保守收斂重複邏輯。

### 8.2 已確認 round regression
見：`FRONTEND_SCOPE_AUDIT.md`

目前核心 filter 期待：
- `homeQuizRound='1' / '2' / 'all'`

但 UIUX V1 override 會傳：
- `第一次 / 第二次`

造成首頁指定單一考次可能顯示「沒有題目」。

月底先把內部 round canonical 統一成 `1 / 2 / all`。

### 8.3 多答案／特殊給分前端尚未支援
見：`FRONTEND_MONTHLY_AUDIT.md`

現行舊前端仍有：
- `ansCorrect(p,a)`
- `k===item.answer`
- `picked===q.answer`
- `/一律給分|送分/`

月底必須：
1. `normalize()` 保留 `accepted_answers + grading_mode`
2. 只用共同 `gradingMode / acceptedAnswers / isCorrectAnswer / answerLabel`
3. 一般刷題、模擬考、錯題、history、review schedule、正確率都走同一 contract
4. `all_credit` 空白得分，不進錯題
5. `any_answer` 空白不得分，進錯題
6. 特殊給分 UI 不把 A-D 四個都畫成「學理正確」

### 8.4 CDN 前端 loader 尚未切
見：`CDN_FRONTEND_MIGRATION_DESIGN.md`

低風險策略：
- manifest-first
- 指定歷屆只載需要 shard
- 需要全庫的搜尋／考點／隨機模擬／review 再 `ensureAllQuestionsLoaded()`
- 保留 `ALL` 相容橋，先不要大改全部 feature
- IndexedDB 改成可保存 manifest / shard；舊完整 `questions` cache 可做 fallback
- Cloudflare shard 是跨 origin，現行 `sw.js` 不攔；**不要硬塞進 Service Worker shell cache**

### 8.5 Stored XSS
見：`FRONTEND_XSS_AUDIT.md`

`renderQuiz()` 等仍有 DB/AI 動態文字直接進 `innerHTML`；月底要 context-aware escape，URL 只允許安全 scheme。

### 8.6 其他月底一起修
- 穩定 `X-SWSI-Client-ID`
- Worker 真實 quota/error message
- 模擬考未作答各科分母/history/review 一致
- deep-link 理論／法規自動展開
- localStorage 寫入失敗提示
- 申論 AI 過度承諾文案收斂
- AI 外部處理隱私說明
- 前端照片最多 3 張
- `E-115-2-R-1` PUA 字元清理
- 首頁第一屏「免費社工師國考學習平台」
- SEO / OG
- keyboard / aria
- 色彩對比
- 最後 bump `sw.js` VERSION（目前 v4）

---

## 9. 如果使用者明確說「開始月底學生端 patch」

施工順序不要亂：

1. **先修 round canonical regression**
2. **立刻補 `accepted_answers + grading_mode` 與統一 grading helper**
3. 加 grading regression / mock 驗收
4. 再切 Cloudflare manifest/shard loader
5. 再補 XSS / Client-ID / quota message / storage / deep-link / accessibility / 文案
6. bump `sw.js` VERSION
7. build + smoke + diff review
8. Netlify production deploy **一次**
9. iPhone Safari / Android Chrome / desktop Chrome + PWA smoke

不要先從 SEO、外觀或新功能開始。

---

## 10. 目前可以繼續做（還沒得到月更開工指令時）

可以：
- read-only frontend audit
- backend/self-test/regression
- 文件一致性清理
- GitHub Actions 測試加強

不要：
- 改 `index.html`
- 改 `sw.js`
- 改 `manifest.json`
- 改會影響 production 學生端的檔案
- 為了「程式漂亮」大規模重構 override
- 再做一套新的 grading / CDN 架構

2026-08-27 本輪已做：
- README 架構對齊：commit `f92c4f2`
- shard grading contract CI：commit `778ee7f`，run success
- Unified QA special-grading self-test：commit `e968e1a`，run success
- 以上變更都不在 Netlify student-facing path，`netlify_ignore.py` 會 skip production build

---

## 11. 不要重做／不要誤判

- 不要重查 4,800 題官方答案；audit = 0 finding
- 不要把 24 多答案 review 當 DB 錯題
- 不要把 16 特殊給分混成同一種：12 all_credit / 4 any_answer
- 不要把 `answer='一律給分'` 當 grading source of truth
- 不要重建 D1 / rate limit binding
- 不要重新開公開 DB write
- 不要讓 AI 修改官方題目／答案／grading mode
- 不要拿固定 shard revision 當 invariant
- 不要開 R2 或第三個 Worker重做題庫 CDN
- 不要拿 GitHub 舊 Edge Function 覆蓋 production
- 不要改 Netlify，除非使用者明確要求開始月更施工

---

## 12. 下一個對話最短啟動指令

> **請讀 GitHub `grizzly020503/swsi-quiz-backup` 的 `PROJECT_HANDOFF.md`，依「目前真正還沒做的是月底學生端 patch」與「目前可以繼續做」繼續。不要重做已完成後端，也不要改 Netlify，除非我明確要求。**
