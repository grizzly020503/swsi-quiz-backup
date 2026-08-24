# Netlify 重新部署

這是一個靜態網站。

部署時至少需要：
- `index.html`
- `essay_guides.js`
- `manifest.json`
- `sw.js`
- `apple-touch-icon.png`
- `icons/`

`data/questions_master_backup_20260824_2220.csv` 是題庫救援母檔，不需要公開部署。

注意：選擇題仍由 Supabase `questions` 表載入，因此正式網站須能存取原 Supabase 專案。
