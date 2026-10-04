# SWSI Maintenance Guide

本文件整理 SWSI 長期維運真正需要保留的規則。它面向維運者、貢獻者與自動化工具，不綁定任何單一 AI 供應商或聊天 session。

## 1. 先確認真實狀態

開始任何修改前，先看最新 `main`、open Issue / PR、相關 workflow、deployment 與 production evidence。

不要依賴舊 SHA、舊聊天摘要或 timestamped 文件推測現在狀態。若文件與 live state 衝突，以 live state、較新的 maintainer decision 與可驗證 evidence 為準。

## 2. Official Core 與 Enrichment 分層

Official Core 包含官方題目、選項、答案、`accepted_answers`、`grading_mode` 與官方申論題。

Enrichment 包含解析、分類、topic、keywords、理論／法規關聯、申論 guide、時事關聯、風險排序與其他學習層資料。

規則：

- Official Core 不因模型推論或 heuristic 自動改寫。
- Official Core 疑點先留 evidence、進 review，不直接猜答案。
- generated metadata 不能反過來當成官方來源。
- enrichment 可自動產生，但必須可追溯、可重跑、可降級、可 review。

## 3. 歷史法規

歷史考題使用考試當時的法規與政策版本。

- 不得用現行法直接證明舊題。
- 法規名稱命中不代表已確認直接法源。
- provenance 應能追到來源、版本與必要時的條文層級。
- source mismatch / outage / ambiguity 應 retry、review 或 quarantine，不得判定成功。

## 4. 資料品質

「有資料」不等於「已驗證」。

高風險優先檢查：

- 反向題與否定詞
- 年份、比例、期限、金額、年齡、例外規定
- 歷史法規版本
- 容易混淆的理論
- 模板化或只重述題幹的解析
- 來源不明或 metadata 自我引用

自動規則需要正例與反例 regression。不要為了 coverage 降低 precision。

## 5. 時事與命題關聯

時事庫不是新聞收藏庫。

- 重大社工事件即使沒有修法，仍可能具有專業與申論價值。
- 不能只因人物職稱或單一關鍵字就納入。
- 同事件多篇報導應增加 evidence，而不是灌成多個趨勢事件。
- primary / supporting subjects 要分開。
- 時事到歷屆題的關聯要保留 evidence 與強度。
- 低信心推論不可在學生端包裝成命題保證。

## 6. 自動維運方向

目標流程：

```text
官方 / 公開來源
  ↓
自動抓取
  ↓
結構與來源驗證
  ↓
Deterministic QA / Provenance
  ↓
高風險與 unresolved queue
  ↓
輔助 review
  ↓
Human / Quarantine（少數 conflict）
  ↓
版本化結果 + Health Report
```

自動化的目的，是讓人只處理真正困難的例外，不是取消 evidence gate。

## 7. GitHub Actions 與成本

能在本機或 deterministic script 驗證的工作，先在本機完成。避免為每個小 commit 重跑高成本 workflow。

CI failure 要先分類原因：code、data、quota、runner、permission、configuration 或 provider outage。不要為了讓燈變綠而刪 gate。

## 8. 安全與 private boundary

Public source 可以公開架構與一般維運方法，但不得公開：

- credential value
- service-role key
- provider token
- password
- MFA / recovery code
- private backup key / identity
- plaintext private database dump
- raw private user / admin payload
- provider account takeover / recovery material

環境變數名稱可以文件化，值不可以。

## 9. 文件治理

Repository 根目錄只保留真正的專案入口與長期文件。

新的單次工作紀錄應放在 Issue / PR / audit；不要再新增：

- `CLAUDE.md` / `GEMINI.md` 類模型專屬 prompt
- `AI_PROJECT_CONTEXT.md` 類聊天接管稿
- `PROJECT_DIARY_YYYY-MM-DD.md` 類施工日誌
- 多份互相覆蓋的 handoff snapshot

若某份歷史 audit 有保留價值，放在 `docs/` 或 `audit/` 並清楚標示日期與 snapshot 性質。

## 10. Merge / release

高風險變更（grading、schema、auth、security、production data、release）需要比一般 UI 修改更強的 evidence。

未取得明確 maintainer 授權，不執行 merge、production deploy、history rewrite 或不可逆資料操作。
