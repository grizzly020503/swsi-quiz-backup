# 官方 PDF 批次核對流程

單一入口串接既有 Official Core、全文完整性、修正證據與 PDF release gate，依原始 PDF 分組準備待審資料，並重建已有證據的 43 題修正資料候選。不會猜測改題、修改正式答案、寫入資料庫、部署或操作備援站。

## 本機整批執行

```bash
python scripts/official_pdf_batch_pipeline.py --out /tmp/swsi-pdf-batch --evidence-dir /path/to/official/questions
```

只需要 Python 標準函式庫、Git 歷史與 Poppler `pdftotext`。原始 PDF 檔名依來源 registry，例如 `107110-107-0606.pdf`；內容必須符合既有官方 SHA256。沒有原卷時可明確指定 `--download`，只允許官方 MOEX HTTPS 檔案端點，限制單檔大小、下載與解析逾時。來源失敗保留錯誤，不計為完成。

`--batch-size 25 --max-batches 4 --max-sources 12` 可限制單次工作量。再次執行相同命令即從已驗證的逐筆 checkpoint 接續；輸入/程式變更會建立新命名空間，不混用舊結果。每次仍執行必要驗證；檢查點不能跳過品質門檻。進行中的程序持有互斥鎖；同一工作目錄不允許重疊執行。輸出必須位於 checkout 之外。

## 實際產物與完成定義

- `latest.json`、各輸入指紋目錄的 `summary.json`：實際準備、重用、失敗與尚未處理數字。
- `checkpoint.json`：逐筆更新；中斷後保留已完成記錄。
- `inputs.json`、`checks.json`、`check-*.log`、`full-corpus.json`：輸入與驗證證據。
- `pdfs/`：官方 hash 符合的原卷。
- `packets/`：原始差異、當前完整題目、PDF layout 文字、來源/雜湊；固定保持待查及未人工核准。
- `verified-candidate/`：從已提交且 source-bound 的修正 recipe 重建資料檔，逐檔比對已驗證 SHA256；保留官方給分規則。

「資料包準備完成」不等於「題目已校正」。新差異沒有足夠證據時保持 review；更新題目仍須增加精確官方來源、修改前後、校驗鎖、驗證與 PR 審核。原有預設 PDF/AI release gates 不被此流程取代，440 筆未審不能因此歸零。此版本只重建已證實的修正，不會將新差異直接當成可發布更正。

## GitHub 背景執行

`Official PDF Batch Pipeline` 在相關 PR 更新時自動執行，亦提供手動入口及每日排程定義。**GitHub 每日排程須待 workflow 合併到預設分支才會生效**；PR 上的排程不是已啟用的正式背景任務。

工作有唯讀 repository 權限、同分支互斥及15分鐘上限。每次最多4批、12份來源 PDF；使用輸入指紋 cache 接續，審核資料包與候選產物保存14天（原始 PDF 僅存 cache，避免重複佔用 artifact 額度）。Cache 可被 GitHub 回收；需要長期保存的重要審核結果仍應提交原有 PR 的正式證據檔。沒有 API key、付費模型或 production credential，也沒有部署與 backup workflow 呼叫。來源不可用時維持失敗狀態，已完成的檢查點仍保存。
