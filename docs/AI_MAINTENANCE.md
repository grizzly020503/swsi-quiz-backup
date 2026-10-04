# SWSI AI 維運與接手規則

> 這份文件是給 ChatGPT、Codex、Claude、GitHub Copilot、其他 AI agent 與未來維運者的長期接手入口。
>
> 目的：把散落在歷史 handoff、audit、queue、patch 裡真正需要長期保存的規則集中在一處，避免下一個 AI 重新猜架構、重做已完成工作，或把臨時分析當成 production 事實。

最後整理：2026-10-04

---

## 1. 權威順序

開始任何工作前，依下列順序重新確認真實狀態：

1. 遠端 `main` 最新 HEAD、open PR / Issue、最新 Actions / deploy 狀態。
2. `README.md`：產品定位與公開首頁。
3. 本文件：AI 維運邊界與長期規則。
4. `PROJECT_HANDOFF.md`：較細的工程脈絡；若內容與遠端現況衝突，以遠端現況與較新的 owner decision 為準。
5. 專項 Issue / audit / workflow / source code。

**不要假設聊天紀錄、舊 SHA、舊部署文件或 timestamped audit 仍代表現在。**

---

## 2. 平台長期方向

SWSI 是社工師國考免費學習平台。核心不是持續堆功能，而是：

- 官方題庫與答案保持可信；
- 解析、法規、理論、時事與歷屆關聯逐步提高資料品質；
- 前台做減法，後台做自動化；
- 讓新考次、法規變動、資料缺口與異常盡可能由程式自動發現；
- 人工只處理 evidence conflict、來源異常、高風險或模型無法可靠判定的少數案例。

新增功能前先問：它是否明顯改善「刷題、複習、申論」或「資料可信度 / 自動維運」？如果不是，優先不做。

---

## 3. Official Core 是不可隨意修改的邊界

Official Core 包含考選部官方題目、選項、答案、accepted answers、grading mode 與官方申論題本體。

### AI 可以做

- 解析、分類、topic、keywords；
- 理論 / 法規學習關聯；
- 申論 guide 與學習提示；
- 時事與歷屆考點關聯；
- review priority / risk signal；
- evidence-bound shadow review。

### AI 不可以做

- 自行改寫官方題目、選項、答案或 grading mode；
- 因為 AI 推論與官方答案不同就直接修改 Official Core；
- 用 generated metadata 反過來當作官方證據；
- 直接從 AI review 跳過 deterministic gate 寫入 verified registry。

遇到 Official Core 疑點：**標記、留 evidence、進 review；不要直接修。**

---

## 4. 資料品質原則

### 4.1 「有資料」不等於「資料已驗證」

- `analysis_status=ready` 不代表逐題人工 verified。
- 有解析不代表解析一定正確。
- 有 `law` 欄位不代表該法規就是題目的直接法源。
- 有新聞來源不代表事件與國考有高關聯。
- 關鍵字命中不等於語意理解。

### 4.2 高風險優先，不把 signal 當 error count

歷史 4,600 題深度掃描曾產生大量 heuristic signal；其中高風險 queue 的用途是**排序 review 優先順序**，不是宣稱那些題目已經錯。

任何後續 AI 若看到 `legacy_4600_high_risk_queue_*`：

- 不可把 queue row 數當成錯題數；
- 不可把舊 4,600 題掃描宣稱成目前 4,800 題 certification；
- 可將它用作 regression、calibration、priority seed；
- 對 current corpus 的結論必須重新以 current 24 shards / production source 為準。

### 4.3 反向題、法規題、數字 / 日期題優先高風險處理

至少特別檢查：

- 「何者錯誤 / 不正確 / 非」等 negative semantics；
- 正確選項與 distractor explanation 是否對應；
- 法規歷史版本與現行版本是否混用；
- 年份、金額、比例、期限、年齡與例外規定；
- AI 解析是否只是題幹重述或模板空話。

---

## 5. 歷史法規 629 題：唯一正確的擴充方向

### 5.1 不要把 priority10 當成全體

既有 historical-law production pipeline 曾以 priority10 / 約 85 題作為高信賴 regression slice；它不是完整 104–115 法規題範圍。

Owner 追蹤的 legal-ready mother scope 為 629 題。擴充時應**泛化輸入與 evidence contract**，不要另做第二套 verifier，也不要直接把 priority10 換成一份由 AI 生成的法規清單。

### 5.2 Provenance 分級

對 law identity 至少區分：

1. 法規名稱明確存在於官方題目 / 選項；
2. 已有 deterministic evidence 支撐；
3. 只有 generated `law` metadata 推論；
4. generated law 無法 canonicalize；
5. 無法規訊號。

規則：

- (1) / (2) 可成為 historical pipeline seed，但仍不代表 `direct_legal_basis`；
- (3) 只能進 independent source confirmation / AI shadow review；
- (4) quarantine；
- (5) out of scope；
- generated-only metadata **不得因為先前 AI 寫過就升格成 evidence**。

### 5.3 不要硬湊 629

如果 full-scope pipeline 與 owner-tracked scope 無法 reconciliation：

- 停止；
- 說明 discrepancy；
- 找 provenance / scope 原因；
- **不得降低 evidence 規則只為了把數字湊成 629。**

---

## 6. Historical Law deterministic chain 優先於 AI

既有 precedence 必須維持：

