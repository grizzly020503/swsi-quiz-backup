# 社工師國考題庫 — 救援重建版

重建日期：2026-08-24

## 已救回內容

- `index.html`：原部署網站主程式
- `essay_guides.js`：由原 `index.html` 內嵌資料重建
  - 49 組考點叢集
  - 35 個理論
  - 18 部法規
  - 230 份申論答題骨架
- `data/questions_master_backup_20260824_2220.csv`
  - 選擇題共 4600 題
  - 唯一 ID 共 4600 筆
- `manifest.json`
- `sw.js`
- `apple-touch-icon.png`
- `icons/icon-192.png`
- `icons/icon-512.png`

## 選擇題科目數量

- 社會工作研究方法：920 題
- 人類行為與社會環境：920 題
- 社會工作：920 題
- 社會工作直接服務：920 題
- 社會政策與社會立法：920 題

## 重要提醒

1. `questions_master_backup_20260824_2220.csv` 是救援母檔，不要直接覆寫。
2. 原網站選擇題仍從 Supabase `questions` 資料表載入；CSV 是獨立備份。
3. AI 申論批改依賴原 Cloudflare Worker；後端失效不會影響題庫本身。
4. 此 repository 必須維持 **Private**。
5. 完整專案另有壓縮備份，請至少再保留一份於本機或雲端。
