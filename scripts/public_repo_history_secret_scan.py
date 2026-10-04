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

import base64
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BLOB_BYTES = 8 * 1024 * 1024
MAX_REVIEWED_ZIP_BYTES = 16 * 1024 * 1024
SUPABASE_PUBLIC_PROJECT_REF = "yumjtrdctaxyczpspuyo"
# These exact historical ZIP bytes were inspected (entry paths/types, CRC,
# extracted text, and identity data). New or changed archives still block.
REVIEWED_ZIP_SHA256 = {
    "3518ff591d670f1677531cf0f62e9defbfdde61840bf58a74c3fe06049454d90",
    "d9f49ec58a61b910c8a6bd850a7833cfaf968967e373d4a70c347e4792c25d99",
    "9be50e5ecf58eaedcf9025d5bbbf0f000177848cd5e4ea447eb71b31407f370d",
    "654bdbdc59d7ecb063fc67b0d29240f2025f05b007bea8a9a782b46598ddda2f",
}
# The only other binary blobs in the audited refs are three PNG assets. Their
# chunks are IHDR/IDAT/IEND only (no text metadata), and no credential/email
# pattern appears in their bytes. Unknown binary content blocks publication.
REVIEWED_PNG_SHA256 = {
    "6e741ba47df5f42b3fba1b5ca1b8cefd73003fc230fd3d2e9b86e3f65f75a5f9",
    "17562e59d94321204b0e7c3596e864072d15dd1f89c7d85626c4ee8da829091d",
    "9faa01ebb151febb1183ff15379ad92a2fd2ff00cc6e2b2ca883f052f2572726",
}
# Issue #330: after the replacement production admin was verified and the
# legacy personal admin was removed from the allowlist, the owner accepted
# residual historical identity linkage without rewriting Git history. This
# exact immutable blob contains the old prefill; any changed/new blob blocks.
REVIEWED_HISTORICAL_ADMIN_IDENTITY = (
    "a7a7913afd1f15fc00bdc7372d67e74db01c7842",
    "cdn/preview/admin/index.html",
    "e532bab895ca80b7cc31b4f43c40ff940d52268d4093bced48cce2606201678c",
)
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
PLACEHOLDER_LITERAL_VALUES = {
    "changeme", "change-me", "replace-me", "replace_me", "placeholder",
    "redacted", "example", "your-token", "your_token", "your-secret", "your_secret",
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


def read_blob_batch(rows: list[tuple[str, str, int, str]]) -> dict[str, bytes]:
    """Read a bounded group through one Git process instead of one per blob."""
    requested = [oid for oid, _, size, _ in rows if size <= MAX_TEXT_BLOB_BYTES]
    if not requested:
        return {}
    raw = git("cat-file", "--batch", input_bytes=("\n".join(requested) + "\n").encode())
    offset = 0
    found: dict[str, bytes] = {}
    for expected in requested:
        line_end = raw.find(b"\n", offset)
        if line_end < 0:
            raise RuntimeError("git batch blob header missing")
        parts = raw[offset:line_end].decode("ascii", "replace").split()
        if len(parts) != 3 or parts[0] != expected or parts[1] != "blob":
            raise RuntimeError("git batch blob object mismatch")
        size = int(parts[2])
        start = line_end + 1
        end = start + size
        if end >= len(raw) or raw[end:end + 1] != b"\n":
            raise RuntimeError("git batch blob payload truncated")
        found[expected] = raw[start:end]
        offset = end + 1
    if offset != len(raw):
        raise RuntimeError("git batch blob output has unexpected trailing data")
    return found


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
    if domain in PLACEHOLDER_EMAIL_DOMAINS or domain.endswith((".example.com", ".invalid")):
        return True
    if local in {"user", "username", "name", "email", "test", "example"} and domain.startswith("example"):
        return True
    return False


def reviewed_test_assignment(name: str, value: bytes, path: str) -> bool:
    if name == "POSTGRES_PASSWORD" and value == b"postgres":
        return path in {
            ".github/workflows/disaster-recovery-drill.yml",
            ".github/workflows/disaster-recovery-restore-drill.yml",
            ".github/workflows/ops-ledger-candidate-db-qa.yml",
        }
    return name == "SWSI_INTERNAL_KEY" and value == b"internal-secret" and path == "scripts/cloudflare_worker_smoke.js"


def sensitive_literal_assignment_names(data: bytes, path: str) -> list[str]:
    """Return only unreviewed literal assignments, without exposing values."""
    names: set[str] = set()
    runtime_prefixes = (
        "$", "deno.env", "process.env", "os.environ", "os.getenv", "getenv(",
        "secrets.", "github.", "env.", "vars.",
    )
    for match in SENSITIVE_ASSIGNMENT_RE.finditer(data):
        raw_value = match.group(2)
        value = raw_value.decode("utf-8", "replace").strip()
        normalized = value.lower()
        if normalized.startswith(runtime_prefixes):
            continue
        if normalized.strip("<>[]{}()\"'") in PLACEHOLDER_LITERAL_VALUES:
            continue
        name = match.group(1).decode("ascii", "ignore").upper()
        if reviewed_test_assignment(name, raw_value, path):
            continue
        names.add(name)
    return sorted(names)


def is_public_supabase_anon_jwt(token: bytes, data: bytes, offset: int, path: str) -> bool:
    """Accept only legacy browser anon keys for this project; never trust a role label alone."""
    if path not in {"index.html", "cdn/index.html", "cdn/preview/index.html"} and not path.endswith("/index.html"):
        return False
    try:
        def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JWT field")
                result[key] = value
            return result

        header_b64, payload_b64, _ = token.split(b".")
        header = json.loads(base64.urlsafe_b64decode(header_b64 + b"=" * (-len(header_b64) % 4)), object_pairs_hook=unique_pairs)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + b"=" * (-len(payload_b64) % 4)), object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError):
        return False
    if header != {"alg": "HS256", "typ": "JWT"}:
        return False
    if set(payload) != {"exp", "iat", "iss", "ref", "role"}:
        return False
    if payload["iss"] != "supabase" or payload["ref"] != SUPABASE_PUBLIC_PROJECT_REF or payload["role"] != "anon":
        return False
    if type(payload["iat"]) is not int or type(payload["exp"]) is not int or payload["exp"] <= payload["iat"]:
        return False
    prefix = data[max(0, offset - 256):offset]
    return bool(re.search(
        rb'url\s*:\s*["\']https://' + SUPABASE_PUBLIC_PROJECT_REF.encode() + rb'\.supabase\.co["\']\s*,\s*key\s*:\s*["\']$',
        prefix,
        re.I,
    ))


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


