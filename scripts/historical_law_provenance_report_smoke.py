#!/usr/bin/env python3
"""Fail closed if the committed priority-law provenance report overstates trust."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data/historical_law_provenance_priority10.v1.json"
LINKS = ROOT / "data/law_question_links_priority10.v1.json"

allowed_statuses = {
    "article_resolution_required",
    "official_history_unavailable",
    "article_origin_review",
    "effective_date_review",
    "historical_text_required",
    "exam_date_required",
    "current_text_equals_exam_year_candidate",
}
protected_fields = {
    "official_answer", "answer", "accepted_answers", "grading_mode",
    "opt_a", "opt_b", "opt_c", "opt_d",
}

report = json.loads(REPORT.read_text(encoding="utf-8"))
links = json.loads(LINKS.read_text(encoding="utf-8"))
rows = report.get("questions") or []

# Identity is law + question, not question_id alone: one historical question is
# intentionally linked to two laws, so 86 mappings represent 85 unique questions.
expected_pairs = []
expected_ids = []
for card in links.get("cards") or []:
    law = card["law_name"]
    for row in card.get("questions") or []:
        expected_pairs.append((law, row["question_id"]))
        expected_ids.append(row["question_id"])
actual_pairs = [(r.get("law_name"), r.get("question_id")) for r in rows]

assert report.get("schema_version") == 1
assert report.get("question_count") == 86 == len(rows)
assert report.get("law_count") == 10
assert len(expected_pairs) == 86
assert len(set(expected_pairs)) == 86
assert Counter(actual_pairs) == Counter(expected_pairs)
assert len(set(expected_ids)) == 85
assert Counter(expected_ids)["SP104-2-10"] == 2
assert sum((report.get("status_counts") or {}).values()) == 86
assert set(report.get("status_counts") or {}) <= allowed_statuses
assert all(r.get("status") in allowed_statuses for r in rows)
assert all(r.get("historical_version_checked") is False for r in rows)
assert all(not (protected_fields & set(r)) for r in rows), "report must not duplicate protected official core"
assert all(r.get("official_history_url") for r in rows), "every priority-law row needs an official MOJ history URL"
assert all(r.get("law_name") for r in rows)

actual_counts = Counter(r["status"] for r in rows)
assert dict(sorted(actual_counts.items())) == report.get("status_counts")

laws = report.get("laws") or []
assert len(laws) == 10
assert sum(x.get("question_count", 0) for x in laws) == 86

# Source failures are observations, never proof about legal validity.
errors = report.get("law_fetch_errors") or []
assert report.get("law_fetch_error_count") == len(errors)
error_laws = {e.get("law_name") for e in errors}
for row in rows:
    if row.get("law_name") in error_laws:
        assert row.get("historical_version_checked") is False

# V1 baseline must remain conservative: candidates are not verified facts.
for row in rows:
    if row.get("eligible_for_historical_version_checked"):
        assert row.get("status") == "current_text_equals_exam_year_candidate"
        assert row.get("historical_version_checked") is False

print(
    "HISTORICAL LAW PROVENANCE REPORT CONTRACT OK:",
    report.get("status_counts"),
    "mappings=86 unique_questions=85 source_errors=",
    report.get("law_fetch_error_count"),
)
