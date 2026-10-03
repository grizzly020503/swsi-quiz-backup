#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "monthly_patch_parts" / "00.part").read_text(encoding="utf-8")
LOCK = (ROOT / "monthly_patch_parts" / "zzzz_product_v1_lock.part").read_text(encoding="utf-8")
LAW_UI = (ROOT / "monthly_patch_parts" / "86.law-trust-ui.part").read_text(encoding="utf-8")
THEORY_UI = (ROOT / "monthly_patch_parts" / "88.theory-trust-ui.part").read_text(encoding="utf-8")

# Question trust UI must stay in the existing product owner.
assert "function addQuestionTrust(exp,item)" in LOCK
assert "swsi-answer-trust" in LOCK
assert "資料可信度" in LOCK

# 00.part is the canonical question normalization/cache owner. Official source and
# analysis trust metadata must survive CDN/Supabase -> normalize -> legacy cache.
required_assignments = (
    "q.source_exam_code = (r && r.source_exam_code) || '';",
    "q.source_url = (r && r.source_url) || '';",
    "q.analysis_status = (r && r.analysis_status) || '';",
    "q.legal_status = (r && r.legal_status) || '';",
    "q.legal_checked_at = (r && r.legal_checked_at) || null;",
    "q.legal_note = (r && r.legal_note) || '';",
    "q.legal_source_url = (r && r.legal_source_url) || '';",
)
for line in required_assignments:
    assert line in CORE, f"normalize trust metadata passthrough missing: {line}"
assert "source_exam_code:q.source_exam_code,source_url:q.source_url,analysis_status:q.analysis_status" in CORE

# Official exam data and SWSI enrichment must stay visibly distinct in student language.
assert "官方題目／答案" in LOCK
assert "平台解析・已通過基本檢查" in LOCK
assert "題目、選項、官方答案與特殊給分以考選部資料為準" in LOCK
assert "SWSI 另外整理解析與延伸內容" in LOCK

# `ready` is not human verification. Keep the boundary without exposing QA jargon.
assert "這份解析已通過目前的自動與結構檢查，不等於逐題人工核對" in LOCK
assert "不是考選部官方解析" in LOCK
assert "平台解析・待複核" in LOCK
assert "平台解析・處理中" in LOCK

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

print("QUESTION TRUST LABELS CONTRACT OK: official data, platform checks, metadata transport, and legal review states stay distinct in plain student language")
