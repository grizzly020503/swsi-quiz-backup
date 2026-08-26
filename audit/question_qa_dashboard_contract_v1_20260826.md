# Question QA Dashboard Contract V1

日期：2026-08-26
狀態：`admin data contract / non-production`

## 目的

後台首頁不應下載完整題庫、完整解析或全部 audit history 才能知道「現在有沒有問題」。

`build_question_qa_dashboard.py` 將完整 unified QA report 壓縮成只包含：

- 考次健康度
- Official Core 通過／警告／阻擋數
- Enrichment 通過／警告／阻擋數
- 真正需要人處理的 anomaly queue
- 自動生成 backlog 統計
- legal watch 狀態

完整題目內容只在管理者點入單題時再載入。

---

# 115-2 實際 dashboard baseline

CI `Unified Question QA #7` 已驗證：

```json
{
  "health": "healthy",
  "official_health_pct": 100.0,
  "official_core": {
    "total": 210,
    "passed": 210,
    "needs_review": 0,
    "blocked": 0,
    "release_ready": true
  },
  "human_queue": {
    "total": 0,
    "blocked": 0,
    "needs_review": 0,
    "items": []
  },
  "generation_backlog": {
    "total": 185,
    "by_kind": {
      "essay": 10,
      "mcq": 175
    },
    "ready_by_kind": {
      "mcq": 25
    }
  }
}
```

分科 generation backlog：

- 人類行為與社會環境：17
- 社會工作：42
- 社會工作直接服務：42
- 社會工作研究方法：42
- 社會政策與社會立法：42

這裡的 185 是機器生成／補解析工作，不是人工待辦。

---

# 後台 UI 建議只依賴這份 contract

## 首頁卡片

```text
115-2 題庫健康度       100%
Official Core          210 / 210 passed
需要人工處理           0
自動生成待完成         185
可發布                 是
```

## 只有 human_queue > 0 才顯示警示清單

每個 action item 僅需：

- id
- kind
- subject
- qno
- official_status
- enrichment_status
- risk
- reasons[]

不在首頁 payload 放：

- 完整題幹
- A/B/C/D
- 完整解析
- 申論 guide
- 全部歷史 audit log

管理者點該 ID 後再向題庫／audit endpoint 取得詳情。

---

# 擴充原則

未來 50,000 題也不改首頁 contract。

首頁永遠只載：

1. 每個考次的 aggregate counts。
2. 未解決 anomaly queue。
3. generation backlog aggregate。

舊的已解決 audit event 應進歷史查詢，不進預設首頁 payload。

因此資料庫題數與後台首頁重量不需要線性成長。

---

# 安全與發布邊界

- 本 contract 不直接觸發 Netlify 或 Cloudflare 部署。
- `generation_backlog` 不阻擋 Official Core release。
- `blocked > 0` 才阻擋官方核心發布。
- `needs_review` 只呈現真正未解決的人工作業。
- current legal watch 只有顯式 current-intake mode 才能清 review；歷史題不可使用。

這份 contract 是之後真正製作管理後台 UI 時的資料接口基準。
