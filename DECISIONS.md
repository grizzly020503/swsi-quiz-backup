# SWSI Engineering Decisions

本檔只記錄會影響多個模組、容易被下一個 AI 重新猜錯的決策。新決策請追加，不要只留在聊天裡。

## D-001 GitHub 是跨 AI source of truth

**決策：** 專案狀態以 repo 文件、commit、CI、production metadata 為準，不以任何單一聊天或 Agent memory 為準。

**原因：** ChatGPT / Claude / Gemini / Codex / Work 等工作階段會中斷，只有持久化到 repo 的資訊才能被下一個接手者可靠看到。

---

## D-002 特殊給分一律 fail closed

`grading_mode` 合法值：
- `standard`
- `all_credit`
- `any_answer`

缺失或矛盾時不得從題目 ID、`answer='一律給分'`、`送分` 等文字推理模式。

**原因：** heuristic 會掩蓋 upstream metadata 漂移，且可能把未作答是否得分判錯。

---

## D-003 所有作答入口共用同一 grading contract

普通刷題、計時模擬考、錯題、複習、分數統計不得各自維護一套判題邏輯。

**原因：** 歷史上模擬考仍使用 legacy `picked === q.answer`，造成多答案與特殊給分不一致。

---

## D-004 歷史題採考試當時版本

歷史法規、政策、制度題必須使用當次考試時點可成立的內容。

禁止：
- 用現在法條回填舊考題。
- 把 2026 長照3.0 等後來政策塞進早期考題。
- 用 current legal watch 的「目前沒變」直接驗證歷史版本。

---

## D-005 題庫發布採 Official Core / Enrichment 分離

Official Core 完整性通過後可以發布；解析、申論 guide、法規說明等加值內容 pending 不應讓 200+ 官方題全部塞進人工 queue。

人工只處理真正異常與高風險內容。

---

## D-006 新考次 QA 採 exception-based review

正常題自動通過；只有：
- 特殊給分
- schema 不一致
- 官方更正
- 法規／政策高風險
- parser 異常
- content coverage 異常

才進人工 queue。

**目的：** 題庫長到幾萬題仍可維護。

---

## D-007 CDN shard 必須做真實 SHA-256 驗證

不能只讀 manifest hash 再把預期值寫入 cache。下載內容 bytes 必須計算 hash 並與 manifest 比對。

不匹配即拒絕使用／保存該 shard。

---

## D-008 Service Worker 不得長期黏住判題與內容檔

`monthly_patch.js`、`essay_guides.js`、mutable manifest 必須採 network-first 更新策略。

跨網域題庫 shard、Supabase、AI API 不由 Service Worker 攔截。

---

## D-009 申論 guide 一題一份唯一 key

`essay_guides.js` 不允許多份同 ID 定義靠 JavaScript 靜默覆蓋。

長期採 registry + builder，deploy artifact 必須唯一 key。

---

## D-010 不以刪除 gate 換 CI 綠燈

測試失敗時先判斷：
1. runtime 真 bug；
2. test 過期；
3. contract 寫錯。

不可直接移除安全檢查、降低 grading 標準、忽略失敗來換綠燈。

---

## D-011 長時間 Agent 要做 checkpoint commits

一組獨立修正通過 regression 後立即 commit，再做下一組。

**原因：** Work / Agent 可能因額度或工作時間中斷；數小時本地成果若未 commit，其他 AI 無法接手。

---

## D-012 正式發布與開發分離

修復可在 branch + preview 完成；`main` merge 與 production deploy 是獨立決策。

沒有使用者明確授權，不得自動 merge main 或正式 Netlify deploy。
