#!/usr/bin/env python3
"""Fail-closed public-repository history audit for SWSI.

This script is intentionally zero-network. Run it from a complete local clone after:

    git fetch --all --tags --prune
    python3 scripts/public_repo_history_secret_scan.py

Optional identity review patterns can be supplied from a file *outside this Git
working tree* so names or other private identifiers never need to be committed:

    SWSI_IDENTITY_REVIEW_PATTERNS_FILE=/private/path/patterns.txt \
      python3 scripts/public_repo_history_secret_scan.py

Each non-empty, non-comment line in that file is treated as a regular expression.
The script never prints matched credential values, Email addresses, or private
identity patterns. Findings report only object/path/category metadata.
"""

from __future__ import annotations

import hashlib
import os
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
OPAQUE_CONTAINER_EXTENSIONS = {
    ".zip", ".7z", ".rar", ".gz", ".tgz", ".bz2", ".xz",
    ".p12", ".pfx", ".jks", ".keystore", ".age", ".gpg", ".pgp",
    ".sqlite", ".sqlite3", ".db", ".dump", ".bak",
}
PLACEHOLDER_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "invalid"}


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


def compile_secret_patterns() -> dict[str, re.Pattern[bytes]]:
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


SENSITIVE_ASSIGNMENT_RE = re.compile(
    rb"(?im)^\s*(?:export\s+)?"
    rb"(SUPABASE_SERVICE_ROLE_KEY|SERVICE_ROLE_KEY|NETLIFY_AUTH_TOKEN|"
    rb"CLOUDFLARE_API_TOKEN|CLOUDFLARE_API_KEY|GROQ_API_KEY|OPENAI_API_KEY|"
    rb"GITHUB_TOKEN|GH_TOKEN|DATABASE_URL|SUPABASE_DB_PASSWORD|POSTGRES_PASSWORD|"
    rb"JWT_SECRET|CRON_SECRET|SWSI_INTERNAL_KEY|AI_PROXY_INTERNAL_KEY)"
    rb"\s*(?:=|:)\s*[\"']?([^\s\"'`#]{8,})"
)
EMAIL_RE = re.compile(rb"(?i)(?<![A-Z0-9._%+\-])[A-Z0-9._%+\-]{1,64}@(?:[A-Z0-9\-]+\.)+[A-Z]{2,63}")


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


def is_placeholder_email(raw: bytes) -> bool:
    email = raw.decode("ascii", "ignore").strip().lower()
    if not email or "@" not in email:
        return True
    local, domain = email.rsplit("@", 1)
    if domain == "users.noreply.github.com" or email == "noreply@github.com":
        return True
    if domain in PLACEHOLDER_EMAIL_DOMAINS or domain.endswith(".example.com"):
        return True
    if local in {"user", "username", "name", "email", "test", "example"} and domain.startswith("example"):
        return True
    return False


