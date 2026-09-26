#!/usr/bin/env python3
"""Offline recoverability inventory for the SWSI disaster-recovery drill."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


edge_inventory = json.loads(
    (ROOT / "supabase/recovery/edge_functions.json").read_text(encoding="utf-8")
)
expected_functions = {row["slug"] for row in edge_inventory["functions"]}
actual_functions = {
    path.name
    for path in (ROOT / "supabase/functions").iterdir()
    if path.is_dir() and (path / "index.ts").is_file()
}
require(
    actual_functions == expected_functions,
    "Edge Function source inventory mismatch: "
    f"missing={sorted(expected_functions - actual_functions)} "
    f"extra={sorted(actual_functions - expected_functions)}",
)

deprecated = (
    ROOT / "supabase/functions/check-official-laws/index.ts"
).read_text(encoding="utf-8")
for marker in ("status: 410", "Deprecated bulk MOJ downloader", "sync-legal-watch"):
    require(marker in deprecated, f"deprecated Edge Function marker missing: {marker}")

manifest_path = ROOT / "cdn/question-shards/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
require(manifest.get("total_questions") == 4800, "question total is not 4800")
require(manifest.get("shard_count") == 24, "question shard count is not 24")

shard_dir = manifest_path.parent
expected_shards = {row["file"] for row in manifest["shards"]}
actual_shards = {p.name for p in shard_dir.glob("*.json") if p.name != "manifest.json"}
require(
    actual_shards == expected_shards,
    f"question shard file mismatch missing={sorted(expected_shards - actual_shards)} "
    f"extra={sorted(actual_shards - expected_shards)}",
)

total = 0
for row in manifest["shards"]:
    raw = (shard_dir / row["file"]).read_bytes()
    require(len(raw) == int(row["bytes"]), f"{row['file']}: byte length mismatch")
    require(
        hashlib.sha256(raw).hexdigest() == row["sha256"],
        f"{row['file']}: SHA-256 mismatch",
    )
    payload = json.loads(raw)
    questions = payload.get("questions") or []
    require(
        len(questions) == int(row["question_count"]),
        f"{row['file']}: question count mismatch",
    )
    total += len(questions)
require(total == 4800, f"loaded shard total mismatch: {total}")

# Scan for high-confidence credential VALUE formats. Environment variable names
# such as SUPABASE_SERVICE_ROLE_KEY are expected source code and are not secrets.
secret_patterns = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{20,})\b"
    ),
    "supabase-secret": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}\b"),
    "openai-style-secret": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "jwt-value": re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    ),
}

scan_roots = [
    ROOT / "supabase/recovery",
    ROOT / "supabase/functions",
    ROOT / ".github/workflows",
    ROOT / "scripts",
]
allowed_suffixes = {".sql", ".ts", ".js", ".py", ".yml", ".yaml", ".json", ".md", ".sh"}
hits: list[str] = []
for scan_root in scan_roots:
    for path in scan_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in secret_patterns.items():
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)}:{name}")
require(not hits, "high-confidence secret-like value found: " + ", ".join(sorted(hits)))

env_names: set[str] = set()
env_re = re.compile(r"""Deno\.env\.get\(["']([A-Z0-9_]+)["']\)""")
for slug in sorted(expected_functions):
    source = (
        ROOT / "supabase/functions" / slug / "index.ts"
    ).read_text(encoding="utf-8")
    env_names.update(env_re.findall(source))

print(
    "SWSI DR REPO INVENTORY OK "
    f"edge_functions={len(expected_functions)} "
    f"question_shards={manifest['shard_count']} "
    f"questions={manifest['total_questions']}"
)
print("EXTERNAL CONFIG NAMES ONLY: " + ",".join(sorted(env_names)))
