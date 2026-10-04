# 2026-10-03 法規引用輔助欄位收尾

## 為什麼需要第二批

PR #325 / migration `correct_law_citation_metadata` 已把 12 題主要 `law / exp_why / extension` 條號校正，但正式 shard 抽查時發現部分學生可見的 `exp_trap` / `mnemonic` 仍保留舊條號。

因此本批不是新增內容，也不是改官方答案，而是把同一組 citation correction 完整傳播到所有會顯示給學生的輔助解析欄位。

## 精準範圍

共 10 題：

- `SP104-1-28`：`exp_trap` §7 → §6
- `SP106-1-17`：`exp_trap` / `mnemonic` §3 → §2
- `SP107-1-34`：`exp_trap` / `mnemonic` §7 → §6
- `SP108-2-34`：`mnemonic` §7 → §6
- `SP109-2-35`：`exp_trap` / `mnemonic` §7 → §6
- `SP110-1-34`：`exp_trap` / `mnemonic` §3 → §2
- `SP110-1-37`：`mnemonic` §13 → §11
- `SP111-1-35`：`exp_trap` / `mnemonic` §3 → §2
- `SP111-2-35`：`mnemonic` §15 → §13-1
- `SP114-1-35`：`exp_trap` / `mnemonic` §7 → §6

`topic / keywords / exp_others` 已唯讀檢查，未發現同一批舊條號殘留。

## 安全邊界

- migration 以目前 production 的舊 `exp_trap / mnemonic` 完整字串作 fail-closed precondition；任何 drift 會拒絕整批套用。
- 只更新 `exp_trap / mnemonic`。
- 不修改 Official Core、`law / exp_why / extension`、analysis/legal trust state 或歷史法規 verified registry。
- 上線後必須由正式 question-shard builder 重建，不直接編輯 CDN JSON。

## Cloudflare 發布狀態背景

前一批 shard rebuild 已成功產生並 commit dataset revision `2da01c3a712e3e73758f`；attempt 5 的 production smoke 失敗原因是 Cloudflare 在 30 次、約 150 秒等待期間仍回舊 revision `84249302b9562897ed6d`。CORS/cache header 正常，因此該紅燈屬 production revision propagation timeout，不能誤判成 shard build 或 Official Core 驗證失敗。
