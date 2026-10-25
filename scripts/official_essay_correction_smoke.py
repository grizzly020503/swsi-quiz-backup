#!/usr/bin/env python3
"""Verify the single PDF-backed official essay correction and its exact boundary."""
import hashlib
import json
from pathlib import Path
import re

from audit_moex_source_subjects import load_registry, require_source
from monthly_patch_build import _array_span
from official_essay_pdf_audit import normalize
from official_exam_readonly_guard import canonical_row, row_hash, ESSAY_FIELDS, collect_essays

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "audit/official_essay_112_2_sw2_correction.json"


def check():
    proof = json.loads(PROOF.read_text())
    ident = proof["id"]
    before, after = proof["before"], proof["after"]
    assert proof["human_approval"] is False and proof["maintainer_review_required"] is True
    assert all(before[k] == after[k] for k in ("id", "subject", "year", "round", "qno", "points"))
    assert set(k for k in ESSAY_FIELDS if before.get(k) != after.get(k)) == {"q"}
    assert row_hash(canonical_row(before, ESSAY_FIELDS)) == proof["before_lock_sha256"]
    assert row_hash(canonical_row(after, ESSAY_FIELDS)) == proof["after_lock_sha256"]
    assert normalize(after["q"]) == normalize(proof["official_source"]["official_pdf_text"])
    assert "Cowger" in after["q"] and "百分之三十" not in after["q"]
    for key in ("keywords", "theories", "laws", "related"):
        assert after[key] == [], "stale enrichment must remain quarantined"
    assert after["analysis_status"] == "review" and after["cluster"] is None
    source = require_source(load_registry(), "112110", "社會工作", after["source_url"])
    assert source["pdf_sha256"] == proof["official_source"]["pdf_sha256"]
    for name in ("index.html", "cdn/index.html"):
        text = (ROOT/name).read_text()
        a,b = _array_span(text,"ESSAYS")
        row = next(r for r in json.loads(text[a:b]) if r["id"] == ident)
        assert row == after, name + ": corrected official essay drifted"
        matches = list(re.finditer(re.escape(json.dumps(ident,ensure_ascii=False))+r"\s*:\s*",text))
        assert len(matches) == 1
        guide,_ = json.JSONDecoder().raw_decode(text,matches[0].end())
        assert guide == proof["quarantined_guide"], name + ": stale inline guide returned"
    # Fingerprint the unchanged portions of the immutable baseline lock. This
    # remains deterministic in shallow CI checkouts without fetching history.
    locked = json.loads((ROOT/"data/official_exam_readonly.lock.json").read_text())
    digest = lambda value: hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    mcq_baseline = dict(locked["mcq"])
    mcq_proof = json.loads((ROOT/"audit/official_mcq_corrections_20261025.json").read_text())
    additional_mcq = json.loads((ROOT/"audit/official_mcq_corrections_additional_20261025.json").read_text())
    assert additional_mcq["count"] == 7 and additional_mcq["human_approval"] is False
    for row in mcq_proof["rows"] + additional_mcq["rows"]:
        assert mcq_baseline[row["id"]] == row["after_lock_sha256"]
        mcq_baseline[row["id"]] = row["before_lock_sha256"]
    assert digest(mcq_baseline) == proof["unchanged_mcq_lock_map_sha256"], "undeclared MCQ locks changed"
    others = {key:value for key,value in locked["essays"].items() if key != ident}
    assert len(others) == 239 and len(locked["mcq"]) == 4800
    assert digest(others) == proof["unchanged_other_essay_lock_map_sha256"], "another essay lock changed"
    assert locked["essays"][ident] == proof["after_lock_sha256"]
    assert collect_essays()[ident] == canonical_row(after, ESSAY_FIELDS)
    print("OFFICIAL ESSAY CORRECTION OK: one q/one lock; 239 other essays unchanged; MCQ deltas confined to separate controlled proof; stale guide quarantined; human approval pending")


if __name__ == "__main__":
    check()
