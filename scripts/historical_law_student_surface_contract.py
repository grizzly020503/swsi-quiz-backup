#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "monthly_patch_parts" / "86.law-trust-ui.part"
REGISTRY_PATH = ROOT / "data" / "historical_law_verified_priority10.v1.json"

ui = UI_PATH.read_text(encoding="utf-8")
registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

assert registry.get("schema_version") == 1
records = registry.get("records") or []
assert len(records) == registry.get("verified_record_count") == registry.get("historical_version_checked_count")
assert len(records) >= 1

match = re.search(r"var HISTORICAL_VERIFIED=(\{.*?\});\n\n  function H", ui, flags=re.S)
assert match, "historical runtime map missing from law trust owner"
embedded = json.loads(match.group(1))

expected = {}
for row in records:
    qid = str(row.get("question_id") or "").strip()
    assert qid and qid not in expected
    assert row.get("historical_version_checked") is True
    assert row.get("verification_level") == "machine_verified_historical_v1"
    version = row.get("selected_version") or {}
    expected[qid] = {
        "law_name": row.get("law_name"),
        "exam_code": row.get("exam_code"),
        "article": row.get("article"),
        "historical_version_checked": True,
        "verification_level": "machine_verified_historical_v1",
        "selected_version": {
            "version_date": version.get("version_date"),
            "effective_date": version.get("effective_date"),
            "url": version.get("url"),
        },
        "official_history_url": row.get("official_history_url"),
        "exam_date_source_url": row.get("exam_date_source_url"),
    }

assert embedded == expected, "student runtime historical-law map drifted from verified registry"
assert len(embedded) == 13, f"expected current verified registry size 13, got {len(embedded)}"

for qid, row in embedded.items():
    for key in ("law_name", "exam_code", "article", "verification_level"):
        assert str(row.get(key) or "").strip(), (qid, key)
    for url in (
        (row.get("selected_version") or {}).get("url"),
        row.get("official_history_url"),
        row.get("exam_date_source_url"),
    ):
        assert isinstance(url, str) and url.startswith("https://"), (qid, url)

# Student UI must fail closed: only the exact verified level + historical flag may surface.
assert "x.historical_version_checked!==true" in ui
assert "x.verification_level!=='machine_verified_historical_v1'" in ui
assert "rec.historical_version_checked!==true" in ui
assert "rec.verification_level!=='machine_verified_historical_v1'" in ui

# The UI explains the boundary instead of claiming official answer verification.
for marker in (
    "考試當時法規版本已核對",
    "機器驗證 metadata",
    "不是考選部官方解析",
    "不用 2026 現行法硬證明舊題",
    "考試時點法規 ↗",
    "法規沿革 ↗",
    "考試日期 ↗",
):
    assert marker in ui, marker

# Keep the derived surface compact and privacy-safe: no historical full text/hash mirror and no new network/storage path.
for forbidden in (
    "historical_article_sha256",
    "historical_semantic",
    "verification_basis",
    "fetch(",
    "localStorage.setItem",
    "sessionStorage.setItem",
):
    assert forbidden not in ui, f"unexpected historical-law student-surface payload/side effect: {forbidden}"

# Reuse the existing law-trust runtime owner instead of adding another monthly_patch part.
assert "window.SWSI_HISTORICAL_LAW_TRUST" in ui
assert "decorateHistoricalQuestionTrust" in ui
assert "swsi-answer-trust" in ui

print(
    "HISTORICAL LAW STUDENT SURFACE CONTRACT OK: "
    f"{len(embedded)} verified records exactly mirror the registry and fail closed in student UI"
)
