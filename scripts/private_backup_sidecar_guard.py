#!/usr/bin/env python3
"""Verify a local encrypted backup's mandatory SHA-256 sidecar before decryption.

Only checks encrypted bytes and their paired filename, never decrypts or reads
private records. Does not authenticate the author of either local file.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


class SidecarRejected(ValueError):
    pass


def verify(bundle: Path) -> str:
    sidecar = Path(str(bundle) + ".sha256")
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size == 0:
        raise SidecarRejected("encrypted bundle is not a nonempty regular file")
    if sidecar.is_symlink() or not sidecar.is_file() or sidecar.stat().st_size == 0:
        raise SidecarRejected("matching SHA-256 sidecar is missing")

    # Backup creator emits precisely: <64 lowercase hex><two spaces><basename>\n
    # Restrict metadata to one short line, never loading arbitrary files into RAM.
    with sidecar.open("rb") as handle:
        raw = handle.read(257)
    if len(raw) > 256:
        raise SidecarRejected("sidecar is oversized")
    try:
        line = raw.decode("ascii").removesuffix("\n")
    except UnicodeDecodeError:
        raise SidecarRejected("invalid sidecar encoding") from None
    matched = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
    if not matched or matched.group(2) != bundle.name:
        raise SidecarRejected("SHA-256 sidecar format or paired filename mismatch")

    digest = hashlib.sha256()
    with bundle.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != matched.group(1):
        raise SidecarRejected("encrypted bundle SHA-256 mismatch")
    return actual


def main() -> int:
    if len(sys.argv) != 2:
        print("PRIVATE BACKUP SIDECAR REFUSED: one encrypted bundle required", file=sys.stderr)
        return 64
    try:
        digest = verify(Path(sys.argv[1]))
    except (SidecarRejected, OSError):
        print("PRIVATE BACKUP SIDECAR REFUSED: missing, mismatched, or unsafe pair", file=sys.stderr)
        return 64
    print(f"ENCRYPTED BUNDLE SHA256 OK {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
