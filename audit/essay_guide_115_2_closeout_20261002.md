# 115-2 申論學習 Guide Closeout — 2026-10-02

> 目的：留下可被後續 AI／maintainer 直接搜尋的 durable audit。這份文件只記錄已驗證狀態，不取代官方題庫，也不宣稱 SWSI guide 是考選部標準答案。

## 最終狀態

- 115-2 官方申論題：10 / 10 存在且官方題幹受保護。
- `data/essay_enrichment.json`：10 / 10 teaching metadata 已 ready。
- `data/essay_guide_overlay.json`：**10 verified / 0 held**。
- 所有 overlay guide：`is_official=false`，學生端明示非考選部官方答案。
- 學生 runtime 總 guide 數：**240 unique guides**。
- 官方題幹 contract：`official_question_text_unchanged=yes`。

## 本次完成鏈

### PR #238 — 研究方法兩題

- `E-115-2-R-1`：概念化／操作化／測量流程。
- `E-115-2-R-2`：縱向、橫向、理論性質性分析。
- 合併後 coverage：7 verified / 3 held。

### PR #239 — 性侵害犯罪防治法題

- `E-115-2-SP-2`。
- 115-2 實際考試日：2026-07-25 至 2026-07-26。
- 《性侵害犯罪防治法》考試日有效版本：2023-02-15 修正公布之 56 條版本。
- 第 7 條第 2、3 項之跨罪被害人保護準用，與第 1 項加害人處遇準用分開處理。
- 合併：`f2ce61ee2eb791ca0a397ddeeb795afd316f009e`。

### PR #241 — 危機介入／性侵害處遇題

- `E-115-2-SW-1`。
- 危機介入以短期、當下、恢復心理平衡與因應能力為主。
- 成年被害人的驗傷採證與服務選擇維持知情／自主；社工執行職務知悉疑似性侵害，法定通報仍須於 24 小時內完成。
- 合併：`52e9fd006653ff7685bdffafa655ab6aadd51aeb`。

### PR #242 — 福利給付型態題／全 coverage closeout

- `E-115-2-SP-1`。
- Guide 以政策價值與執行條件分析現金、實物、代券、抵減稅額；不宣稱存在唯一固定的官方原則清單。
- 同步修正 `scripts/essay_guide_overlay_smoke.js`：當 `held_for_review=[]` 時，fail-closed mutation test 改以 verified record 模擬未驗證覆寫，仍要求 builder 拒絕 `review_status != verified`。
- 合併：`62347e73d1bc5e12af4f2a7aac7633d900ff6c5a`。
- Cloudflare preview bot 後續 main：`c5dc101de97b9db9a4540cb96c2af01201a4d8cd`。

## 最終 QA 證據

PR #242 Essay Guide Overlay QA：

- `ESSAY GUIDES RUNTIME OK: 240 unique guides; overlay_verified=10; held=0`
- `ESSAY GUIDE OVERLAY CONTRACT OK: sessions=115-2; verified=10; held=0; official_question_text_unchanged=yes`
- `ESSAY GUIDE OVERLAY BROWSER OK: verified=10; held=0; page_errors=0`

合併後 main 再驗：

- Essay Guide Overlay QA run `36956941147`：**success**。
- Build Cloudflare Frontend Preview run `36956941128`：**success**。
- Cloudflare preview build、isolated preview 標記、static assets publish、preview deployment 均 success。

## 已清理的舊 PR

- PR #240 是較早的 SP-1-only 分支，base 與 coverage 停在 `8 verified / 2 held`。
- 已於 2026-10-02 關閉且明示 superseded，**不可重新合併**，避免把舊 overlay 狀態帶回 main。
- Closeout 後 open PR：**0**。

## 尚未完成，不得誤報為完成

### 1. Netlify production release

`Netlify Controlled Production Deploy` 的 PR event 只做 preflight/build；production deploy、production HTTP verify、production browser smoke 都會 skipped。

因此本次 10/10 guide 已：

- merged to main；
- main QA passed；
- Cloudflare isolated preview passed；

但**不能因此宣稱最新版本已部署到 Netlify production**。正式 production 仍需針對最新 main 做 controlled `workflow_dispatch`，再以 production HTTP/browser smoke 驗證。

### 2. Issue #157 — 真實 private-data DR exercise

Repo/source 隔離式 DR 與 guarded tooling 已完成；Issue #157 保持 open 的唯一實質理由是 maintainer-controlled local exercise 尚未執行：

1. 在受控本機建立第一份 production private-data 加密備份；
2. encrypted bundle + checksum 存到至少一個 repo 外／off-site 位置；
3. 還原至全新 isolated target；
4. 用 count-only baseline 驗 source/target（含 `auth.users`）；
5. 實測並記錄 hosted-data RPO / RTO。

安全規則：不要把 production DB URL、password、age private identity、解密後 private rows 放入 Git、GitHub Actions artifact、Issue、PR、log 或聊天。

## 後續 AI READ FIRST

若要繼續開發：

1. 先讀最新 main HEAD，不要假設本文件 SHA 永遠最新。
2. 不要重新建立 115-2 guide coverage；目前已是 10 / 10 verified。
3. 不要重新開或合併 #240。
4. 若要處理 production，上線前先確認 `netlify-controlled-production-deploy.yml` 的 controlled dispatch 真實執行 SHA。
5. #157 不可用 CI 假造完成；只有實際 encrypted private-data backup + isolated restore + RPO/RTO evidence 才能關閉。