1. deterministic Stage 2–6 evidence chain；
2. 已存在的 evidence adjudication；
3. AI Shadow review 只處理 unresolved / ambiguous lanes；
4. human / quarantine 處理 conflict。

AI 是 support layer，不是平行 verifier。

### AI Shadow 不可跨越的界線

- 不看 Official answer / grading fields 作為判定依據；
- 不直接寫 verified registry；
- 不直接跳 Stage 7；
- 不降低 Stage 6 threshold 以增加 coverage；
- source outage / mismatch = retry 或 quarantine，不能算 success；
- model / prompt / parser 重大變更時，calibration 必須重置回 Shadow。

已經 evidence-adjudicated 的案例，不要重新當普通 backlog；最多作為 hidden-label calibration control。

---

## 7. Guardian → durable review 必須保留 evidence metadata

如果修改 historical-law Guardian / review queue，不可只傳 `route` 與 `confidence`。

至少保留足以重建判定脈絡的 compact evidence，例如：

- Stage 3 route / confidence / reason；
- suggested article；
- official article source URL；
- metadata articles；
- top candidate articles / scores；
- historical article hash / source identity；
- Stage 6 selected historical version URL；
- expected rank；
- top / second article、margin 與 top candidates。

目的：讓 durable review、AI Shadow、human review 能看到 evidence，而不是只看到模型或前一階段的結論。

---

## 8. 時事 / 五科 / 歷屆題關聯規則

- 時事庫不是新聞收藏庫。
- 重大社工事件即使沒有修法，也可能具有高專業 / 申論價值。
- 不能因「人物職稱是社工」就自動納入。
- 同一事件多篇報導增加 evidence，不等於多個趨勢事件。
- 社會工作管理是上層架構，不是第六科。
- 每個事件應區分 primary subjects 與 supporting subjects。
- 研究方法只有在事件真的涉及調查、研究、統計、評估 evidence 時才升主科。
- 時事 → 歷屆題關聯需保留 evidence 與強度，不可只靠共字串。

低信心自動推論在學生端必須明確標示，不可包裝成確定事實或命題保證。

---

## 9. 自動化與 Agent 的目標形態

長期希望形成：

```text
官方 / 公開來源
  ↓
自動抓取
  ↓
結構與來源驗證
  ↓
deterministic QA / provenance
  ↓
高風險與 unresolved queue
  ↓
AI Shadow / evidence review
  ↓
human / quarantine（只處理少數 conflict）
  ↓
版本化結果 + health report
```

Agent 應該減少人工「逐題全部重看」，不是取消 evidence gate。

---

## 10. GitHub Actions / CI 判讀

GitHub Actions 曾出現 runner / quota 導致的：

- `0 steps`；
- `steps=null`；
- 無 job logs；
- workflow 立即紅燈。

這種情況**不是 code failure**。沒有實際執行步驟，就不能把紅燈當測試結果，也不要用「一直 rerun 看看」處理。

真正的 code / scanner failure 必須有實際 job steps、logs 或本機可重現證據。

---

## 11. Public Repository 安全邊界

公開 GitHub 前，優先以 Issue `#330` 作為 Public Readiness 主追蹤。

基本規則：

- full-history scanner 未真正 PASS 前，不應把 repository 切 Public；
- scanner finding 要分辨真 credential、public credential / anon key、test fixture、opaque archive、identity review；
- 發現真 credential 時先 revoke / rotate，再談 history remediation；
- 不因一般歷史姓名 / Email attribution 就輕率做整庫 history rewrite；
- 不把刪 stale branch 當成清除 main ancestry 的替代方案；
- 不把 `service_role`、provider token、password、internal key 寫入 repo / docs / artifact。

Public 後再依 GitHub 實際能力啟用 branch protection / ruleset、secret scanning / push protection、Dependabot 與 vulnerability reporting。

---

## 12. 新 AI 接手 Checklist

開始前：

- [ ] 重新讀最新 main HEAD。
- [ ] 讀 README + 本文件。
- [ ] 找到本次任務對應的 owner Issue / PR。
- [ ] 確認 production / deploy / Git Actions 限制。
- [ ] 區分 Official Core、generated enrichment、review signal、verified evidence。
- [ ] 確認是不是已有現成 pipeline / script，避免平行重做。

工作中：

- [ ] 小範圍、可回滾、先測試。
- [ ] evidence / provenance 不因 coverage 壓力而降級。
- [ ] 不把 heuristic signal 當已證實錯誤。
- [ ] 不把 AI 結論當 source of truth。
- [ ] 不在學生端新增重複入口或無必要複雜度。

完成後：

- [ ] 說明改了什麼、沒改什麼。
- [ ] 記錄驗證方式與限制。
- [ ] 若狀態有長期影響，更新對應 Issue / 本文件，而不是新增一份臨時工作日誌。

---

## 13. 文件治理

README 應保持像公開專案首頁，不記流水帳。

長期規則放本文件；具體任務與進度放 GitHub Issues；程式 contract 放測試 / schema / source code。

以下類型通常不應再新增為長期 repo 文件：

- `WORK_HANDOFF_YYYYMMDD.md`；
- 「今天做到哪」型日誌；
- 一次性 prompt / AI 工作紀錄；
- 可由 Issue / commit / test 重建的暫時狀態快照。

需要保留的歷史 audit 可存在 `docs/` / `audit/`，但應清楚標示日期與 snapshot 性質，避免未來 AI 把舊狀態當現況。
