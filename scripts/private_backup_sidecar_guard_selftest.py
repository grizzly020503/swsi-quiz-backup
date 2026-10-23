#!/usr/bin/env python3
"""Synthetic encrypted-bundle checksum tests: no age keys, DB or private data."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("private_backup_sidecar_guard.py")


def main() -> int:
    checks = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bundle = root / "swsi-supabase-private-20261024T010203Z-123456789abc.tar.age"
        sidecar = Path(str(bundle) + ".sha256")
        data = b"synthetic-ciphertext-only-no-student-data"
        digest = hashlib.sha256(data).hexdigest()
        bundle.write_bytes(data)

        def run(expected_ok: bool, label: str) -> None:
            nonlocal checks
            p = subprocess.run([sys.executable, str(SCRIPT), str(bundle)],
                               capture_output=True, text=True, timeout=5)
            assert (p.returncode == 0) is expected_ok, (label, p.returncode, p.stderr)
            if expected_ok:
                assert digest in p.stdout, p.stdout
            else:
                assert "PRIVATE BACKUP SIDECAR REFUSED" in p.stderr, p.stderr
            checks += 1
            print("PASS", label)

        run(False, "missing sidecar")
        sidecar.write_text("", encoding="ascii")
        run(False, "empty sidecar")
        sidecar.write_text("bad", encoding="ascii")
        run(False, "malformed sidecar")
        sidecar.write_text("f" * 64 + "  " + bundle.name + "\n", encoding="ascii")
        run(False, "digest mismatch")
        sidecar.write_text(digest + "  wrong-file.tar.age\n", encoding="ascii")
        run(False, "unpaired filename")
        sidecar.write_bytes((digest + "  " + bundle.name + "\n").encode() + b"X" * 300)
        run(False, "oversized sidecar")
        sidecar.unlink()
        external = root / "external.sha256"
        external.write_text(digest + "  " + bundle.name + "\n", encoding="ascii")
        sidecar.symlink_to(external)
        run(False, "sidecar symlink")
        sidecar.unlink()
        sidecar.write_text(digest + "  " + bundle.name + "\n", encoding="ascii")
        run(True, "matching SHA-256 and exact filename")
        bundle.write_bytes(data + b"modified")
        run(False, "mutated encrypted bytes")

    print(f"PRIVATE BACKUP SIDECAR SELFTEST OK {checks}/{checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
