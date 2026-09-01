# SWSI Monitoring V1

SWSI uses layered monitoring so「監測」不只是首頁上的宣傳文字。

## 1. 使用者開啟時的即時檢查

公開資訊中心的「監測」頁會在使用者打開時，以唯讀方式檢查：

- Cloudflare 正式主站是否可連線。
- PWA manifest 與 Service Worker 是否可讀取。
- 題庫 manifest 是否仍為 4,800 題 / 24 shards。
- 正式站 `/api/ai` 的 CORS preflight 是否為 204；不送 prompt、不呼叫模型。
- `swsi-feedback` Edge Function 的 CORS preflight 是否為 204；不寫入回報資料。
- 法規監測機制的治理說明：異動需核對後才影響正式內容，不自動改答案。

這是「開啟當下」的即時檢查，不代表伺服器每秒鐘 24/7 主動輪詢。

## 2. 無人開站時的外部定期哨兵

`.github/workflows/public-uptime.yml` 每日 00:17 UTC（台灣時間約 08:17）執行一次 `scripts/public_uptime_smoke.py`。

它只做公開 HTTP/CORS 讀取：

- Cloudflare 正式首頁。
- PWA manifest / Service Worker。
- 題庫 4,800 / 24 基線。
- `/api/ai` preflight。
- feedback preflight。
- Netlify 備援首頁。

刻意維持每日一次，而不是每小時執行，避免為低變動的公開靜態服務浪費 GitHub Actions 額度。Release QA 與真人開啟監測頁會補上部署期間與使用期間的即時檢查。

## 3. 題庫、法規與回報的治理層

- 題庫完整性仍由 shard SHA-256、manifest invariant、grading QA 與 production smoke 守門。
- 法規監測只產生警示；需要核對後才能修改正式題庫或答案。
- 使用者問題回報進入既有 Supabase feedback / Admin 流程，不公開管理資料。
- AI telemetry 尚未啟用，因此 Monitoring V1 不宣稱能顯示 AI 即時用量、錯誤率或模型成本。

## 隱私與成本原則

Monitoring V1 不新增追蹤 cookie、不建立使用者帳號、不上傳學習紀錄、不呼叫 AI 模型，也不需要新的付費監控服務或 secret。
