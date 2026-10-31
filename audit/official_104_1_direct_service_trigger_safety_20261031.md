# 104-1 Direct Service 三題｜正式資料庫觸發器風險與隔離交易證據

狀態：**DRAFT / NO-GO**。本文是工程審查證據，不是正式部署指令。

## 已查核來源

- 2026-10-31，Supabase production `public.questions`：4,800 題；4,666 ready；134 review。
- 考選部官方原始 PDF：`104030 / 11020`，317,707 bytes；SHA256 `979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc`。
- 原卷第 4-3 頁，Q22、Q27、Q29 共 15/15 題幹／選項欄位已與候選一致；答案 A/B/D 不改。
- 唯讀 37 欄影子模擬：`audit/official_104_1_direct_service_three_shadow_readonly_20261031.sql`，4,800 判分 tuple、4,797 非目標題皆未變。
- 隔離 PostgreSQL 17 真正交易測試： [Actions #41212305277](https://github.com/grizzly020503/swsi-quiz-backup/actions/runs/41212305277) **SUCCESS**；由 `scripts/official_1041_ds_isolated_pg_rehearsal.py` 產生 4,800 筆資料、三題完整 37 欄快照，並在無正式金鑰的 disposable Postgres 17 容器內執行兩種交易。
- GitHub 工作流程：`.github/workflows/official-1041-isolated-pg-rehearsal.yml`，只對此 Draft PR 分支跑；並非 production migration。

## 正式資料庫存在七個啟用的 questions 觸發器

唯讀查詢 `pg_trigger`、`pg_get_triggerdef`、`pg_get_functiondef` 所見：

1. `questions_00_sanitize_unverified_law_provenance`：檢查法律引用來源；
2. `questions_sync_legal_canonical_names`：更新法規名稱快照；
3. `trg_auto_enable_ai_pending`：在 `INSERT` 或明確 `UPDATE OF analysis_status` 為 `pending` 時，可能啟動 AI 分析排程；
4. `trg_auto_stop_ai_queue`：離開 pending/analyzing 時可能進行排程停止判斷；
5. `trg_questions_analysis_completed_at`：更新完成時間；
6. `trg_reject_ai_answer_meta_commentary`：禁止未核准 AI 解析文字；
7. `trg_reset_ai_on_official_change`：官方題幹／選項變動即清空舊 enrichment，並強制 `analysis_status='pending'`。

**已驗證的危險路徑：** 一次 `UPDATE` 同時修改題幹及明確設定 `analysis_status='review'`；BEFORE reset trigger 會將 NEW 改為 `pending`，AFTER `UPDATE OF analysis_status` 的 scheduler trigger 看到 `pending`，可能排程。**不能直接執行該寫法。**

## 隔離環境測過的低風險兩步驟（仍不得直接套到正式站）

1. 在同一交易內，**只** UPDATE 目標三題的 `question/opt_a/opt_b/opt_c/opt_d`，不在第一個 SQL UPDATE 的 SET 欄中列出 `analysis_status`。原 trigger 因 Official Core 差異自動清空過時解析並轉為 `pending`；該次 SQL 不直接觸發 `AFTER UPDATE OF analysis_status` scheduler。
2. 立刻在同一交易內，以**另一條僅修改 `analysis_status`** 的 UPDATE，將三題轉成 `review`；不會觸發 Official Core reset，scheduler 看見的是 `review`。
3. 在 **COMMIT 前** 檢查 exactly 3 postimages、4797 其他題不變、4800 判分不變、沒有 pending、AI 設定仍 disabled、沒有新增排程事件；任何異常必須 rollback。
4. 上述流程在 **隔離、簡化觸發器** 的 PostgreSQL 17 真交易內成功，並已執行 ROLLBACK，還原 4,800 測試資料與模擬 AI 狀態。

**2026-10-31 更新：** 下方「七觸發器原始程式」測試已補上本段原先缺少的五個 triggers，並加入匿名與一般登入角色的 SELECT/RLS 權限檢查。然而 **pg_cron、net.http_post 及完整正式資料庫復原環境仍未複製**；其餘 4,797 題是由公開 CDN 快照載入，非每題 37 欄的 production 備份，因此仍不是「正式交易已驗證」或「必然安全」。production `public.ai_analysis_job_config.enabled` 在本輪唯讀查詢仍為 `false`。在正式環境直接測試寫入，可能有資料觸發器、排程與第三方副作用，需先有**真正隔離的 production-faithful restore**、人工來源批准和明確發布授權。


## 2026-10-31 擴充：全部七個正式 trigger DDL 的隔離執行結果

讀取正式 `pg_catalog` 後，已將七個啟用的 `pg_get_triggerdef` 與相應 `pg_get_functiondef`、法律名稱抽取函式，**逐字保存**於 `audit/official_104_1_live_seven_trigger_definitions_20261031.json`。該文件只有靜態程式與觸發器定義，不包含資料庫金鑰、使用者資料或私密備份。

`scripts/official_1041_ds_isolated_pg_rehearsal.py` 現在會在一次性 PostgreSQL 17 容器建立 4,800 筆公開題庫快照，**載入七個與正式資料庫相同的 trigger 函式定義及 trigger DDL**，並重現官方文字更新的實際執行順序。只有具網路或排程副作用的 `enable_swsi_ai_analysis` 與 `maybe_stop_swsi_ai_analysis` 使用**無副作用替身**，不會產生真實 cron 工作或 HTTP 呼叫。

新增角色測試以獨立的 `swsi_anon` 與 `swsi_authenticated` 模擬兩種學生角色，測試結果均可透過 SELECT/RLS 讀取 4,800 題，且對題庫未持有 INSERT/UPDATE/DELETE 權限。這證明**隔離模型**符合該權限契約，不代表所有正式 Supabase API 權限已完成完整 E2E 驗收。

最新提交 `982aa8457efa340189b4c005b778bdfc51f4322e`：

- <https://github.com/grizzly020503/swsi-quiz-backup/actions/runs/41212950794> — **SUCCESS**：七觸發器、學生角色權限、正式來源修正、兩步驟交易、全部題目回滾、無模擬 AI 排程事件。
- <https://github.com/grizzly020503/swsi-quiz-backup/actions/runs/41212950858> — **SUCCESS**：完整題庫 QA。

**仍未做：** 對正式站 DML、七個觸發器以外的真實 pg_cron/pg_net、Production-faithful 私有 isolated restore、正式部署；獨立人工官方來源核准仍為 false，Owner 尚未授權當前任務合併或部署。

## 尚未完成的必需發布關卡

- 獨立人工來源核准（目前 `false`，不是 AI 自評代替）。
- 在隔離且可回復的 production-faithful 複本中，驗證其餘五個 trigger、相同 RLS、PG cron 與實際更新順序。
- 完整 37 欄 postimage、官方題庫鎖檔、shard/manifest 更新、解析降級，需同批經過 CI。
- owner 另行明確授權 main 合併、正式 DB 更動、Cloudflare 部署與線上驗收；**Netlify 備援站永遠不在範圍**。
- 428 筆原始 PDF review flags、134 題 AI review（若此三題上線，review 預測 136）未因本次測試自動清除。

**本輪正式站、正式資料庫、main、Netlify 備援站：均未修改。**
