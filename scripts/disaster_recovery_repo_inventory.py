#!/usr/bin/env python3
"""Offline repository inventory checks for the SWSI disaster-recovery drill."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise AssertionError(message)


inventory = json.loads((ROOT / "supabase/recovery/edge_functions.json").read_text(encoding="utf-8"))
expected_functions = {row["slug"] for row in inventory["functions"]}
actual_functions = {
    path.name
    for path in (ROOT / "supabase/functions").iterdir()
    if path.is_dir() and (path / "index.ts").is_file()
}
if actual_functions != expected_functions:
    fail(
        "Edge Function source inventory mismatch: "
        f"missing={sorted(expected_functions - actual_functions)} "
        f"extra={sorted(actual_functions - expected_functions)}"
    )

deprecated = (ROOT / "supabase/functions/check-official-laws/index.ts").read_text(encoding="utf-8")
for marker in ("status: 410", "Deprecated bulk MOJ downloader", "sync-legal-watch"):
    if marker not in deprecated:
        fail(f"deprecated check-official-laws marker missing: {marker}")

manifest_path = ROOT / "cdn/question-shards/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("total_questions") != 4800:
    fail(f"expected 4800 questions, got {manifest.get('total_questions')}")
if manifest.get("shard_count") != 24:
    fail(f"expected 24 question shards, got {manifest.get('shard_count')}")

shard_dir = manifest_path.parent
expected_files = {row["file"] for row in manifest["shards"]}
actual_files = {p.name for p in shard_dir.glob("*.json") if p.name != "manifest.json"}
if actual_files != expected_files:
    fail(
        "question shard inventory mismatch: "
        f"missing={sorted(expected_files - actual_files)} extra={sorted(actual_files - expected_files)}"
    )

for row in manifest["shards"]:
    raw = (shard_dir / row["file"]).read_bytes()
    if len(raw) != int(row["bytes"]):
        fail(f"{row['file']}: byte length mismatch")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != row["sha256"]:
        fail(f"{row['file']}: SHA-256 mismatch")
    payload = json.loads(raw)
    if len(payload) != int(row["question_count"]):
        fail(f"{row['file']}: question count mismatch")

# Best-effort credential-value scan. Environment variable names are allowed;
# actual high-confidence credential formats are not.
secret_patterns = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "supabase-secret": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}\b"),
    "openai-style-secret": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "jwt-value": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

scan_roots = [
    ROOT / "supabase/recovery",
    ROOT / "supabase/functions",
    ROOT / ".github/workflows",
    ROOT / "scripts",
]
hits: list[str] = []
for scan_root in scan_roots:
    for path in scan_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".sql", ".ts", ".js", ".py", ".yml", ".yaml", ".json", ".md", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in secret_patterns.items():
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)}:{name}")
if hits:
    fail("high-confidence secret-like value found: " + ", ".join(sorted(hits)))

env_names: set[str] = set()
env_re = re.compile(r'Deno\.env\.get\(["\']([A-Z0-9_]+)["\']\)')
for slug in sorted(expected_functions):
    source = (ROOT / "supabase/functions" / slug / "index.ts").read_text(encoding="utf-8")
    env_names.update(env_re.findall(source))

print(
    "SWSI DR REPO INVENTORY OK "
    f"edge_functions={len(expected_functions)} "
    f"question_shards={manifest['shard_count']} "
    f"questions={manifest['total_questions']}"
)
print("EXTERNAL CONFIG NAMES ONLY: " + ",".join(sorted(env_names)))
