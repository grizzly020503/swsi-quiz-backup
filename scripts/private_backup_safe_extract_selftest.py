#!/usr/bin/env python3
"""Synthetic-only malicious TAR regression suite; no age identities or DB."""
from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("private_backup_safe_extract.py")
FILES = ["roles.sql", "schema.sql", "data.sql", "source-counts.json", "metadata.json"]


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, kind, data in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                content = data.encode()
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
            elif kind in {"symlink", "hardlink"}:
                info.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
                info.linkname = data
                tar.addfile(info)
            elif kind == "directory":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
    return out.getvalue()


def case(name, entries, accepted):
    with tempfile.TemporaryDirectory() as parent:
        dest = Path(parent) / "extract"
        dest.mkdir()
        p = subprocess.run(
            [sys.executable, str(SCRIPT), str(dest)],
            input=archive(entries), capture_output=True, timeout=8,
        )
        passed = (p.returncode == 0) == accepted
        if accepted:
            passed = passed and {x.name for x in dest.iterdir()} == set(FILES)
            passed = passed and all(x.is_file() and not x.is_symlink() for x in dest.iterdir())
        if not passed:
            raise AssertionError(f"{name}: exit {p.returncode} stdout={p.stdout!r} stderr={p.stderr!r}")
        if name == "parent traversal":
            assert not (Path(parent) / "escape").exists(), "TAR escaped private temp folder"
        print(f"PASS {name} ({'accept' if accepted else 'reject'})")


def main():
    base = [(n, "file", f"synthetic:{n}") for n in FILES]
    cases = [
        ("canonical 5 files", base, True),
        ("missing metadata", base[:-1], False),
        ("extra file", base + [("something.txt", "file", "synthetic")], False),
        ("parent traversal", base + [("../escape", "file", "synthetic")], False),
        ("absolute path", base + [("/tmp/swsi-escape-test", "file", "synthetic")], False),
        ("subdirectory path", base + [("other/data.sql", "file", "synthetic")], False),
        ("duplicate component", base + [("data.sql", "file", "second")], False),
        ("empty required file", base[:-1] + [("metadata.json", "file", "")], False),
        ("symlink component", base[:-1] + [("metadata.json", "symlink", "/etc/passwd")], False),
        ("hardlink component", base[:-1] + [("metadata.json", "hardlink", "data.sql")], False),
        ("unexpected directory", base + [("aux", "directory", "")], False),
    ]
    for name, entries, accepted in cases:
        case(name, entries, accepted)
    print(f"SWSI SAFE TAR EXTRACTOR SELFTEST OK {len(cases)}/{len(cases)}")


if __name__ == '__main__':
    main()
