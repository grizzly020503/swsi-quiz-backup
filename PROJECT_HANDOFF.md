# SWSI Project Status Pointer

> 此檔僅為舊工具與舊文件相容而保留。它不再作為長篇聊天交接、模型 prompt 或每日施工日誌。

## 現況來源

目前專案狀態請依下列順序確認：

1. 最新 `main`
2. Open Issues / Pull Requests
3. 實際 GitHub Actions / deployment 狀態
4. `README.md`
5. `docs/MAINTENANCE.md`
6. `ARCHITECTURE.md`、`TESTING.md`、`SECURITY.md`
7. 與任務直接相關的 audit / source / test

固定 SHA、舊聊天摘要與本檔歷史版本都可能過時。

## 長期原則

- Official Core 與平台 enrichment 必須分層。
- 歷史法規使用考試當時版本，不以現行法倒灌舊題。
- deterministic evidence / provenance 優先於生成式判斷。
- 前台做減法，後台做自動化。
- 低信心或衝突結果進 review / quarantine。
- 不把 secret、private backup、private user/admin payload 放進 repository。

## 進度紀錄方式

新的任務、決策、blocker 與驗證結果應記錄在 GitHub Issues / Pull Requests 或對應 audit 文件，不再把單次 AI session 的工作紀錄持續堆進本檔。

Public readiness 與公開前安全事項以 GitHub 對應 Issue 的最新狀態為準。
