#!/usr/bin/env python3
"""Scan reachable Git history for public-repository privacy/security blockers.

Zero network. No third-party packages. Secret values and Email values are never
printed.

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


DEFAULT_MAX_BLOB_BYTES = 8 * 1024 * 1024

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

LITERAL_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(" + "|".join(map(re.escape, SENSITIVE_ENV_NAMES)) +
    r")\s*[:=]\s*['\"]?(?!\$\{|\$[A-Za-z_(])[^'\"\s#]{16,}"
)

NOREPLY_EMAILS = {
    "noreply@github.com",
}


@dataclass(frozen=True)
class Finding:
    object_id: str
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
    return b"\x00" in data[:8192]


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_noreply_email(value: str) -> bool:
    email = value.strip().lower()
    if not email:
        return True
    if email in NOREPLY_EMAILS:
        return True
    return email.endswith("@users.noreply.github.com")


def scan_commit_metadata() -> list[Finding]:
    raw = str(git("log", "--all", "--format=%H%x09%ae%x09%ce"))
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        commit, author_email, committer_email = parts
        if author_email and not is_noreply_email(author_email):
            key = (commit, "author")
            if key not in seen:
                seen.add(key)
                findings.append(
                    Finding(
                        object_id=commit,
                        path="<commit-metadata>",
                        kind="non-noreply-author-email",
                    )
                )
        if committer_email and not is_noreply_email(committer_email):
            key = (commit, "committer")
            if key not in seen:
                seen.add(key)
                findings.append(
                    Finding(
                        object_id=commit,
                        path="<commit-metadata>",
                        kind="non-noreply-committer-email",
                    )
                )

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--max-blob-bytes",
        type=int,
        default=DEFAULT_MAX_BLOB_BYTES,
        help="maximum text blob size to regex-scan (default: 8 MiB); skipped text blobs fail closed",
    )
    args = ap.parse_args()

    try:
        ensure_repo()
        rows = object_inventory()
        findings = scan_commit_metadata()
    except RuntimeError as exc:
        print(f"PUBLIC HISTORY SCAN ERROR: {exc}", file=sys.stderr)
        return 3

    blob_rows = [(oid, size, path) for oid, typ, size, path in rows if typ == "blob"]
    scanned_oids: set[str] = set()
    large_text_oids: set[str] = set()

    for oid, size, path in blob_rows:
        path_kind = suspicious_path(path)
        if path_kind:
            findings.append(Finding(object_id=oid, path=path or "<unknown>", kind=path_kind))

        if oid in scanned_oids:
            continue
        scanned_oids.add(oid)

        try:
            data = git("cat-file", "blob", oid, binary=True)
            assert isinstance(data, bytes)
        except RuntimeError as exc:
            print(f"PUBLIC HISTORY SCAN ERROR: {exc}", file=sys.stderr)
            return 3

        if likely_binary(data):
            continue

        canonical_path = path or "<unknown>"
        if size > args.max_blob_bytes:
            large_text_oids.add(oid)
            findings.append(
                Finding(
                    object_id=oid,
                    path=canonical_path,
                    kind="large-text-blob-not-regex-scanned",
                )
            )
            continue

        text = data.decode("utf-8", errors="replace")

        for kind, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        object_id=oid,
                        path=canonical_path,
                        kind=kind,
                        line=line_number(text, match.start()),
                    )
                )

        for match in LITERAL_ASSIGNMENT.finditer(text):
            findings.append(
                Finding(
                    object_id=oid,
                    path=canonical_path,
                    kind=f"literal-sensitive-assignment:{match.group(1)}",
                    line=line_number(text, match.start()),
                )
            )

    unique = sorted(
        set(findings),
        key=lambda f: (f.path, f.kind, f.object_id, f.line or 0),
    )

    email_findings = sum(1 for f in unique if "email" in f.kind)
    secret_findings = sum(
        1
        for f in unique
        if f.kind not in {
            "non-noreply-author-email",
            "non-noreply-committer-email",
            "large-text-blob-not-regex-scanned",
        }
    )

    print(
        "PUBLIC HISTORY SCAN SUMMARY "
        f"reachable_objects={len(rows)} "
        f"unique_blobs={len(scanned_oids)} "
        f"large_text_blobs_unscanned={len(large_text_oids)} "
        f"secret_or_sensitive_path_findings={secret_findings} "
        f"non_noreply_email_findings={email_findings} "
        f"total_findings={len(unique)}"
    )

    if unique:
        print("FINDINGS (secret and Email values intentionally redacted/not printed):")
        for finding in unique:
            location = f":{finding.line}" if finding.line is not None else ""
            print(
                f"- {finding.kind} {finding.path}{location} "
                f"object={finding.object_id}"
            )
        print(
            "REVIEW REQUIRED: rotate/revoke real credentials before history/log cleanup; "
            "decide whether non-noreply commit Email exposure is acceptable; "
            "re-scan any skipped large text blob with a higher limit."
        )
        return 2

    print(
        "PUBLIC HISTORY SCAN OK: no high-confidence secret/sensitive-path findings, "
        "no non-noreply commit Email metadata, and no large text blobs were skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
