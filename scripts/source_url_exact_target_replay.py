#!/usr/bin/env python3
"""Deterministic, zero-network replay of the exact 3,920 source-URL-only release.

Works *before* or *after* the URL-only shard candidate is staged. The old
Git objects are pinned by git-blob SHA and reconstructed only into a disposable
outside-repository directory, so a post-staging QA run cannot silently skip
the original 3,920-row replay or its native PostgreSQL rollback rehearsal.

This does not authorize production database writes, merge, deploy, or approval
of official question wording, grading, essay AI or human PDF reviews.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from historical_source_url_guard import validate_historical_source_urls
from source_url_promotion_stage import git_blob, load_unique_json, stage

CONFIG = "data/source_url_promotion_config.json"
BASE = "cdn/question-shards"
EXPECTED_CHANGED = 3920


def historical_blob(repo: Path, sha: str) -> bytes:
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("invalid pinned old blob SHA")
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", sha],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=12,
    )
    if proc.returncode != 0 or git_blob(proc.stdout) != sha:
        raise ValueError(f"missing/drifted historical Git blob {sha[:12]}")
    return proc.stdout


def verify(repo: Path, fixture: Path | None = None) -> dict:
    cfg = load_unique_json((repo / CONFIG).read_bytes())
    if cfg.get("schema") != "swsi-source-url-promotion-review-v1" or cfg.get("status") != "QA_ONLY_NOT_AUTHORIZED_FOR_PRODUCTION":
        raise ValueError("unexpected promotion authorization contract")
    before, after = cfg["expected_sessions_before_git_blobs"], cfg["expected_sessions_after_git_blobs"]
    if set(before) != set(after) or len(before) != 22 or cfg["expected_total_changed"] != EXPECTED_CHANGED:
        raise ValueError("incomplete 22-session historical release contract")
    files = {s: (repo / BASE / f"{s}.json").read_bytes() for s in before}
    digests = {s: git_blob(raw) for s, raw in files.items()}
    manifest_bytes = (repo / BASE / "manifest.json").read_bytes()
    man_digest = git_blob(manifest_bytes)
    is_before = (all(digests[s] == before[s] for s in before) and man_digest == cfg["expected_manifest_before_git_blob"])
    is_after = (all(digests[s] == after[s] for s in before) and man_digest == cfg["expected_manifest_after_git_blob"])
    if is_before == is_after:
        raise ValueError("partial/mixed/unknown source URL release state; stop")
    originals = {}
    if is_before:
        originals.update(files)
        original_manifest = manifest_bytes
    else:
        originals = {s: historical_blob(repo, before[s]) for s in sorted(before)}
        original_manifest = historical_blob(repo, cfg["expected_manifest_before_git_blob"])
    # Reconstruct an old-state fixture outside repo so existing 9 negative
    # selftests and the native PG17 TEMP-table ROLLBACK can *still* execute
    # against the exact original candidate even after promotion.
    if fixture is not None:
        dest = fixture.resolve()
        if dest == repo or repo in dest.parents:
            raise ValueError("disposable old-state fixture must be outside Git repo")
        if dest.exists() and any(dest.iterdir()):
            raise ValueError("disposable fixture output must be empty")
        (dest / "data").mkdir(parents=True, exist_ok=True)
        (dest / BASE).mkdir(parents=True, exist_ok=True)
        (dest / CONFIG).write_bytes((repo / CONFIG).read_bytes())
        for s, raw in originals.items():
            (dest / BASE / f"{s}.json").write_bytes(raw)
        (dest / BASE / "manifest.json").write_bytes(original_manifest)
        for s in ("115-1", "115-2"):
            (dest / BASE / f"{s}.json").write_bytes((repo / BASE / f"{s}.json").read_bytes())
        fixture_root = dest
    else:
        # In-memory replay needs filesystem inputs but never writes repo.
        # The baseline state is already in repo for pre-promotion.
        if is_after:
            raise ValueError("after-state replay requires --fixture-before OUTSIDE_REPO")
        fixture_root = repo
    regenerated, report = stage(fixture_root, cfg)
    if report["changed_source_urls"] != EXPECTED_CHANGED or report["other_fields_changed"] != 0:
        raise ValueError("source-only 3920 correction proof mismatch")
    for s in before:
        target = regenerated[f"{s}.json"]
        if git_blob(target) != after[s]:
            raise ValueError(f"expected target Git blob changed: {s}")
        if is_after and files[s] != target:
            raise ValueError(f"committed shard differs from exact regenerated target: {s}")
    target_manifest = regenerated["manifest.json"]
    if git_blob(target_manifest) != cfg["expected_manifest_after_git_blob"]:
        raise ValueError("target manifest SHA does not match pinned proof")
    if is_after and manifest_bytes != target_manifest:
        raise ValueError("committed manifest differs from exact regenerated target")
    all_rows = []
    for session in sorted(before):
        all_rows.extend(load_unique_json(regenerated[f"{session}.json"])["questions"])
    for session in ("115-1", "115-2"):
        all_rows.extend(load_unique_json((repo / BASE / f"{session}.json").read_bytes())["questions"])
    if len(all_rows) != 4800 or validate_historical_source_urls(all_rows, registry_path=repo / "data/moex_source_subjects.v1.json") != 4800:
        raise ValueError("post-promotion 4800 official source identities are not verified")
    manifest = load_unique_json(target_manifest)
    for part in manifest["shards"]:
        raw = regenerated.get(part["file"])
        if raw is None:
            raw = (repo / BASE / part["file"]).read_bytes()
        if part["sha256"] != hashlib.sha256(raw).hexdigest() or part["bytes"] != len(raw):
            raise ValueError(f"manifest artifact integrity mismatch: {part['file']}")
    return {"status": "PASS_QA_ONLY_NOT_DEPLOYED", "phase": "after" if is_after else "before",
            "changed_source_urls": EXPECTED_CHANGED, "official_non_url_fields_changed": 0,
            "official_pdf_source_headers_checked": 120,
            "verified_candidate_urls": len(all_rows), "synthetic_pg_fixture_ready": fixture is not None,
            "production_database_written": False, "main_merged": False}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--fixture-before", type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    print(json.dumps(verify(root, args.fixture_before), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