def load_external_identity_patterns() -> list[tuple[str, re.Pattern[str]]]:
    configured = os.environ.get("SWSI_IDENTITY_REVIEW_PATTERNS_FILE", "").strip()
    if not configured:
        return []
    path = Path(configured).expanduser().resolve()
    root = ROOT.resolve()
    if path == root or root in path.parents:
        raise RuntimeError("identity review patterns file must live outside the Git working tree")
    if not path.is_file():
        raise RuntimeError("identity review patterns file does not exist")

    patterns: list[tuple[str, re.Pattern[str]]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        pattern = raw.strip()
        if not pattern or pattern.startswith("#"):
            continue
        digest = hashlib.sha256(pattern.encode("utf-8")).hexdigest()[:12]
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise RuntimeError(f"invalid external identity regex id={digest}: {exc}") from exc
        patterns.append((digest, compiled))
    return patterns


def scan_blobs() -> tuple[list[Finding], list[Finding], int, int, int]:
    secret_patterns = compile_secret_patterns()
    identity_patterns = load_external_identity_patterns()
    credential_findings: list[Finding] = []
    identity_findings: list[Finding] = []
    scanned = 0
    skipped_large_text = 0
    binary_blobs = 0

    for oid, _, size, path in reachable_objects():
        safe_path = path or "<unknown path>"

        # We already know the blob size from batch-check. Do not load a huge blob
        # merely to discover that it exceeds the fail-closed audit limit.
        if size > MAX_TEXT_BLOB_BYTES:
            suffix = Path(path).suffix.lower()
            if suffix in TEXT_EXTENSIONS or Path(path).name.lower().startswith(".env"):
                skipped_large_text += 1
                credential_findings.append(
                    Finding(
                        "unscanned-large-text-blob",
                        oid,
                        safe_path,
                        f"size={size} exceeds audit limit={MAX_TEXT_BLOB_BYTES}",
                    )
                )
            elif suffix in OPAQUE_CONTAINER_EXTENSIONS:
                credential_findings.append(
                    Finding("opaque-history-container", oid, safe_path, f"size={size}; manual extraction/review required")
                )
            continue

        data = git("cat-file", "blob", oid)
        if not looks_textual(path, data):
            binary_blobs += 1
            if Path(path).suffix.lower() in OPAQUE_CONTAINER_EXTENSIONS:
                credential_findings.append(
                    Finding("opaque-history-container", oid, safe_path, f"size={size}; binary/container content not text-scannable")
                )
            continue

        scanned += 1
        for name, pattern in secret_patterns.items():
            if pattern.search(data):
                credential_findings.append(Finding("secret-pattern", oid, safe_path, name))

        sensitive_assignments = list(SENSITIVE_ASSIGNMENT_RE.finditer(data))
        if sensitive_assignments:
            names = sorted({m.group(1).decode("ascii", "ignore").upper() for m in sensitive_assignments})
            credential_findings.append(
                Finding(
                    "sensitive-literal-assignment",
                    oid,
                    safe_path,
                    "variables=" + ",".join(names),
                )
            )

        emails = [m.group(0) for m in EMAIL_RE.finditer(data)]
        review_emails = [email for email in emails if not is_placeholder_email(email)]
        if review_emails:
            identity_findings.append(
                Finding(
                    "historical-inline-email",
                    oid,
                    safe_path,
                    f"count={len(review_emails)}; values redacted",
                )
            )

        if identity_patterns:
            text = data.decode("utf-8", "replace")
            matched_ids = [pattern_id for pattern_id, pattern in identity_patterns if pattern.search(text)]
            if matched_ids:
                identity_findings.append(
                    Finding(
                        "external-identity-pattern",
                        oid,
                        safe_path,
                        "pattern_ids=" + ",".join(sorted(set(matched_ids))),
                    )
                )

    return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs


SENSITIVE_HISTORY_PATH_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.)", re.I),
    re.compile(r"(^|/)(private[-_]?backups?|restore[-_]?reports?)(/|$)", re.I),
    re.compile(r"\.agekey$", re.I),
    re.compile(r"swsi-supabase-private-.*\.tar\.age(?:\.sha256)?$", re.I),
    re.compile(r"\.(?:p12|pfx|jks|keystore|sqlite3?|db|dump)(?:$|\.)", re.I),
    re.compile(r"\.(?:zip|7z|rar|tgz|tar\.gz|tar\.bz2|tar\.xz)(?:$|\.)", re.I),
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
    """Inventory accepted public commit-email metadata without printing values."""
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
            findings.append(Finding("accepted-public-email-metadata", commit, "<commit metadata>", role))
    return findings


def print_findings(title: str, findings: list[Finding], stream) -> None:
    if not findings:
        return
    print(title, file=stream)
    for finding in findings:
        print(
            f"- kind={finding.kind} object={finding.object_id[:12]} "
            f"path={finding.path!r} detail={finding.detail!r}",
            file=stream,
        )


def main() -> int:
    ensure_complete_repo_shape()

    credential_findings = scan_historical_paths()
    blob_credentials, identity_findings, blob_count, skipped_large, binary_count = scan_blobs()
    credential_findings.extend(blob_credentials)
    metadata_findings = scan_commit_email_metadata()

    print(
        "PUBLIC REPO HISTORY AUDIT "
        f"blobs_scanned={blob_count} "
        f"binary_blobs_skipped={binary_count} "
        f"large_text_unscanned={skipped_large} "
        f"credential_blocking_findings={len(credential_findings)} "
        f"identity_review_findings={len(identity_findings)} "
        f"accepted_email_metadata_entries={len(metadata_findings)}"
    )

    if metadata_findings:
        unique_commits = len({f.object_id for f in metadata_findings})
        print(
            "INFO accepted public commit-email metadata present "
            f"commits={unique_commits} entries={len(metadata_findings)} "
            "(owner accepted 2026-10-04; values redacted)"
        )

    print_findings(
        "CREDENTIAL BLOCKING FINDINGS (secret values are never printed):",
        credential_findings,
        sys.stderr,
    )
    print_findings(
        "IDENTITY REVIEW FINDINGS (identity values are never printed):",
        identity_findings,
        sys.stderr,
    )

    if credential_findings:
        print("PUBLIC REPO HISTORY AUDIT FAIL — credential/security review required", file=sys.stderr)
        return 1
    if identity_findings:
        print("PUBLIC REPO HISTORY AUDIT REVIEW REQUIRED — identity/privacy classification pending", file=sys.stderr)
        return 2

    print("PUBLIC REPO HISTORY AUDIT PASS — no blocking credential or identity findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
