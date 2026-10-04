# GitHub Repository 設定與公開邊界

SWSI 的 GitHub repository 可以是 Private，也可以在完成公開前安全稽核後轉為 Public。

**Public repository 不等於公開 production secrets、私人備份或使用者資料。**

## 建議原則

### 可以放在 repository

- SWSI 原始碼
- deterministic tests / QA contracts
- 題庫與官方來源的非敏感 provenance metadata
- 架構、測試、貢獻與公開維運文件
- 不含秘密值的環境變數名稱與設定範例

### 不得 commit

- `.env` / `.env.*` 的真實內容
- Supabase service-role key
- GitHub / Netlify / Cloudflare / AI provider token
- password、MFA / recovery code
- private backup encryption identity
- plaintext private database dump
- private user / admin data
- provider account recovery material

## Public 前必要步驟

Public 前依 `docs/PUBLIC_REPOSITORY_READINESS_20261004.md` 與 Issue #330 完成至少：

1. 完整 Git history secret scan。
2. GitHub Actions 歷史 logs / artifacts 稽核。
3. Git commit author/committer Email privacy 稽核。
4. ops 文件 public/private boundary 盤點。
5. 明確決定 SWSI-authored code license。
6. Public 後立即設定 `main` ruleset / branch protection 與可用的 security features。

在上述 P0 尚未完成前，不要只因目前 main 看起來乾淨就直接切 Public。

## 備份原則

至少保留多份彼此獨立的復原來源。GitHub repository 本身不是 private mutable production data 的備份位置。

私密 Supabase 備份依 `docs/SUPABASE_FREE_TIER_PRIVATE_BACKUP.md` 的 local-only / encrypted 邊界處理；真實備份檔與解密身分不得進 Git。

## Visibility 與 License 是兩件事

Repository 設為 Public，只代表任何人可瀏覽公開 repository 內容；不代表維護者已自動選擇 MIT、Apache-2.0 或其他開源授權。

若要宣稱 SWSI 為 open source，必須另外明確加入適用於 **SWSI-authored code** 的授權，並且不要把第三方或官方來源材料錯誤宣稱為 SWSI 自有著作。
