#!/usr/bin/env python3
"""Fail-closed public-repository history audit for SWSI.

This script is intentionally zero-network. Run it from a complete local clone after:

    git fetch --all --tags --prune

It scans reachable Git history rather than only the current worktree. Findings are
redacted: the script reports object/path/pattern metadata and never prints the
matched secret value.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BLOB_BYTES = 8 * 1024 * 1024
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".py", ".sh", ".ps1", ".sql", ".yml", ".yaml", ".toml", ".ini", ".env",
    ".csv", ".xml", ".html", ".css", ".properties", ".conf", ".config",
}


@dataclass(frozen=True)
class Finding:
    kind: str
    object_id: str
    path: str
    detail: str


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return proc.stdout


def ensure_complete_repo_shape() -> None:
    if not (ROOT / ".git").exists():
        raise RuntimeError("run from a normal Git clone with .git metadata present")
    shallow = git("rev-parse", "--is-shallow-repository").decode().strip()
    if shallow == "true":
        raise RuntimeError("shallow clone detected; fetch full history before auditing")
    refs = git("for-each-ref", "--format=%(refname)").decode().splitlines()
    if not refs:
        raise RuntimeError("no refs found; cannot prove repository history coverage")


def compile_patterns() -> dict[str, re.Pattern[bytes]]:
    # High-confidence credential formats only. Names such as SUPABASE_SERVICE_ROLE_KEY
    # are not findings by themselves.
    raw = {
        "private-key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "github-token": rb"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{20,})\b",
        "supabase-secret": rb"\bsb_secret_[A-Za-z0-9_-]{20,}\b",
        "openai-style-secret": rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b",
        "groq-style-secret": rb"\bgsk_[A-Za-z0-9_-]{20,}\b",
        "jwt-value": rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        "aws-access-key": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    }
    return {name: re.compile(pattern) for name, pattern in raw.items()}


def reachable_objects() -> list[tuple[str, str, int, str]]:
    """Return unique reachable blobs as (oid, type, size, first_path)."""
    raw = git("rev-list", "--objects", "--all").decode("utf-8", "replace").splitlines()
    by_oid: dict[str, str] = {}
    for line in raw:
        if not line.strip():
            continue
        oid, _, path = line.partition(" ")
        by_oid.setdefault(oid, path)

    if not by_oid:
        raise RuntimeError("rev-list returned no objects")

    payload = ("\n".join(by_oid) + "\n").encode()
    batch = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", input_bytes=payload)
    rows: list[tuple[str, str, int, str]] = []
    for line in batch.decode().splitlines():
        oid, obj_type, size_s = line.split(" ", 2)
        if obj_type == "blob":
            rows.append((oid, obj_type, int(size_s), by_oid.get(oid, "")))
    return rows


def looks_textual(path: str, data: bytes) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix in TEXT_EXTENSIONS or Path(path).name.lower().startswith(".env"):
        return True
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    if not sample:
        return True
    printable = sum((32 <= b <= 126) or b in (9, 10, 13) or b >= 0x80 for b in sample)
    return printable / len(sample) >= 0.85


def scan_blobs() -> tuple[list[Finding], int, int]:
    patterns = compile_patterns()
    findings: list[Finding] = []
    scanned = 0
    skipped_large_text = 0

    for oid, _, size, path in reachable_objects():
        # Read a tiny sample first so binary blobs are not pulled into memory unnecessarily.
        data = git("cat-file", "blob", oid)
        if not looks_textual(path, data):
            continue
        if size > MAX_TEXT_BLOB_BYTES:
            skipped_large_text += 1
            findings.append(
                Finding(
                    "unscanned-large-text-blob",
                    oid,
                    path or "<unknown path>",
                    f"size={size} exceeds fail-closed audit limit={MAX_TEXT_BLOB_BYTES}",
                )
            )
            continue
        scanned += 1
        for name, pattern in patterns.items():
            if pattern.search(data):
                findings.append(Finding("secret-pattern", oid, path or "<unknown path>", name))

    return findings, scanned, skipped_large_text


SENSITIVE_HISTORY_PATH_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.)", re.I),
    re.compile(r"(^|/)(private[-_]?backups?|restore[-_]?reports?)(/|$)", re.I),
    re.compile(r"\.agekey$", re.I),
    re.compile(r"swsi-supabase-private-.*\.tar\.age(?:\.sha256)?$", re.I),
]


def scan_historical_paths() -> list[Finding]:
    findings: list[Finding] = []
    lines = git("rev-list", "--objects", "--all").decode("utf-8", "replace").splitlines()
    seen: set[tuple[str, str]] = set()
    for line in lines:
        oid, _, path = line.partition(" ")
        if not path:
            continue
        for pattern in SENSITIVE_HISTORY_PATH_PATTERNS:
            if pattern.search(path):
                key = (oid, path)
                if key not in seen:
                    seen.add(key)
                    findings.append(Finding("sensitive-history-path", oid, path, pattern.pattern))
                break
    return findings


def scan_commit_email_metadata() -> list[Finding]:
    """Report public-identity email metadata without printing the addresses.

    Historical non-noreply email is intentionally informational rather than a
    secret-pattern failure. Owner decision dated 2026-10-04 accepts this exposure,
    so the scanner records counts/commit IDs but does not block publication for it.
    """
    fmt = "%H%x00%ae%x00%ce"
    raw = git("log", "--all", f"--format={fmt}").decode("utf-8", "replace")
    findings: list[Finding] = []
    for line in raw.splitlines():
        parts = line.split("\x00")
        if len(parts) != 3:
            continue
        commit, author_email, committer_email = parts
        for role, email in (("author", author_email), ("committer", committer_email)):
            normalized = email.strip().lower()
            if not normalized:
                continue
            if normalized.endswith("@users.noreply.github.com") or normalized == "noreply@github.com":
                continue
            # Redact the address. Commit ID + role is sufficient to inventory exposure.
            findings.append(Finding("accepted-public-email-metadata", commit, "<commit metadata>", role))
    return findings


def main() -> int:
    ensure_complete_repo_shape()
    blocking_findings: list[Finding] = []
    informational_findings: list[Finding] = []

    path_findings = scan_historical_paths()
    blob_findings, blob_count, skipped_large = scan_blobs()
    email_findings = scan_commit_email_metadata()

    blocking_findings.extend(path_findings)
    blocking_findings.extend(blob_findings)
    informational_findings.extend(email_findings)

    print(
        "PUBLIC REPO HISTORY AUDIT "
        f"blobs_scanned={blob_count} "
        f"large_text_unscanned={skipped_large} "
        f"blocking_findings={len(blocking_findings)} "
        f"accepted_email_metadata_entries={len(informational_findings)}"
    )

    if informational_findings:
        unique_commits = len({f.object_id for f in informational_findings})
        print(
            "INFO accepted public commit-email metadata present "
            f"commits={unique_commits} entries={len(informational_findings)} "
            "(owner accepted 2026-10-04; values redacted)"
        )

    if blocking_findings:
        print("BLOCKING FINDINGS (secret values are never printed):", file=sys.stderr)
        for finding in blocking_findings:
            short_oid = finding.object_id[:12]
            print(
                f"- kind={finding.kind} object={short_oid} "
                f"path={finding.path!r} detail={finding.detail!r}",
                file=sys.stderr,
            )
        return 1

    print("PUBLIC REPO HISTORY SECRET AUDIT PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