def scan_text_payload(
    data: bytes, oid: str, path: str,
    secret_patterns: dict[str, re.Pattern[bytes]],
    identity_patterns: list[tuple[str, re.Pattern[str]]],
) -> tuple[list[Finding], list[Finding]]:
    credentials: list[Finding] = []
    identities: list[Finding] = []
    for name, pattern in secret_patterns.items():
        if name == "jwt-value":
            if any(not is_public_supabase_anon_jwt(m.group(0), data, m.start(), path) for m in pattern.finditer(data)):
                credentials.append(Finding("secret-pattern", oid, path, name))
        elif pattern.search(data):
            credentials.append(Finding("secret-pattern", oid, path, name))

    assignment_names = sensitive_literal_assignment_names(data, path)
    if assignment_names:
        credentials.append(Finding("sensitive-literal-assignment", oid, path, "variables=" + ",".join(assignment_names)))

    review_emails = [m.group(0) for m in EMAIL_RE.finditer(data) if not is_placeholder_email(m.group(0))]
    reviewed_identity_blob = (oid, path, hashlib.sha256(data).hexdigest()) == REVIEWED_HISTORICAL_ADMIN_IDENTITY
    if review_emails and not reviewed_identity_blob:
        identities.append(Finding("historical-inline-email", oid, path, f"count={len(review_emails)}; values redacted"))
    if identity_patterns:
        text = data.decode("utf-8", "replace")
        matched_ids = [pattern_id for pattern_id, pattern in identity_patterns if pattern.search(text)]
        if matched_ids:
            identities.append(Finding("external-identity-pattern", oid, path, "pattern_ids=" + ",".join(sorted(set(matched_ids)))))
    return credentials, identities


def scan_reviewed_zip(
    data: bytes, oid: str, path: str,
    secret_patterns: dict[str, re.Pattern[bytes]],
    identity_patterns: list[tuple[str, re.Pattern[str]]],
) -> tuple[list[Finding], list[Finding]]:
    if hashlib.sha256(data).hexdigest() not in REVIEWED_ZIP_SHA256:
        return [Finding("opaque-history-container", oid, path, "unreviewed ZIP SHA-256")], []
    credentials: list[Finding] = []
    identities: list[Finding] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > 1000:
                raise ValueError("invalid entry count")
            seen: set[str] = set()
            total_bytes = 0
            for entry in entries:
                member = entry.filename
                parts = PurePosixPath(member).parts
                if (not member or member.startswith("/") or "\\" in member or ":" in member
                        or any(part in {".", ".."} for part in parts)
                        or member.casefold() in seen):
                    raise ValueError("unsafe or duplicate entry path")
                seen.add(member.casefold())
                if entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("encrypted or symlink entry")
                if entry.is_dir():
                    continue
                total_bytes += entry.file_size
                if entry.file_size > MAX_TEXT_BLOB_BYTES or total_bytes > MAX_REVIEWED_ZIP_BYTES:
                    raise ValueError("entry or archive exceeds review limit")
                lower = member.lower()
                if (re.search(r"(^|/)\.env($|\.)", lower)
                        or re.search(r"(^|/)(private[-_]?backups?|restore[-_]?reports?)(/|$)", lower)
                        or Path(lower).suffix in OPAQUE_CONTAINER_EXTENSIONS):
                    raise ValueError("sensitive or nested entry path")
                contents = archive.read(entry)  # verifies the member CRC
                member_path = path + "!/" + member
                if contents.startswith(b"\x89PNG\r\n\x1a\n") and lower.endswith(".png"):
                    continue  # exact reviewed archive digest pins these image bytes
                if not looks_textual(member, contents):
                    raise ValueError("unreviewed binary entry")
                found_credentials, found_identities = scan_text_payload(
                    contents, oid, member_path, secret_patterns, identity_patterns,
                )
                credentials.extend(found_credentials)
                identities.extend(found_identities)
    except (ValueError, RuntimeError, zipfile.BadZipFile, OSError) as exc:
        credentials.append(Finding("opaque-history-container", oid, path, f"reviewed ZIP validation failed: {type(exc).__name__}"))
    return credentials, identities


