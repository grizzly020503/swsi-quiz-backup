#!/usr/bin/env python3
"""Focused fail-closed regression checks for public history classification."""

import base64
import io
import json
import zipfile

import public_repo_history_secret_scan as scan


def jwt(role: str, *, ref: str = scan.SUPABASE_PUBLIC_PROJECT_REF) -> bytes:
    def part(value: dict) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
    return b".".join((
        part({"alg": "HS256", "typ": "JWT"}),
        part({"iss": "supabase", "ref": ref, "role": role, "iat": 100, "exp": 200}),
        b"synthetic_signature_not_a_real_key",
    ))


def hits(data: bytes, path: str) -> list[scan.Finding]:
    return scan.scan_text_payload(data, "synthetic-object", path, scan.compile_secret_patterns(), [])[0]


def main() -> None:
    prefix = b'const CONFIG = { url: "https://' + scan.SUPABASE_PUBLIC_PROJECT_REF.encode() + b'.supabase.co", key: "'
    assert not hits(prefix + jwt("anon") + b'" };', "index.html")
    assert hits(prefix + jwt("service_role") + b'" };', "index.html")
    assert hits(prefix + jwt("anon", ref="another-project-ref") + b'" };', "index.html")
    assert hits(b'const token = "' + jwt("anon") + b'";', "index.html")
    assert hits(prefix + jwt("anon") + b'" };', "server/index.ts")

    postgres = b"POSTGRES_" + b"PASSWORD: postgres"
    assert not hits(postgres, ".github/workflows/disaster-recovery-drill.yml")
    assert hits(postgres, ".github/workflows/production.yml")
    assert hits(b"POSTGRES_" + b"PASSWORD: actual-password", ".github/workflows/disaster-recovery-drill.yml")
    internal = b"SWSI_INTERNAL_" + b"KEY: internal-secret"
    assert not hits(internal, "scripts/cloudflare_worker_smoke.js")
    assert hits(internal, "scripts/production.js")
    assert hits(b"SWSI_INTERNAL_" + b"KEY: real-secret-value", "scripts/cloudflare_worker_smoke.js")
    assert not hits(b"fixture@qa.invalid", "scripts/fixture.py")
    ordinary_email = b"person@" + b"real-domain.com"
    assert hits(ordinary_email, "scripts/fixture.py") == []  # identity is a separate review stream
    assert scan.scan_text_payload(ordinary_email, "synthetic-object", "scripts/fixture.py", scan.compile_secret_patterns(), [])[1]

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("index.html", prefix + jwt("anon") + b'" };')
    blocked, _ = scan.scan_reviewed_zip(output.getvalue(), "synthetic-object", "new-package.zip", scan.compile_secret_patterns(), [])
    assert any(f.kind == "opaque-history-container" for f in blocked)
    binary_findings = scan.scan_one_blob("synthetic-object", 3, "unknown.bin", b"\x00\x01\x02", scan.compile_secret_patterns(), [])[0]
    assert any(f.kind == "unreviewed-binary-blob" for f in binary_findings)
    disguised = b"A" * 4096 + b"\x00"
    assert not scan.looks_textual("disguised.txt", disguised)
    assert not scan.looks_textual("disguised.json", b"hello\xff")

    sample = scan.reachable_objects()[:2]
    for oid, contents in scan.read_blob_batch(sample).items():
        assert contents == scan.git("cat-file", "blob", oid)
    print("public history scanner fail-closed selftest PASS")


if __name__ == "__main__":
    main()
