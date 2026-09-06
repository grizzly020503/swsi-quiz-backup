# SWSI Monitoring V2

SWSI 的「監測」不是單一網站 ping，而是五個互相獨立、都能追到真實資料來源的監測面向：新聞／時事、法規、題庫、系統、使用者回報。

## 1. 新聞／時事監測

- `scripts/current_affairs_watch.py` 讀取衛生福利部官方 RSS 與中央社社會／生活／政治／國際 RSS。
- 只保留與社工師考試較有關的兒少、家暴、心理健康、長照、社會救助、身障、人權、移工、少年司法、社工制度等議題。
- `.github/workflows/public-monitoring-feed.yml` 每 6 小時重新掃描一次，並把去重、聚類後的公開結果同步到 `auto/current_affairs.json` 與 `cdn/auto/current_affairs.json`。
- 公開監測頁只顯示標題、類別、日期、來源與官方／新聞連結，不蒐集使用者資料。

這是近即時雷達，不宣稱每秒鐘輪詢新聞網站。

## 2. 法規監測

- `scripts/moj_law_watch.py` 直接核對全國法規資料庫的官方頁面與修正日期。
- watchlist 目前涵蓋 52 部與題庫相關的法規。
- 完整法規核對採低頻、低負擔方式執行；偵測到修正日期變動只產生警示，不直接改題目、答案或解析。
- `scripts/build_public_legal_watch_snapshot.py` 會把內部報告轉成 privacy-safe 的 `auto/legal_watch.json`／`cdn/auto/legal_watch.json`，公開頁只看到總數、查核時間與官方法規連結，不公開營運診斷或管理資料。

正式內容是否需要修改，仍必須經人工查證歷史施行時點與考題年份。

## 3. 題庫監測

- `MOEX Social Worker Exam Sync` 每日檢查考選部社工師官方考題／答案。
- 題庫 runtime 另外核對 4,800 題、24 shards、manifest、SHA-256、grading_mode 與特殊給分語意。
- 公開監測頁同時讀取 live question manifest、`auto/health.json` 與 `auto/sync_state.json`，讓「題庫正常」不是只看檔案能不能下載。

任何官方答案、特殊給分或歷史法規差異，都不能因自動監測結果直接覆寫正式資料。

## 4. 系統監測

使用者開啟監測頁時，會以唯讀方式檢查：

- Cloudflare 正式主站。
- PWA manifest 與 Service Worker。
- `/api/ai` CORS preflight；不送 prompt、不呼叫模型。

另外 `.github/workflows/public-uptime.yml` 每日約台灣時間 08:17 執行外部 sentinel，補上無人開站時的可用性訊號，並保留 Netlify 備援檢查。

## 5. 使用者回報監測

- 公開監測頁只檢查 `swsi-feedback` Edge Function 的 CORS／可用性，不寫入測試資料。
- 真人回報仍進入 Supabase feedback 與 Admin 管理流程。
- 公開頁不顯示回報者聯絡方式、user-agent、client identifier 或管理端內容。

## 成本、隱私與誠實邊界

- Monitoring V2 不新增追蹤 cookie、不建立新的公開帳號、不上傳學習紀錄、不為監測呼叫 AI 模型。
- 新聞雷達每 6 小時更新；完整法規核對是低頻背景工作；系統監測則在使用者開啟時立即執行，另有每日外部 sentinel。
- 因此 SWSI 可以稱為「持續監測」或「開啟當下即時檢查」，但不應宣稱所有五個來源都是每秒 24/7 即時輪詢。
- 監測發現異常只產生警示。題目、答案、法規解讀、Auth、安全與資料庫變更仍需要人工審查與 release gate。
