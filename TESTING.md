# SWSI Testing Guide

本檔定義修改後最低限度要跑的測試。目的不是測試數量多，而是避免不同入口各自 regression。

## 1. 最低共通檢查

任何程式修改至少確認：

- 語法檢查通過。
- 沒有 secrets / API key / service-role key 被加入 diff。
- 沒有意外修改 production-only 設定。
- 對應 regression test 通過。
- 若修改學生端，需跑 production-shaped static smoke。

## 2. Grading / 題庫

修改以下任一處時必跑：
- grading helper
- `grading_mode`
- `accepted_answers`
- 模擬考
- 題庫 loader
- shard

至少測五種情境：
1. `standard` 單答案。
2. `standard` 多 accepted answers。
3. `all_credit` 已作答。
4. `all_credit` 未作答仍得分。
5. `any_answer` 未作答不得分。
6. 特殊給分缺／矛盾 metadata 必須 fail closed。

同時檢查：
- 模擬考分母含未作答普通題。
- 未作答錯題依 contract 進入複習／錯題紀錄。
- 一般刷題與模擬考結果一致。

## 3. CDN shard / Offline

修改 shard loader、manifest、IndexedDB 時必測：
- 200 題結構正確 shard 可載入。
- SHA-256 正確才接受。
- SHA 不符必須拒絕且不得以 manifest 預期值偽裝成已驗證。
- 舊 cache 缺 hash 時不能永久繞過 integrity check。
- 線上更新後舊離線 shard 能被安全刷新。

## 4. Service Worker

修改 `sw.js`、mutable asset 或發布策略時必測：
- HTML network-first。
- `monthly_patch.js` network-first。
- `essay_guides.js` network-first。
- mutable manifest network-first。
- 外部 Cloudflare/Supabase/AI request 不被攔截。
- cache version 更新後舊 cache 被清理。
- 離線仍可 fallback 到最近 shell。

## 5. 申論

修改 guide / builder 時必測：
- source duplicate-key lint。
- deploy artifact key 唯一。
- verified 題 `guideMust` 全部命中。
- `guideMustNot` 不得命中。
- 歷史法規題版本鎖定。
- Batch verified registry 不得同題互相覆蓋。

## 6. MOEX / 新考次

修改 parser / importer / health / QA 時必測：
- 每科 40 題。
- 一考次 200 選擇題。
- 題號 1–40。
- A/B/C/D 完整。
- accepted answers 合法。
- grading mode 合法且特殊題 fail closed。
- parser 未能安全解析時不得 import。
- schema-only backfill 不應被誤判為官方內容變更。

Unified QA 必須從 manifest 自動辨識最新考次，不要每年硬改 workflow 年份。

## 7. AI / Cloudflare Worker

修改 Worker、AI 前端、quota 時必測：
- Origin / method / payload size guard。
- 模型 whitelist。
- 文字／照片限制。
- 429 rate-limit 與 daily/global quota 可區分。
- `temperature: 0` 真正保留為 0，不得因 `||` fallback 變成其他值。
- timeout / 4xx / 5xx 有可理解錯誤。
- 失敗時不丟失本機申論草稿。
- quota refund contract 正常。

### AI 回饋品質 Golden Set

Worker/security smoke 只能證明「管線與防線正常」，不能證明生成內容品質沒有退步。

若修改以下任一項，除原本 Worker / browser contract 外，還必須做 AI feedback Golden Set 評估：
- `monthly_patch_parts/99z.essay-trust-layer.part` 的主要申論回饋 prompt / authority boundary /輸出結構；
- Cloudflare Worker 的 public model；
- 會明顯改變申論 AI 回饋內容的模型參數或行為。

最低步驟：
1. `python3 scripts/ai_feedback_eval.py`：確認 Golden Set、prompt version、required clauses、temperature 與 public-model contract 沒有無聲漂移。
2. `python3 scripts/ai_feedback_eval_selftest.py`：確認 evaluator 對權威式給分、漏 section、漏 case、prompt/model drift 會 fail closed。
3. 真正要更換 prompt / public model 時，對固定 Golden Set 產生一輪 candidate outputs，逐案例做 human rubric review，再跑 `python3 scripts/ai_feedback_eval.py --outputs <file> --require-human-scores`。

Default GitHub Actions **不得直接呼叫 live AI provider**。Golden Set 的 CI gate 應維持 deterministic / no-network / no-model-quota；live-model 比較是有目的、有限次數的人工 release/review 動作，不得為了綠燈重複燒免費額度。

目前 V1 只涵蓋文字申論回饋；photo/OCR 是不同 failure surface，後續若要納入應建立獨立案例集，不得把文字 Golden Set 的 PASS 當成照片辨識品質證據。

## 8. Supabase

若變更 SQL / migration / trigger / function：
- production schema 與 repo recovery SQL 做 drift compare。
- RLS / function privileges 檢查。
- `SECURITY DEFINER` function EXECUTE 不得意外給 `PUBLIC/anon/authenticated`。
- official-change trigger 對題幹、選項、答案、accepted_answers、grading_mode 的異動行為一致。
- DDL 優先使用 migration；不要把手動 production hotfix 當唯一 source。

## 9. Browser smoke

涉及學生端互動時，用 Chromium / browser smoke 驗證至少：
- 首頁考次 selector `all / 1 / 2`。
- 開始刷題。
- 作答與解析。
- 模擬考開卷／交卷。
- 申論入口。
- AI 按鈕 busy / 429 顯示。
- 手機尺寸不遮底部操作。

## 10. CI 紅燈處理順序

CI 失敗時：
1. 讀完整 log。
2. 確認是 runtime bug、test 過期，還是 infrastructure/permission 問題。
3. 修真正原因。
4. 重新跑。
5. 不得直接刪 gate。

若 GitHub App / Actions token 權限不足以修改 workflow，應記錄為 infra blocker，不要誤判成產品程式失敗。

## 11. Merge 前最低要求

- P0 對應 regression 全綠。
- Monthly Frontend QA 全綠。
- Cloudflare preview/build 全綠或只有明確非產品權限 blocker。
- Unified QA 全綠。
- browser/Chromium smoke 全綠。
- diff / secret scan 完成。
- `PROJECT_HANDOFF.md` 更新。
