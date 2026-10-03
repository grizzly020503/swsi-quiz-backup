# 2026-10-03 法規解析引用校正（12 題）

## 範圍

本批只修正平台生成／教材層的法規條號引用，不修改受保護的官方題幹、選項、官方答案、accepted_answers 或 grading_mode，也不因本次校正把題目標成 human verified / verified_current / historical_version_checked。

Production 在修正前 12 題均為 `analysis_status=ready`、`legal_status=unreviewed`。Migration 以題號＋現有 law／exp_why／extension 完整值作 fail-closed 前置條件；任何一筆先被其他流程修改就整批拒絕套用，避免覆蓋較新的人工或自動修正。

## 已確認的引用錯置

### 特殊境遇家庭扶助條例

- 扶助項目應引用第 2 條，而非第 3 條：
  - `SP106-1-17`
  - `SP110-1-34`
  - `SP111-1-35`
- 緊急生活扶助的金額、三個月原則與事實發生後六個月內申請，應引用第 6 條，而非第 7 條：
  - `SP104-1-28`
  - `SP107-1-34`
  - `SP108-2-34`
  - `SP109-2-35`
  - `SP114-1-35`
- 各項津貼或補助之權利不得扣押、讓與或供擔保，應引用第 13-1 條，而非第 15 條：
  - `SP111-2-35`

Official source: 法務部全國法規資料庫 `特殊境遇家庭扶助條例`（pcode `D0050075`）。

### 國民年金法

- 中央主管機關應補助保險費及應負擔款項之財源，應引用第 47 條，而非第 36 條：
  - `SP106-2-24`
- 月投保金額依消費者物價指數累計成長率調整，應引用第 11 條，而非第 13 條：
  - `SP110-1-37`

Official source: 法務部全國法規資料庫 `國民年金法`（pcode `D0050152`）。

### 身心障礙者權利公約施行法

- 施行後二年提出優先檢視清單、不符者三年內完成增修／改進、其餘五年內完成的 2/3/5 年法規檢視時程，應引用第 10 條；production 原 `law` 誤標第 7、9 條：
  - `SP107-1-23`

Official source: 法務部全國法規資料庫 `身心障礙者權利公約施行法`（pcode `D0050194`）。

## 信任邊界

- 本批是 **citation/metadata correction**，不是「整題解析已人工驗證」宣告。
- substantive explanation 已與對應條文內容一致者只修條號；不為了改 citation 重寫整段答案理由。
- 歷史法規版本驗證仍由 priority10 provenance / Stage 3–7 流程管理；本 migration 不直接增加 19/85 的 historical verified coverage。
- Stage 3 article resolver 保持 answer-blind；後續另建 answer-aware evidence adjudication lane，避免高相似度候選被錯誤選項吸走後直接升級。

## 來源／後續

- Issue #261 已記錄本批根因與待辦。
- 本批上線後需用正式 question-shard publish 流程同步 Supabase → repo shards → Cloudflare，並抽查 12 題新 citation；不得手改 CDN JSON。
