# SWSI｜社工師國考免費學習平台

SWSI 是一個以台灣社會工作師國考準備為核心的免費學習平台。專案把歷屆選擇題、錯題複習、申論練習、PWA 離線能力與可選的 AI 學習回饋整合在同一個低門檻介面中。

> 本專案為民間學習工具，並非考選部、政府機關或任何補習機構的官方服務。正式考試資訊、答案與法規仍應以主管機關最新公告為準。

## 目前包含

- 4,800 題歷屆選擇題資料流程與特殊給分模式支援
- 練題、模擬考與錯題複習
- 1 → 3 → 7 → 14 → 30 天間隔複習邏輯
- 歷屆申論題、拆題骨架與草稿練習
- 可選的 AI 申論學習回饋
- PWA / Service Worker 與瀏覽器儲存備援
- Supabase Auth / RLS / 管理員 allowlist 邊界
- Cloudflare Worker 的 Origin、rate limit、每日免費額度與 secret-backed internal access

## 架構概覽

```text
學生瀏覽器
  ├─ 靜態前端 / PWA
  ├─ 題庫 CDN
  ├─ Supabase（資料、Auth、回報）
  └─ Cloudflare Worker（AI proxy / quota / security boundary）
       └─ AI provider
```

更多設計背景請看 `ARCHITECTURE.md`。

## 為什麼這個 repository 是「整理後的公開版」

正式營運環境的部署歷史、備份包、私有 handoff、production secrets 與私人 Git commit history 不屬於公開作品的一部分，因此不會放在這裡。

這個 repository 使用乾淨 snapshot 建立，不繼承私人開發 repository 的舊 Git history。公開版也不包含未取得明確再散布授權的第三方讀書筆記內容。

## 安全原則

- production secret 不進 Git
- service-role / AI provider / internal access key 只能由部署環境注入
- 公開前端知道 endpoint 並不等於取得權限；真正授權由後端 RLS/Auth/allowlist/secret checks 執行
- AI 故障或額度耗盡時，刷題、錯題與非 AI 核心功能仍應可使用
- 不因為測試失敗就降低 grading、Auth、security 或資料完整性要求

安全問題請先閱讀 `SECURITY.md`。

## 本機查看

這是傳統靜態前端，可以用任一靜態 HTTP server 查看，例如：

```bash
python -m http.server 8000
```

部分資料與 AI 功能會連到公開 runtime services；單純開啟 HTML 檔案不一定能重現完整正式環境。

## 資料與內容說明

歷屆考試與法規資訊應回查原始主管機關。這個 repository 的可見原始碼不代表第三方內容一併取得開放授權；未另行註明的第三方材料不應視為本專案授權內容。

## 授權

目前尚未選定開放原始碼授權。除非 repository 之後加入明確的 `LICENSE`，否則不要假設程式碼或內容可任意複製、再發布或商業使用。
