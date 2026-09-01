#!/usr/bin/env python3
"""Build a conservative, history-free public SWSI source snapshot.

This script intentionally uses an allowlist. New files are NOT exported merely
because they appear in the private repository. The output is a plain directory
that can seed a brand-new repository; it must never include the source `.git`.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_FILES = (
    ".gitignore",
    "ARCHITECTURE.md",
    "essay_guides.js",
    "index.html",
    "manifest.json",
    "sw.js",
)

ROOT_DIRS = (
    "admin",
    "icons",
    "cloudflare/wandering-wave-4418",
    "supabase/functions",
    "supabase/migrations",
)

EXTRA_FILES = (
    "scripts/public_content_sanitize.py",
)

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
FORBIDDEN_SUFFIXES = {
    ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz",
    ".pem", ".key", ".p12", ".pfx", ".crt", ".cer",
}
FORBIDDEN_BASENAMES = {".env", ".npmrc", ".netrc"}

THIRD_PARTY_MARKERS = (
    "蔡宇庭",
    "老師提供的學長姐心得",
    "資深學長姐的應考心得",
    "這份心得是資深學長姐",
    "學長姊應考心得",
)

PERSONAL_MARKERS = (
    "熊品澄",
    "品澄",
)

SECRET_PATTERNS = {
    "private-key block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "GitHub classic token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "Groq-style secret": re.compile(r"\bgsk_[A-Za-z0-9_-]{20,}\b"),
    "Supabase secret key": re.compile(r"\bsb_secret_[A-Za-z0-9._-]{20,}\b"),
    "generic OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
}

EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9._%+-])")


def copy_file(src_root: Path, out_root: Path, rel: str) -> None:
    src = src_root / rel
    if not src.is_file():
        raise RuntimeError(f"required public snapshot file missing: {rel}")
    dst = out_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_dir(src_root: Path, out_root: Path, rel: str) -> None:
    src = src_root / rel
    if not src.is_dir():
        raise RuntimeError(f"required public snapshot directory missing: {rel}")
    dst = out_root / rel
    shutil.copytree(src, dst)


def check_path_safety(path: Path, rel: str) -> None:
    lower_name = path.name.lower()
    if lower_name in FORBIDDEN_BASENAMES or lower_name.startswith(".env."):
        raise RuntimeError(f"forbidden environment file in public snapshot: {rel}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        raise RuntimeError(f"forbidden binary/credential suffix in public snapshot: {rel}")
    if ".git" in path.parts:
        raise RuntimeError(f"Git metadata must never enter public snapshot: {rel}")


def scan_text(path: Path, rel: str) -> None:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"unexpected non-UTF8 file in public snapshot: {rel}") from exc

    for marker in THIRD_PARTY_MARKERS:
        if marker in text:
            raise RuntimeError(f"third-party study-guide marker survived public snapshot: {rel}: {marker}")

    for marker in PERSONAL_MARKERS:
        if marker in text:
            raise RuntimeError(f"personal identity marker survived public snapshot: {rel}: {marker}")

    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            raise RuntimeError(f"possible {label} in public snapshot: {rel}")

    for email in EMAIL_RE.findall(text):
        if email.lower().endswith("@users.noreply.github.com"):
            continue
        raise RuntimeError(f"personal/contact email requires explicit public review: {rel}: {email}")


def scan_snapshot(out_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(out_root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"symlinks are not allowed in public snapshot: {path.relative_to(out_root)}")
        if not path.is_file():
            continue
        rel = path.relative_to(out_root).as_posix()
        check_path_safety(path, rel)
        scan_text(path, rel)
        files.append(path)
    return files


def write_manifest(out_root: Path, files: list[Path]) -> None:
    rows = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {path.relative_to(out_root).as_posix()}")
    (out_root / "PUBLIC_SNAPSHOT_SHA256.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--output", default="dist/public-repo")
    args = parser.parse_args()

    src_root = Path(args.source_root).resolve()
    out_root = Path(args.output).resolve()

    if (src_root / ".git").resolve() == out_root:
        raise RuntimeError("output cannot be the source .git directory")
    if out_root == src_root or src_root in out_root.parents and out_root.name == ".git":
        raise RuntimeError("unsafe public snapshot output path")

    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    for rel in ROOT_FILES:
        copy_file(src_root, out_root, rel)
    for rel in ROOT_DIRS:
        copy_dir(src_root, out_root, rel)
    for rel in EXTRA_FILES:
        copy_file(src_root, out_root, rel)

    public_readme = src_root / "public_repo_template/README.md"
    if not public_readme.is_file():
        raise RuntimeError("missing public_repo_template/README.md")
    shutil.copy2(public_readme, out_root / "README.md")

    public_security = src_root / "public_repo_template/SECURITY.md"
    if not public_security.is_file():
        raise RuntimeError("missing public_repo_template/SECURITY.md")
    shutil.copy2(public_security, out_root / "SECURITY.md")

    sanitizer = src_root / "scripts/public_content_sanitize.py"
    subprocess.run(
        [sys.executable, str(sanitizer), str(out_root / "index.html")],
        check=True,
        cwd=src_root,
    )

    files = scan_snapshot(out_root)
    write_manifest(out_root, files)

    # Re-scan the generated manifest too. It should contain hashes and paths only.
    scan_text(out_root / "PUBLIC_SNAPSHOT_SHA256.txt", "PUBLIC_SNAPSHOT_SHA256.txt")

    print(f"PUBLIC REPO SNAPSHOT READY: {out_root}")
    print(f"files: {len(files) + 1}")
    print("This directory has no Git history. Create a NEW private repository before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
