#!/usr/bin/env python3
"""Scan every reachable Git blob for high-confidence secret material.

Zero network. No third-party packages. Secret values are never printed.

Run this from a complete local clone after fetching all refs that should be
considered before making the repository public.

Examples:
    git fetch --all --tags --prune
    python3 scripts/public_repo_history_secret_scan.py

Exit codes:
    0 = no findings
    2 = one or more findings need review
    3 = scanner/setup failure
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath


DEFAULT_MAX_BLOB_BYTES = 2 * 1024 * 1024

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "supabase-secret": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}\b"),
    "openai-secret": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "groq-secret": re.compile(r"\bgsk_[A-Za-z0-9_-]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "stripe-live-secret": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    "jwt-value": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

SENSITIVE_ENV_NAMES = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "NETLIFY_AUTH_TOKEN",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_API_KEY",
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)

# Detect a known sensitive variable being assigned a literal-looking value.
# Values are deliberately not captured or printed.
LITERAL_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(" + "|".join(map(re.escape, SENSITIVE_ENV_NAMES)) +
    r")\s*[:=]\s*['\"]?(?!\$\{|\$[A-Za-z_(])[^'\"\s#]{16,}"
)


@dataclass(frozen=True)
class Finding:
    oid: str
    path: str
    kind: str
    line: int | None = None


def git(*args: str, input_text: str | None = None, binary: bool = False) -> bytes | str:
    try:
        proc = subprocess.run(
            ["git", *args],
            input=(input_text.encode("utf-8") if input_text is not None else None),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"unable to execute git: {exc}") from exc

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    if binary:
        return proc.stdout
    return proc.stdout.decode("utf-8", errors="replace")


def ensure_repo() -> None:
    value = str(git("rev-parse", "--is-inside-work-tree")).strip().lower()
    if value != "true":
        raise RuntimeError("run inside a Git working tree")


def object_inventory() -> list[tuple[str, str, int, str]]:
    raw = str(git("rev-list", "--objects", "--all"))
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        return []

    checked = str(
        git(
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)",
            input_text="\n".join(lines) + "\n",
        )
    )

    rows: list[tuple[str, str, int, str]] = []
    for line in checked.splitlines():
        parts = line.split(" ", 3)
        if len(parts) < 3:
            continue
        oid, obj_type, size_raw = parts[:3]
        rest = parts[3] if len(parts) == 4 else ""
        try:
            size = int(size_raw)
        except ValueError:
            continue
        rows.append((oid, obj_type, size, rest))
    return rows


def suspicious_path(path: str) -> str | None:
    if not path:
        return None
    p = PurePosixPath(path.lower())
    name = p.name
    parts = set(p.parts)

    if name == ".env" or name.startswith(".env."):
        return "sensitive-path-env"
    if name.endswith((".pem", ".p12", ".pfx")):
        return "sensitive-path-key-material"
    if name.endswith(".agekey") or "private-backups" in parts:
        return "sensitive-path-private-backup"
    if name in {"credentials.json", "service-account.json", "service_account.json"}:
        return "sensitive-path-credentials"
    return None


def likely_binary(data: bytes) -> bool:
    sample = data[:8192]
    return b"\x00" in sample


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_blob(oid: str, path: str, max_bytes: int) -> list[Finding]:
    findings: list[Finding] = []
    path_kind = suspicious_path(path)
    if path_kind:
        findings.append(Finding(oid=oid, path=path or "<unknown>", kind=path_kind))

    data = git("cat-file", "blob", oid, binary=True)
    assert isinstance(data, bytes)
    if len(data) > max_bytes or likely_binary(data):
        return findings

    text = data.decode("utf-8", errors="replace")
    for kind, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(
                Finding(
                    oid=oid,
                    path=path or "<unknown>",
                    kind=kind,
                    line=line_number(text, match.start()),
                )
            )

    for match in LITERAL_ASSIGNMENT.finditer(text):
        findings.append(
            Finding(
                oid=oid,
                path=path or "<unknown>",
                kind=f"literal-sensitive-assignment:{match.group(1)}",
                line=line_number(text, match.start()),
            )
        )

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--max-blob-bytes",
        type=int,
        default=DEFAULT_MAX_BLOB_BYTES,
        help="maximum blob size to decode and regex-scan (default: 2 MiB)",
    )
    args = ap.parse_args()

    try:
        ensure_repo()
        rows = object_inventory()
    except RuntimeError as exc:
        print(f"PUBLIC HISTORY SECRET SCAN ERROR: {exc}", file=sys.stderr)
        return 3

    # Same blob can appear under different historical paths. Keep one scan per
    # oid, but preserve every sensitive historical path finding.
    blob_rows = [(oid, size, path) for oid, typ, size, path in rows if typ == "blob"]
    scanned_oids: set[str] = set()
    findings: list[Finding] = []
    skipped_large = 0

    for oid, size, path in blob_rows:
        path_kind = suspicious_path(path)
        if path_kind:
            findings.append(Finding(oid=oid, path=path or "<unknown>", kind=path_kind))

        if oid in scanned_oids:
            continue
        scanned_oids.add(oid)

        if size > args.max_blob_bytes:
            skipped_large += 1
            continue

        try:
            data = git("cat-file", "blob", oid, binary=True)
            assert isinstance(data, bytes)
        except RuntimeError as exc:
            print(f"PUBLIC HISTORY SECRET SCAN ERROR: {exc}", file=sys.stderr)
            return 3

        if likely_binary(data):
            continue

        text = data.decode("utf-8", errors="replace")
        canonical_path = path or "<unknown>"

        for kind, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        oid=oid,
                        path=canonical_path,
                        kind=kind,
                        line=line_number(text, match.start()),
                    )
                )

        for match in LITERAL_ASSIGNMENT.finditer(text):
            findings.append(
                Finding(
                    oid=oid,
                    path=canonical_path,
                    kind=f"literal-sensitive-assignment:{match.group(1)}",
                    line=line_number(text, match.start()),
                )
            )

    unique = sorted(set(findings), key=lambda f: (f.path, f.kind, f.oid, f.line or 0))

    print(
        "PUBLIC HISTORY SECRET SCAN SUMMARY "
        f"reachable_objects={len(rows)} "
        f"unique_blobs={len(scanned_oids)} "
        f"large_blobs_skipped={skipped_large} "
        f"findings={len(unique)}"
    )

    if unique:
        print("FINDINGS (values intentionally redacted/not printed):")
        for finding in unique:
            location = f":{finding.line}" if finding.line is not None else ""
            print(f"- {finding.kind} {finding.path}{location} blob={finding.oid}")
        print(
            "REVIEW REQUIRED: rotate/revoke real credentials before history/log cleanup; "
            "document false positives without copying secret values."
        )
        return 2

    print("PUBLIC HISTORY SECRET SCAN OK: no high-confidence findings in scanned reachable text blobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