def scan_blobs() -> tuple[list[Finding], list[Finding], int, int, int]:
    secret_patterns = compile_secret_patterns()
    identity_patterns = load_external_identity_patterns()
    credential_findings: list[Finding] = []
    identity_findings: list[Finding] = []
    scanned = skipped_large_text = binary_blobs = 0

    rows = reachable_objects()
    for group_start in range(0, len(rows), 128):
        group = rows[group_start:group_start + 128]
        blobs = read_blob_batch(group)
        for oid, _, size, path in group:
            credentials, identities, text_count, large_count, binary_count = scan_one_blob(
                oid, size, path, blobs.get(oid), secret_patterns, identity_patterns,
            )
            credential_findings.extend(credentials)
            identity_findings.extend(identities)
            scanned += text_count
            skipped_large_text += large_count
            binary_blobs += binary_count

    return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs


def scan_one_blob(
    oid: str, size: int, path: str, data: bytes | None,
    secret_patterns: dict[str, re.Pattern[bytes]],
    identity_patterns: list[tuple[str, re.Pattern[str]]],
) -> tuple[list[Finding], list[Finding], int, int, int]:
    credential_findings: list[Finding] = []
    identity_findings: list[Finding] = []
    scanned = skipped_large_text = binary_blobs = 0
    safe_path = path or "<unknown path>"
    suffix = Path(path).suffix.lower()
    if size > MAX_TEXT_BLOB_BYTES:
        if suffix in TEXT_EXTENSIONS or Path(path).name.lower().startswith(".env"):
            skipped_large_text += 1
            credential_findings.append(Finding("unscanned-large-text-blob", oid, safe_path, f"size={size} exceeds audit limit={MAX_TEXT_BLOB_BYTES}"))
        else:
            credential_findings.append(Finding("unscanned-large-blob", oid, safe_path, f"size={size} exceeds audit limit={MAX_TEXT_BLOB_BYTES}"))
        return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs

    if data is None or len(data) != size:
        raise RuntimeError("blob missing from git batch")
    if suffix == ".zip" or data.startswith(b"PK\x03\x04"):
        binary_blobs += 1
        credentials, identities = scan_reviewed_zip(data, oid, safe_path, secret_patterns, identity_patterns)
        credential_findings.extend(credentials)
        identity_findings.extend(identities)
        return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs
    if suffix in OPAQUE_CONTAINER_EXTENSIONS or data.startswith((b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x1f\x8b")):
        binary_blobs += 1
        credential_findings.append(Finding("opaque-history-container", oid, safe_path, "unreviewed container"))
        return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs
    if not looks_textual(path, data):
        binary_blobs += 1
        if not (suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() in REVIEWED_PNG_SHA256):
            credential_findings.append(Finding("unreviewed-binary-blob", oid, safe_path, f"size={size}"))
        return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs

    scanned += 1
    credentials, identities = scan_text_payload(data, oid, safe_path, secret_patterns, identity_patterns)
    credential_findings.extend(credentials)
    identity_findings.extend(identities)

    return credential_findings, identity_findings, scanned, skipped_large_text, binary_blobs


SENSITIVE_HISTORY_PATH_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.)", re.I),
    re.compile(r"(^|/)(private[-_]?backups?|restore[-_]?reports?)(/|$)", re.I),
    re.compile(r"\.agekey$", re.I),
    re.compile(r"swsi-supabase-private-.*\.tar\.age(?:\.sha256)?$", re.I),
    re.compile(r"\.(?:p12|pfx|jks|keystore|sqlite3?|db|dump)(?:$|\.)", re.I),
    re.compile(r"\.(?:7z|rar|tgz|tar\.gz|tar\.bz2|tar\.xz)$", re.I),
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
        f"binary_blobs_checked={binary_count} "
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
