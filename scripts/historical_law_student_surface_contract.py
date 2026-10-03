#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from historical_law_student_surface_sync import build_student_map, extract_embedded

ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "monthly_patch_parts" / "86.law-trust-ui.part"

ui = UI_PATH.read_text(encoding="utf-8")
embedded = extract_embedded(ui)
expected = build_student_map()

assert embedded == expected, "student runtime historical-law map drifted from combined verified evidence"
assert len(embedded) == 19, f"expected current combined verified size 19, got {len(embedded)}"
levels = [row.get("verification_level") for row in embedded.values()]
assert levels.count("machine_verified_historical_v1") == 13
assert levels.count("evidence_adjudicated_historical_v1") == 6

for qid, row in embedded.items():
    assert row.get("historical_version_checked") is True, qid
    assert row.get("verification_level") in {
        "machine_verified_historical_v1",
        "evidence_adjudicated_historical_v1",
    }, qid
    for key in ("law_name", "exam_code", "article", "verification_level"):
        assert str(row.get(key) or "").strip(), (qid, key)
    for url in (
        (row.get("selected_version") or {}).get("url"),
        row.get("official_history_url"),
        row.get("exam_date_source_url"),
    ):
        assert isinstance(url, str) and url.startswith("https://"), (qid, url)

# Student UI must fail closed: checked=true plus one of the two reviewed levels.
assert "x.historical_version_checked!==true" in ui
assert "historicalVerificationCopy" in ui
assert "machine_verified_historical_v1" in ui
assert "evidence_adjudicated_historical_v1" in ui
assert "return null" in ui
assert "rec.historical_version_checked!==true" in ui
assert "!historicalVerificationCopy(rec)" in ui

# Human wording must distinguish the evidence method without exposing internal level names.
for marker in (
    "考試當時法規版本已核對",
    "核對方式：規則驗證",
    "核對方式：官方證據交叉核對",
    "不是人工審查",
    "不是考選部官方解析",
    "不用現在的法規硬證明舊題",
    "考試時點法規 ↗",
    "法規沿革 ↗",
    "考試日期 ↗",
):
    assert marker in ui, marker

# Keep the derived surface compact and privacy-safe: no evidence internals/full text and no new network/storage path.
for forbidden in (
    "historical_article_sha256",
    "historical_semantic",
    "verification_basis",
    "evidence_adjudication",
    "fetch(",
    "localStorage.setItem",
    "sessionStorage.setItem",
):
    assert forbidden not in ui, f"unexpected historical-law student-surface payload/side effect: {forbidden}"

# Reuse the existing law-trust runtime owner instead of adding another monthly_patch part or global API.
assert "decorateHistoricalQuestionTrust" in ui
assert "swsi-answer-trust" in ui
assert "window.SWSI_HISTORICAL_LAW_TRUST" not in ui

print(
    "HISTORICAL LAW STUDENT SURFACE CONTRACT OK: "
    "19 verified records (13 rule-verified + 6 evidence-adjudicated) are compact, distinct, and fail closed"
)
