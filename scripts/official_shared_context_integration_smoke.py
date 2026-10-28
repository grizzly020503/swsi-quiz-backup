#!/usr/bin/env python3
"""Fail-closed verification of the existing 13-row source correction candidate.

The committed preimage is mandatory: current locks alone cannot prove that
unrelated answers, explanations, or Official Core rows were preserved.
No network access, lock refresh, production write, or release approval.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
SHARDS = "cdn/question-shards/"
LOCK = "data/official_exam_readonly.lock.json"
INTEGRATION = "audit/official_shared_context_13_integration_20261029.json"
SOURCE_PROOFS = (
    ("105-2.json", "audit/official_105_2_shared_context_20261028.json",
     {f"R-105-2-{n:02}" for n in (12, 13, 14, 15, 16, 20, 21, 22)},
     "6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836"),
    ("107-2.json", "audit/official_107_2_shared_context_20261028.json",
     {f"R-107-2-{n:02}" for n in (4, 5, 6, 7, 8)},
     "65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d"),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dataset_revision(entries):
    # Same identity rule as build_question_shards.build().
    return sha("\n".join(f"{e['file']}:{e['sha256']}" for e in entries).encode())[:20]


def baseline_reader(root, ref):
    require(bool(re.fullmatch(r"[0-9a-f]{40}", ref)), "baseline must be a full commit SHA")

    @lru_cache(maxsize=None)
    def read(path):
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True, check=False,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1"}, timeout=30)
        require(result.returncode == 0,
                f"baseline unavailable: {ref}:{path}; fetch the pinned commit, do not skip comparison")
        return result.stdout

    return read


def verify(root=ROOT, read_before=None):
    root = Path(root)
    read = lambda path: (root / path).read_bytes()
    proof = json.loads(read(INTEGRATION))
    if read_before is None:
        read_before = baseline_reader(root, proof["baseline_commit"])
    manifest = json.loads(read(SHARDS + "manifest.json"))
    previous_manifest = json.loads(read_before(SHARDS + "manifest.json"))
    lock = json.loads(read(LOCK))
    previous_lock = json.loads(read_before(LOCK))
    require(manifest["total_questions"] == len(lock["mcq"]) == 4800, "MCQ coverage")
    require(manifest["shard_count"] == len(manifest["shards"]) == 24, "shard coverage")
    require(lock["essay_count"] == len(lock["essays"]) == 240, "essay lock coverage")
    require(manifest["dataset_revision"] == proof["dataset_revision"] ==
            dataset_revision(manifest["shards"]), "dataset revision differs from builder identity")

    changes = {}
    changed_files = set()
    for name, path, ids, pdf_sha in SOURCE_PROOFS:
        source = json.loads(read(path))
        require(source["source_pdf_sha256"] == pdf_sha and source["not_approved_for_merge"] is True,
                f"source provenance or approval drift: {path}")
        require(len(source["changes"]) == len(ids) and {c["id"] for c in source["changes"]} == ids,
                f"source correction coverage: {path}")
        require(sha(read(SHARDS + name)) == source["new_shard_sha256"] == proof["sha256"][name],
                f"candidate shard differs from source PR: {name}")
        require(sha(read_before(SHARDS + name)) == source["old_shard_sha256"],
                f"source preimage drift: {name}")
        for change in source["changes"]:
            ident = change["id"]
            require(ident not in changes, f"duplicate source correction: {ident}")
            require(set(change["fields"]) <= {"question", "opt_d"}, f"unapproved field: {ident}")
            changes[ident] = change
        changed_files.add(name)
    require(len(changes) == len(proof["changed_ids"]) == 13 and
            set(changes) == set(proof["changed_ids"]), "integration correction coverage")

    old_entries = {e["file"]: e for e in previous_manifest["shards"]}
    require(len(old_entries) == 24, "baseline manifest coverage")
    seen_files, seen_ids, changed_ids = set(), set(), set()
    total_bytes = 0
    for entry in manifest["shards"]:
        name = entry["file"]
        require(name in old_entries and name not in seen_files, f"shard identity: {name}")
        seen_files.add(name)
        raw, old_raw = read(SHARDS + name), read_before(SHARDS + name)
        require(sha(raw) == entry["sha256"] and len(raw) == entry["bytes"], f"shard integrity: {name}")
        total_bytes += len(raw)
        payload, old_payload = json.loads(raw), json.loads(old_raw)
        rows, old_rows = payload["questions"], old_payload["questions"]
        require(len(rows) == len(old_rows) == payload["question_count"] == entry["question_count"] == 200,
                f"shard row count: {name}")
        expected_payload = deepcopy(old_payload)
        for old, new, expected in zip(old_rows, rows, expected_payload["questions"]):
            ident = old["id"]
            require(new["id"] == ident and ident not in seen_ids, f"row identity/order: {ident}")
            seen_ids.add(ident)
            require(row_hash(canonical_row(old, MCQ_FIELDS)) == previous_lock["mcq"][ident],
                    f"baseline core lock: {ident}")
            require(row_hash(canonical_row(new, MCQ_FIELDS)) == lock["mcq"][ident],
                    f"candidate core lock: {ident}")
            change = changes.get(ident)
            if change:
                require(previous_lock["mcq"][ident] == change["old_lock_sha256"] and
                        lock["mcq"][ident] == change["new_lock_sha256"], f"source lock evidence: {ident}")
                for field, delta in change["fields"].items():
                    require(old[field] == delta["before"] != delta["after"], f"field preimage: {ident}.{field}")
                    expected[field] = delta["after"]
                for field in ("answer", "accepted_answers", "grading_mode"):
                    require(old.get(field) == new.get(field) == change[field], f"grading evidence: {ident}")
            require(new == expected, f"unapproved row/answer/enrichment change: {ident}")
            if old != new:
                changed_ids.add(ident)
        require(payload == expected_payload, f"unapproved shard metadata change: {name}")
        if name not in changed_files:
            require(raw == old_raw and entry == old_entries[name], f"untouched shard changed: {name}")
        else:
            expected_entry = {**old_entries[name], "bytes": len(raw), "sha256": sha(raw)}
            require(entry == expected_entry, f"unapproved manifest entry change: {name}")

    require(changed_ids == set(changes) and len(seen_ids) - len(changed_ids) == proof["unchanged_count"] == 4787,
            "13 changed / 4787 unchanged row boundary")
    require(total_bytes == manifest["total_uncompressed_bytes"] == proof["manifest_total_bytes"], "total bytes")
    require(seen_ids == set(lock["mcq"]) == set(previous_lock["mcq"]), "lock IDs drift")
    expected_lock = deepcopy(previous_lock)
    for ident, change in changes.items():
        expected_lock["mcq"][ident] = change["new_lock_sha256"]
    require(lock == expected_lock, "non-target MCQ / essay lock or lock metadata drift")
    for path in ("index.html", "auto/essays_auto.json"):
        require(read(path) == read_before(path), f"essay source changed: {path}")
    allowed_manifest_fields = {"generated_at", "dataset_revision", "total_uncompressed_bytes", "shards"}
    require({k: v for k, v in manifest.items() if k not in allowed_manifest_fields} ==
            {k: v for k, v in previous_manifest.items() if k not in allowed_manifest_fields}, "manifest metadata drift")
    require(proof["source_proofs"] == [p for _, p, _, _ in SOURCE_PROOFS] and
            proof["source_pdf_sha256"] == [s for _, _, _, s in SOURCE_PROOFS], "integration provenance drift")
    require(all(proof[k] is False for k in ("merge_approval", "backup_modified", "production_mutation")),
            "read-only evidence must not imply release approval")
    return {"changed": 13, "unchanged": 4787, "grading_preserved": 4800,
            "essay_locks_preserved": 240, "shards": 24, "dataset_revision": manifest["dataset_revision"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.root), ensure_ascii=False, sort_keys=True))
    print("PASS: source integration only; human PDF acceptance and release gates remain required")


if __name__ == "__main__":
    main()
