#!/usr/bin/env python3
"""Stage two source-corrected MOEX MCQs into an OFFLINE, NO-GO artifact.

Never modifies tracked question shards, Supabase, Cloudflare, Netlify or human
approval flags. Stage against CURRENT checked-in physical manifest and frozen
Official Core. Exact case-only proof and 4,800 grading invariants are required.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
SHARDS = ROOT / "cdn/question-shards"
LOCK = ROOT / "data/official_exam_readonly.lock.json"
REGISTRY = ROOT / "data/moex_source_subjects.v1.json"
PREFLIGHT = ROOT / "audit/official_held_two_live_preflight_evidence_20261105.json"
Q40_PROOF = ROOT / "audit/official_r107_2_40_option_tail_candidate_20261105.json"
SCOPE = {
    "R-107-2-40": ("107-2.json", "D"),
    "SP111-2-34": ("111-2.json", "C"),
}
EXPECTED_PDF = {
    "R-107-2-40": "65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d",
    "SP111-2-34": "9a4afe4df13a7b88582efa0bb3950ccdb3780ec5c7e3380afabe8b0e8f2e3a0d",
}
REPAIRS = {
    "R-107-2-40": {
        "opt_d": "兩個變項間有高度相關，則非常可能有因果關係",
    },
    "SP111-2-34": {
        "opt_a": "1 至 3 個月",
        "opt_b": "2 至 4 個月",
        "opt_c": "3 至 6 個月",
        "opt_d": "4 至 6 個月",
    }
}
OLD = {
    "R-107-2-40": {
        "opt_d": "兩個變項間有高度相關，則非常可能有因果關係 備 註：第 12 題答 B 或 C 或 BC 者均給分。",
    },
    "SP111-2-34": {
        "opt_a": "至3 個月 2",
        "opt_b": "至4 個月 3",
        "opt_c": "至6 個月 4",
        "opt_d": "至6 個月",
    },
}
ENRICHMENT = ("exp_why", "exp_others", "exp_trap", "exp_raw",
              "mnemonic", "extension")
GRADE = ("answer", "accepted_answers", "grading_mode")


def fail(condition, reason):
    if not condition:
        raise RuntimeError("NO-GO STAGER: " + reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def stable(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def paper_identity(url):
    p = urlsplit(str(url))
    fail(p.scheme == "https" and p.netloc == "wwwq.moex.gov.tw"
         and p.path == "/exam/wHandExamQandA_File.ashx", "official PDF URL origin")
    pairs = parse_qsl(p.query, keep_blank_values=True)
    fail(len(pairs) == 5, "unexpected PDF URL query items")
    return dict(pairs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    fail(out != ROOT and ROOT not in out.parents, "staging must be outside repo")
    fail(not out.exists(), "staging folder must not preexist")

    proof = json.loads(PREFLIGHT.read_text("utf-8"))
    q40 = json.loads(Q40_PROOF.read_text("utf-8"))
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    lock = json.loads(LOCK.read_text("utf-8"))
    registry = json.loads(REGISTRY.read_text("utf-8"))

    fail(proof["status"] == "LIVE_SELECT_PREIMAGE_PROVEN_RELEASE_NO_GO"
         and proof["results"]["strict_matches"] == 2
         and proof["results"]["targets"] == 2
         and proof["results"]["official_mcq_count"] == 4800
         and proof["results"]["production_writes"] == 0,
         "live exact-before evidence or HOLD missing")
    fail(all(proof["safety"][k] is False for k in
             ("human_original_pdf_approval", "release_approved", "production_write",
              "backup_operation", "official_core_modified")),
         "requires unapproved, read-only evidence")
    fail(q40["case_id"] == "R-107-2-40" and q40["human_approval"] is False
         and q40["release_approved"] is False
         and q40["proposal"]["changed_official_fields"] == ["opt_d"]
         and q40["proposal"]["opt_d"] == REPAIRS["R-107-2-40"]["opt_d"],
         "source Q40 exact repair evidence")
    fail({r["id"] for r in proof["rows"]} == set(SCOPE), "exact two source IDs")
    fail(len(manifest["shards"]) == 24 and manifest["total_questions"] == 4800
         and lock["mcq_count"] == 4800 and lock["essay_count"] == 240,
         "baseline 4,800/240 counts")

    for e in proof["rows"]:
        rid = e["id"]
        fail(e["original_pdf_registry_sha256"] == EXPECTED_PDF[rid]
             and e["changed_fields_proposed"] == sorted(REPAIRS[rid])
             and e["expected_answer"] == SCOPE[rid][1],
             "source case identity and unchanged answer")
        paper_url = paper_identity(e["original_pdf_url"])
        papers = [p for p in registry["records"] if paper_identity(p["url"]) == paper_url]
        fail(len(papers) == 1 and papers[0]["pdf_sha256"] == EXPECTED_PDF[rid],
             "source PDF SHA-256 registry drift")

    originals = {}
    raw_shards = {}
    for entry in manifest["shards"]:
        fname = entry["file"]
        fail(Path(fname).name == fname and fname.endswith(".json"), "unsafe file path")
        raw = (SHARDS / fname).read_bytes()
        fail(len(raw) == entry["bytes"] and sha(raw) == entry["sha256"],
             "baseline physical shard hash: " + fname)
        data = json.loads(raw)
        rows = data["questions"]
        fail(len(rows) == entry["question_count"] == 200, "not 200 questions")
        raw_shards[fname] = data
        for row in rows:
            rid = row["id"]
            fail(rid not in originals, "duplicate ID " + rid)
            originals[rid] = copy.deepcopy(row)
            fail(row_hash(canonical_row(row, MCQ_FIELDS)) == lock["mcq"].get(rid),
                 "Official Core baseline lock mismatch " + rid)
    fail(len(originals) == 4800 and len(lock["mcq"]) == 4800, "full corpus ID drift")

    proposed = copy.deepcopy(originals)
    changes = {}
    for rid, (fname, answer) in SCOPE.items():
        row = proposed.get(rid)
        original = originals.get(rid)
        fail(row is not None and original is not None and
             any(x["file"] == fname for x in manifest["shards"]),
             "source ID/session not found")
        fail(row["answer"] == answer and row["accepted_answers"] is None
             and row["grading_mode"] == "standard" and
             row["analysis_status"] == "ready",
             "source answer/status drift " + rid)
        fail(all(row.get(field) == value for field, value in OLD[rid].items()),
             "exact old OCR source preimage drift " + rid)
        source = next(x for x in proof["rows"] if x["id"] == rid)
        fail(paper_identity(row["source_url"]) ==
             paper_identity(source["original_pdf_url"]), "row paper identity")
        if rid == "R-107-2-40":
            fail(row == q40["before_row"], "full Q40 original row changed")
        for field, new in REPAIRS[rid].items():
            fail(field in ("opt_a", "opt_b", "opt_c", "opt_d"), "unexpected source field")
            row[field] = new
        # Explicitly quarantine option-dependent AI notes. The law field,
        # topic and independent grading are preserved for later review.
        for field in ENRICHMENT:
            row[field] = None
        row["analysis_status"] = "review"
        diff = {k for k in row if row[k] != original[k]}
        fail(set(REPAIRS[rid]) <= diff and
             diff <= set(REPAIRS[rid]) | set(ENRICHMENT) | {"analysis_status"},
             "unrelated official/enrichment edit")
        fail(tuple(row[k] for k in GRADE) == tuple(original[k] for k in GRADE),
             "grading tuple touched")
        changes[rid] = {
            "original_core_sha256": lock["mcq"][rid],
            "staged_core_sha256": row_hash(canonical_row(row, MCQ_FIELDS)),
            "source_fields_changed": sorted(REPAIRS[rid]),
            "additional_stale_enrichment_quarantined": sorted(diff - set(REPAIRS[rid])),
            "official_answer_unchanged": row["answer"],
            "source_pdf_sha256": EXPECTED_PDF[rid],
            "human_approval": False,
        }

    unchanged = set(originals) - set(SCOPE)
    fail(len(unchanged) == 4798 and all(originals[i] == proposed[i] for i in unchanged),
         "non-target question changed")
    fail(all(tuple(originals[r][f] for f in GRADE) ==
             tuple(proposed[r][f] for f in GRADE) for r in originals),
         "4,800 grading tuples changed")

    staged_manifest = copy.deepcopy(manifest)
    for entry in staged_manifest["shards"]:
        name = entry["file"]
        if name not in {"107-2.json", "111-2.json"}:
            continue
        data = copy.deepcopy(raw_shards[name])
        count = 0
        for i, row in enumerate(data["questions"]):
            rid = row["id"]
            if rid in SCOPE:
                data["questions"][i] = proposed[rid]
                count += 1
        fail(count == 1, "expected exactly one target per target shard")
        original_bytes = (SHARDS / name).read_bytes()
        staged_bytes = stable(data)
        fail(staged_bytes != original_bytes, "candidate shard identical to baseline")
        entry["sha256"] = sha(staged_bytes)
        entry["bytes"] = len(staged_bytes)
        staged_manifest["total_uncompressed_bytes"] += len(staged_bytes) - len(original_bytes)
        raw_shards[name] = staged_bytes
    hashes = [f"{m['file']}:{m['sha256']}" for m in staged_manifest["shards"]]
    staged_manifest["dataset_revision"] = sha("\n".join(hashes).encode("utf-8"))[:20]
    staged_manifest["source"] = "STAGED NO-GO: original MOEX Q40/SP34 options unapproved"
    staged_manifest["generated_at"] = "2026-11-05T00:00:00Z"
    fail(staged_manifest["dataset_revision"] != manifest["dataset_revision"],
         "manifest not versioned")

    updated_lock = copy.deepcopy(lock)
    for rid in SCOPE:
        updated_lock["mcq"][rid] = changes[rid]["staged_core_sha256"]
    fail({rid for rid in updated_lock["mcq"]
          if updated_lock["mcq"][rid] != lock["mcq"][rid]} == set(SCOPE),
         "unexpected lock changes")
    fail(updated_lock["essays"] == lock["essays"], "essay lock drift")

    (out / "cdn/question-shards").mkdir(parents=True)
    (out / "data").mkdir()
    for name in ("107-2.json", "111-2.json"):
        (out / "cdn/question-shards" / name).write_bytes(raw_shards[name])
    (out / "cdn/question-shards/manifest.json").write_bytes(stable(staged_manifest))
    (out / "data/official_exam_readonly.lock.json").write_text(
        json.dumps(updated_lock, ensure_ascii=False, indent=2) + "\n", "utf-8")
    evidence = {
        "status": "STAGED_ONLY_HUMAN_APPROVAL_FALSE_NO_GO",
        "base_dataset_revision": manifest["dataset_revision"],
        "staged_dataset_revision": staged_manifest["dataset_revision"],
        "original_4800_questions_unchanged": 4798,
        "grading_unchanged_count": 4800,
        "essay_lock_count": 240,
        "changed_core_lock_count": 2,
        "candidate_shard_names": ["107-2.json", "111-2.json"],
        "human_approval": False, "release_approved": False,
        "production_write": False, "netlify_backup_write": False,
        "current_five_source_holds_not_released": True,
        "changes": changes,
        "review_required": ["independent human original PDF signoff",
                            "production-faithful 7-trigger/pg_cron/pg_net rehearsal",
                            "fresh 37-column DB preimage/rollback + exact-head source QA",
                            "controlled production+Cloudflare+browser post-parity"],
    }
    (out / "candidate-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", "utf-8")
    files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
    fail(files == {
        "cdn/question-shards/107-2.json", "cdn/question-shards/111-2.json",
        "cdn/question-shards/manifest.json", "data/official_exam_readonly.lock.json",
        "candidate-evidence.json"}, "unexpected staging files")
    print("STAGED OFFLINE NO-GO: 2 exact MOEX source options corrected; "
          "4798/4798 unrelated MCQs identical; 4800/4800 grading unchanged; "
          "240 essays unchanged; 0 production/Netlify writes; "
          "human release approval=false")


if __name__ == "__main__":
    main()
