#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = (ROOT / "monthly_patch_parts" / "zzzz_product_v1_lock.part").read_text(encoding="utf-8")
LAW_UI = (ROOT / "monthly_patch_parts" / "86.law-trust-ui.part").read_text(encoding="utf-8")
THEORY_UI = (ROOT / "monthly_patch_parts" / "88.theory-trust-ui.part").read_text(encoding="utf-8")

# Question trust UI must stay in the existing product owner, not another late runtime layer.
assert "function addQuestionTrust(exp,item)" in LOCK
assert "swsi-answer-trust" in LOCK
assert "題目來源與解析" in LOCK

# Official exam data and SWSI enrichment must stay visibly distinct in student language.
assert "考選部歷屆試題" in LOCK
assert "平台解析・已通過基本檢查" in LOCK
assert "題目、選項、官方答案與特殊給分以考選部資料為準" in LOCK
assert "SWSI 另外整理解析與延伸內容" in LOCK

# Official identity is determined by durable exam identity metadata, not by whether a
# clickable URL is currently present. Missing/invalid source_url may hide the link,
# but must never turn an official historical question into "SWSI 練習內容".
origin_fn = re.search(r"function questionOrigin\\(item\\)\\{(.*?)\\n  \\}", LOCK, re.S)
assert origin_fn, "questionOrigin() contract missing"
origin_body = origin_fn.group(1)
assert "source_exam_code" in origin_body
assert "'unknown'" in origin_body and "'practice'" in origin_body
assert "/^\\d{6}$/" in origin_body
assert "safeTrustHref(item.source_url)" not in origin_body
assert "appendTrustLink(body,'開啟官方題目來源',official?item.source_url:'');" in LOCK
assert "題目來源待確認" in LOCK
assert "平台自製練習題" in LOCK
assert "此題不是考選部歷屆題；題目與解析都屬 SWSI 學習內容。" not in LOCK

def question_origin_contract(source_exam_code="", source_url="", qtype="", item_id=""):
    kind = f"{qtype} {item_id}"
    if any(marker in kind for marker in ("時事", "預測", "自製")):
        return "practice"
    return "official" if re.fullmatch(r"[0-9]{6}", str(source_exam_code or "").strip()) else "unknown"

assert question_origin_contract("115100", "", "", "HBSE-115-2-001") == "official"
assert question_origin_contract("", "https://www.moex.gov.tw/example", "", "HBSE-115-2-001") == "unknown"
assert question_origin_contract("", "", "時事", "CURRENT-AFFAIRS-01") == "practice"
assert question_origin_contract("synthetic", "", "", "SWSI-LOCAL-01") == "unknown"
assert "q.source_url = (r && r.source_url) || '';" in (ROOT / "monthly_patch_parts" / "00.part").read_text(encoding="utf-8")
assert "q.analysis_status = (r && r.analysis_status) || '';" in (ROOT / "monthly_patch_parts" / "00.part").read_text(encoding="utf-8")

# `ready` is not human verification. Keep the boundary without exposing QA jargon.
assert "這份解析已通過目前的自動與結構檢查，不等於逐題人工核對" in LOCK
assert "不是考選部官方解析" in LOCK
assert "平台解析・待複核" in LOCK
assert "平台解析・處理中" in LOCK

# Missing analysis metadata uses neutral copy instead of a warning that could be
# misread as distrust of the official question itself.
assert "平台解析・SWSI 整理" in LOCK
assert "目前未顯示進一步核對狀態" in LOCK
assert "平台解析・核對狀態未標示" not in LOCK

# Student-visible trust copy must not require understanding maintainer vocabulary.
assert "平台解析・QA 已通過" not in LOCK
assert "屬 Official Core" not in LOCK
assert "歷屆題 Official Core" not in LOCK

# Legal labels reuse the existing database contract and never overclaim historical validity.
for status in ("verified_current", "changed", "unreviewed", "not_applicable"):
    assert f"status==='{status}'" in LOCK
assert "法規・現行來源已核對" in LOCK
assert "歷史考題，考試當時版本與後續修法仍須依歷史法規證據判讀" in LOCK
assert "法規・已偵測變動" in LOCK
assert "法規・待逐題複核" in LOCK

# Source links must remain HTTPS-only and external links stay noopener/noreferrer.
assert "function safeTrustHref(value)" in LOCK
assert "u.protocol==='https:'" in LOCK
assert "a.rel='noopener noreferrer'" in LOCK

# Existing law/theory trust semantics remain available; question labels must not replace them.
assert "✓ 官方來源已逐卡核對" in LAW_UI
assert "○ 已連結官方來源・摘要待逐卡複核" in LAW_UI
assert "✓ 理論內容已逐卡核對" in THEORY_UI
assert "△ 平台整理・待逐卡複核" in THEORY_UI
assert "理論卡不是考選部官方答案" in THEORY_UI

# Corpus contract must actually carry the statuses used by the UI.
seen_ready = False
seen_official = False
seen_legal = set()
for path in sorted((ROOT / "cdn" / "question-shards").glob("*.json")):
    if path.name == "manifest.json":
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    for row in payload.get("questions", []):
        if row.get("analysis_status") == "ready":
            seen_ready = True
        if row.get("source_exam_code") and str(row.get("source_url") or "").startswith("https://"):
            seen_official = True
        if row.get("legal_status"):
            seen_legal.add(str(row["legal_status"]))
assert seen_ready, "no ready analysis status found in corpus"
assert seen_official, "no official source metadata found in corpus"
assert "not_applicable" in seen_legal, "legal_status contract missing from corpus"

# Never introduce a positive claim that collapses platform checks into official/human verification.
# The required negative sentence "不是考選部官方解析" must remain allowed.
for forbidden in (
    "平台解析・人工已驗證",
    "平台解析＝官方解析",
    "平台解析=官方解析",
    "SWSI 官方解析",
    "ready = verified",
    "ready=verified",
):
    assert forbidden not in LOCK, f"misleading trust wording found: {forbidden}"

print("QUESTION TRUST LABELS CONTRACT OK: official identity, source-link availability, platform checks, and legal review states stay distinct")
