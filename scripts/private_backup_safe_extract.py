#!/usr/bin/env python3
"""Extract exactly the five SWSI private-backup components, never tar paths/links.

Consumes an authenticated age-decrypted plaintext TAR only via stdin. Files are
written solely inside a separately created, initially empty private temporary
folder. This does NOT prove authenticity of the bundle's creator or a restore.
"""
from __future__ import annotations

import os
import sys
import tarfile
from pathlib import Path

MAX_BYTES = {
    "roles.sql": 16 * 1024 * 1024,
    "schema.sql": 256 * 1024 * 1024,
    "data.sql": 4 * 1024 * 1024 * 1024,
    "source-counts.json": 2 * 1024 * 1024,
    "metadata.json": 2 * 1024 * 1024,
}


class ArchiveRejected(ValueError):
    pass


def extract(destination: Path) -> None:
    if not destination.is_dir() or any(destination.iterdir()):
        raise ArchiveRejected("destination must be an empty directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    dir_fd = os.open(destination, flags)
    found: set[str] = set()
    try:
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
            for member in archive:
                name = member.name
                if (
                    name not in MAX_BYTES
                    or name in found
                    or not member.isfile()
                    or getattr(member, "sparse", None)
                    or not 0 < member.size <= MAX_BYTES[name]
                ):
                    raise ArchiveRejected("unexpected TAR member or unsafe entry")
                source = archive.extractfile(member)
                if source is None:
                    raise ArchiveRejected("missing TAR member contents")
                file_fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                    dir_fd=dir_fd,
                )
                try:
                    with os.fdopen(file_fd, "wb") as dest:
                        remaining = member.size
                        while remaining:
                            block = source.read(min(1024 * 1024, remaining))
                            if not block:
                                raise ArchiveRejected("truncated TAR member")
                            dest.write(block)
                            remaining -= len(block)
                finally:
                    source.close()
                found.add(name)
    finally:
        os.close(dir_fd)
    if found != set(MAX_BYTES):
        raise ArchiveRejected("missing required TAR members")


def main() -> int:
    if len(sys.argv) != 2:
        print("PRIVATE BACKUP EXTRACTION REFUSED: expected one private destination", file=sys.stderr)
        return 64
    try:
        extract(Path(sys.argv[1]))
    except (ArchiveRejected, OSError, EOFError, tarfile.TarError):
        # Never echo paths, contents, decrypted data or archive metadata.
        print("PRIVATE BACKUP EXTRACTION REFUSED: unsafe or incomplete archive", file=sys.stderr)
        return 64
    print("PRIVATE BACKUP SAFE EXTRACTION OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
