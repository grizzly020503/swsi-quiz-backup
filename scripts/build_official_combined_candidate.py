#!/usr/bin/env python3
"""Reproduce the 41-row DATA integration outside the checkout; never publish.

Pins the three reviewed candidates. Runtime UI integration and the existing
PDF/AI/human release gates are separate and are not approved by this build.
"""
import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
REFS = {
    "base": "31d58ed2e271fc3b831269b238967a92e9ce3e75",
    "shared": "bdeac15988aa8e75f449e9d7b38cba177a07a9bf",
    "figures": "fd4bc0bb6452cf9c5a661adbbf7a67682f98afe0",
    "main": "e08b0292ddb653219327776d65440e837721bba7",
}
SHARDS = "cdn/question-shards/"
LOCK = "data/official_exam_readonly.lock.json"


def require(ok, message):
    if not ok:
        raise ValueError(message)


@lru_cache(maxsize=None)
def read(ref, path):
    return subprocess.run(["git", "show", ref + ":" + path], cwd=ROOT,
                          check=True, capture_output=True, timeout=30).stdout


def doc(ref, path):
    return json.loads(read(ref, path))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stable(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def apply_fields(row, change):
    """Reject stale preimages, unofficial fields and grading drift."""
    require(row_hash(canonical_row(row, MCQ_FIELDS)) == change["old_lock_sha256"],
            "stale core preimage: " + row["id"])
    require(bool(change["fields"]) and set(change["fields"]) <= {"question", "opt_d"},
            "unapproved field: " + row["id"])
    result = deepcopy(row)
    for field, delta in change["fields"].items():
        require(row[field] == delta["before"] != delta["after"], "field preimage: " + row["id"])
        result[field] = delta["after"]
    require(row_hash(canonical_row(result, MCQ_FIELDS)) == change["new_lock_sha256"],
            "source postimage mismatch: " + row["id"])
    for field in ("answer", "accepted_answers", "grading_mode"):
        require(result.get(field) == change[field], "grading drift: " + row["id"])
    return result


def build(out):
    out = Path(out).resolve()
    require(out != ROOT and ROOT not in out.parents, "output must be outside the repository")
    require(not out.exists(), "output already exists; do not overwrite another checkpoint")
    manifest = doc(REFS["base"], SHARDS + "manifest.json")
    lock = doc(REFS["base"], LOCK)
    main_lock = doc(REFS["main"], LOCK)
    payloads, rows, before = {}, {}, {}
    for entry in manifest["shards"]:
        raw = read(REFS["base"], SHARDS + entry["file"])
        require(len(raw) == entry["bytes"] and digest(raw) == entry["sha256"], "base shard integrity")
        payloads[entry["file"]] = json.loads(raw)
        for row in payloads[entry["file"]]["questions"]:
            require(row["id"] not in rows, "duplicate ID")
            require(row_hash(canonical_row(row, MCQ_FIELDS)) == lock["mcq"][row["id"]], "base row lock")
            rows[row["id"]] = row
            before[row["id"]] = deepcopy(row)
    require(len(rows) == len(lock["mcq"]) == 4800, "base coverage")
    base_changed = {i for i in lock["mcq"] if lock["mcq"][i] != main_lock["mcq"][i]}
    require(len(base_changed) == 27, "unexpected base correction scope")
    changes = {}
    proofs = ["audit/official_105_2_shared_context_20261028.json",
              "audit/official_107_2_shared_context_20261028.json"]
    for path in proofs:
        proof = doc(REFS["shared"], path)
        require(proof["not_approved_for_merge"] is True, "unexpected source approval")
        for change in proof["changes"]:
            ident = change["id"]
            require(ident not in changes and ident not in base_changed, "overlapping correction")
            changes[ident] = change
    require(len(changes) == 13, "shared correction coverage")
    for ident, change in changes.items():
        updated = apply_fields(rows[ident], change)
        rows[ident].clear()
        rows[ident].update(updated)
        lock["mcq"][ident] = change["new_lock_sha256"]
    figure = doc(REFS["figures"], "audit/official-figure-core-113-2-13-20261027.json")
    ident = figure["question_id"]
    require(ident not in changes and ident not in base_changed, "figure correction overlap")
    require(rows[ident]["question"] == figure["prior_incorrect_question"], "figure preimage")
    require(lock["mcq"][ident] == figure["previous_official_lock_sha256"], "figure old lock")
    rows[ident]["question"] = figure["new_question"]
    lock["mcq"][ident] = figure["new_official_lock_sha256"]
    require(row_hash(canonical_row(rows[ident], MCQ_FIELDS)) == lock["mcq"][ident], "figure new lock")
    added = set(changes) | {ident}
    require({i for i in rows if rows[i] != before[i]} == added and len(added) == 14, "extra row mutation")
    for i, row in rows.items():
        require(all(row.get(f) == before[i].get(f) for f in ("answer", "accepted_answers", "grading_mode")),
                "grading mutation: " + i)
        require(row_hash(canonical_row(row, MCQ_FIELDS)) == lock["mcq"][i], "combined row lock")
    changed = {i for i in lock["mcq"] if lock["mcq"][i] != main_lock["mcq"][i]}
    require(changed == base_changed | added and len(changed) == 41, "combined 41-row scope")
    require(lock["essays"] == doc(REFS["base"], LOCK)["essays"], "essay locks changed")
    output = {}
    for entry in manifest["shards"]:
        name = entry["file"]
        touched = any(q["id"] in added for q in payloads[name]["questions"])
        raw = stable(payloads[name]) if touched else read(REFS["base"], SHARDS + name)
        output[SHARDS + name] = raw
        entry.update(bytes=len(raw), sha256=digest(raw))
    manifest["total_uncompressed_bytes"] = sum(e["bytes"] for e in manifest["shards"])
    manifest["dataset_revision"] = digest("\n".join(e["file"] + ":" + e["sha256"]
                                                     for e in manifest["shards"]).encode())[:20]
    manifest["source"] = "Pinned combined DATA candidate: 27+13+1 official corrections; NOT release approved"
    output[SHARDS + "manifest.json"] = stable(manifest)
    output[LOCK] = (json.dumps(lock, ensure_ascii=False, indent=2) + "\n").encode()
    assets = doc(REFS["figures"], "data/official_figure_assets.v1.json")
    for asset in assets["figures"]:
        raw = read(REFS["figures"], asset["path"])
        require(digest(raw) == asset["published_png_sha256"], "figure asset hash")
        for prefix in ("", "cdn/"):
            require(read(REFS["figures"], prefix + asset["path"]) == raw, "root/CDN figure drift")
            output[prefix + asset["path"]] = raw
    report = dict(schema_version=1, refs=REFS, mcq=4800, cumulative_core_changes=41,
                  additional_rows=14, unchanged_base_rows=4786, unchanged_main_mcq_locks=4759,
                  grading_preserved=4800, essay_locks_preserved=240,
                  dataset_revision=manifest["dataset_revision"], original_figures=2,
                  runtime_ui_integrated=False, release_approved=False,
                  production_write=False, backup_operation=False,
                  output_sha256={p: digest(raw) for p, raw in output.items()})
    # Validate everything before writing any output.
    for path, raw in output.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (out / "integration.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out), ensure_ascii=False, indent=2))
