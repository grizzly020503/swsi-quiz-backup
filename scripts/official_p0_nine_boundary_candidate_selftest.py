#!/usr/bin/env python3
"""Review-only P0 next-question boundary evidence gate. NEVER publishes official core.

Run from repository root:
    python scripts/official_p0_nine_boundary_candidate_selftest.py

Verifies exact main-shard preimages and nine single-field correction proposals.
PDF page judgment and release approval are EXPLICITLY NOT automated.
"""
from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "audit/official_p0_nine_boundary_candidate_20261110.json"
SAFE_FIELDS = {"question", "opt_a", "opt_b", "opt_c", "opt_d"}
EXPECTED_IDS = {
    "SW-104-1-03", "SW-104-1-12", "SW-104-1-35",
    "SW-106-2-09", "SW-106-2-21", "SW-106-2-35",
    "SW-107-2-11", "SW-107-2-21", "SW-107-2-35",
}
SUFFIX_DIGITS = {
    "SW-104-1-03": "4", "SW-104-1-12": "5", "SW-104-1-35": "7",
    "SW-106-2-21": "5", "SW-106-2-35": "6", "SW-107-2-11": "4",
    "SW-107-2-21": "5", "SW-107-2-35": "6",
}


def verify() -> int:
    doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert doc["status"] == "DRAFT_NO_GO"
    assert doc["source_review_queue_unresolved"] == 428
    for flag in ("independent_human_approval", "release_approval",
                 "production_db_written", "repository_official_shards_changed",
                 "production_sites_deployed"):
        assert doc[flag] is False, flag
    assert doc["official_answer_changes"] == doc["grading_changes"] == 0
    rows = doc["rows"]
    assert len(rows) == doc["changed_question_count"] == doc["changed_field_count"] == 9
    assert {x["id"] for x in rows} == EXPECTED_IDS

    shards = {}
    for entry in rows:
        id_ = entry["id"]
        filename = entry["shard"]
        assert filename in (
            "cdn/question-shards/104-1.json", "cdn/question-shards/106-2.json",
            "cdn/question-shards/107-2.json"
        )
        if filename not in shards:
            blob = json.loads((ROOT / filename).read_text(encoding="utf-8"))
            assert blob["question_count"] == len(blob["questions"]) == 200
            shards[filename] = {x["id"]: x for x in blob["questions"]}
        actual = shards[filename][id_]
        field = entry["field"]
        assert field in SAFE_FIELDS
        assert actual[field] == entry["old_text"], ("main changed; rebase candidate", id_)
        assert actual["answer"] == entry["baseline_answer"]
        assert actual.get("accepted_answers") == entry["baseline_accepted_answers"]
        assert actual["grading_mode"] == entry["baseline_grading_mode"] == "standard"
        assert actual["analysis_status"] == entry["baseline_analysis_status"] == "ready"
        assert entry["proposed_analysis_status"] == "review"
        assert entry["independent_human_approved"] is False
        assert re.fullmatch(r"[a-f0-9]{64}", entry["official_pdf_sha256"])
        assert re.fullmatch(r"[a-f0-9]{64}", entry["pdf_layout_sha256"])
        official_extract = entry["official_pdf_text_extraction"]
        def normalized(text):
            return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
        assert normalized(entry["proposed_text"]) == normalized(official_extract), ("source packet mismatch", id_)
        # Detect substantive edit even when the candidate is not released.
        assert normalized(entry["old_text"]) != normalized(official_extract), ("no official PDF discrepancy", id_)
        url = urlparse(entry["original_pdf_url"])
        assert url.scheme == "https" and url.hostname == "wwwq.moex.gov.tw"
        assert url.path.endswith("/wHandExamQandA_File.ashx")
        before = entry["old_text"]
        after = entry["proposed_text"]
        assert before != after
        if id_ in SUFFIX_DIGITS:
            assert field.startswith("opt_")
            assert before == after + SUFFIX_DIGITS[id_], id_
        else:
            assert id_ == "SW-106-2-09" and field == "question"
            assert before.count("獨立自主4 生活能力") == 1
            assert after == before.replace("獨立自主4 生活能力", "獨立自主生活能力")

        staged = copy.deepcopy(actual)
        staged[field] = after
        staged["analysis_status"] = "review"
        assert staged["answer"] == actual["answer"]
        assert staged.get("accepted_answers") == actual.get("accepted_answers")
        assert staged["grading_mode"] == actual["grading_mode"]
        assert {k for k in staged if staged[k] != actual[k]} == {field, "analysis_status"}

    print("DRAFT P0 NINE BOUNDARY CANDIDATES OK: 9 exact main preimages, "
          "grading unchanged, AI quarantine required, NO-GO; no writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
