# SWSI Netlify 手動更新

這份流程的目的，是讓網站更新不依賴 ChatGPT Pro 或外部代理工具。

## 取得最新部署包

1. 打開 GitHub repo `grizzly020503/swsi-quiz-backup`。
2. 進入 **Actions**。
3. 選擇 **Netlify Manual Deploy Artifact**。
4. 點 **Run workflow**，branch 選 `main`。
5. 等 workflow 顯示綠色成功。
6. 打開該次 run，在 **Artifacts** 下載 `swsi-netlify-manual-deploy`。
7. 解壓 GitHub artifact；裡面會有：
   - `swsi-netlify-manual-deploy.zip`
   - `swsi-netlify-manual-deploy.sha256`
   - `NETLIFY_MANUAL_DEPLOY_INFO.txt`

## 上傳到 Netlify

1. 登入 Netlify。
2. 打開既有的 SWSI site。
3. 進入 **Deploys**。
4. 使用手動部署／drag-and-drop deploy。
5. 上傳 `swsi-netlify-manual-deploy.zip`。
6. 等 Netlify 顯示 deploy 成功後，再用正式網址做基本驗證。

不要上傳整個 GitHub repo，也不要只上傳 `index.html`。部署包已經把 Netlify 的 `_site` publish 內容放在 ZIP 根目錄。

## 這個 ZIP 會更新什麼

它會依照 repo 當下 `netlify.toml` 的正式 build command 重新產生完整 `_site`，因此包含學生端前端、管理中心、monthly runtime、essay guides、PWA/service worker、icons 與公開 auto snapshots 等 Netlify 靜態站內容。

## 這個 ZIP 不會更新什麼

手動 Netlify deploy **不會**部署：

- Supabase migration
- Supabase Edge Functions
- Cloudflare Worker backend / D1
- GitHub Actions secrets 或其他 production credentials

如果未來某次更新同時修改這些 backend/infra，必須另外照該服務的發布流程處理，不能只靠這個 ZIP。

## 安全原則

- 每次部署前重新跑 workflow，拿當下最新 `main` 的 artifact，不要長期重複使用舊 ZIP。
- workflow 會先跑 `netlify.toml` 裡原本就有的 build/QA guards；build 失敗就不會產出可下載的部署包。
- GitHub artifact 保留 30 天；過期後重新 Run workflow 即可重新產生。
