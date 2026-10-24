#!/usr/bin/env python3
"""Offline negative-case test of the actual Netlify production-readiness gate.

Runs zero network calls, never uses credentials, and never deploys.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/netlify-controlled-production-deploy.yml"
MARKER = "2026-09-26-history-v2.2"


def extract_gate():
    source = WORKFLOW.read_text(encoding="utf-8")
    start_tag = '          expected_patch_sha="$(sha256sum _site/monthly_patch.js | cut -c1-16)"'
    end_tag = "\n          fetch_prod /sw.js /tmp/prod-sw.js\n"
    assert source.count(start_tag) == 1, "Netlify exact gate missing"
    start = source.index(start_tag)
    end = source.find(end_tag, start)
    assert end > start, "cannot bound Netlify readiness gate"
    gate = textwrap.dedent(source[start:end])
    for required in (
        'grep -Fq',
        'cmp -s _site/monthly_patch.js /tmp/prod-monthly-patch.js',
        'cmp -s _site/sw.js /tmp/prod-sw.js',
        'NETLIFY EXACT RUNTIME READY',
        'NO-GO',
        'exit 1',
    ):
        assert required in gate, f"release gate guard missing: {required}"
    assert "curl " not in gate and "netlify deploy" not in gate
    return gate


def run_fixture(root, name, gate, *, tag=True, js=True, sw=True,
                marker=MARKER, missing_js=False):
    case = root / name
    remote = case / "remote"
    site = case / "_site"
    remote.mkdir(parents=True)
    site.mkdir()
    patch = b"// new correct runtime\n"
    service_worker = b"const VERSION = 'v7';\n"
    (site / "monthly_patch.js").write_bytes(patch)
    (site / "sw.js").write_bytes(service_worker)
    digest = hashlib.sha256(patch).hexdigest()[:16]
    version = digest if tag else "deadbeefdeadbeef"
    (remote / "index.html").write_text(
        f'<meta name="swsi-netlify-release" content="{marker}">\n'
        f'<script src="monthly_patch.js?v={version}"></script>\n',
        encoding="utf-8",
    )
    if not missing_js:
        (remote / "monthly_patch.js").write_bytes(patch if js else b"// old runtime\n")
    (remote / "sw.js").write_bytes(service_worker if sw else b"const VERSION = 'v6';\n")

    # Substitute only the temporary result paths; checks use the EXACT workflow
    # condition and byte comparisons instead of a separately coded approximation.
    replacements = (
        ("/tmp/prod-index.html", str(case / "received-index.html")),
        ("/tmp/prod-monthly-patch.js", str(case / "received-monthly-patch.js")),
        ("/tmp/prod-sw.js", str(case / "received-sw.js")),
    )
    for old, new in replacements:
        gate = gate.replace(old, new)

    mock = """
set -euo pipefail
fetch_prod() {
  local path="$1"
  local output="$2"
  local source="$FAKE_REMOTE$path"
  if [ "$path" = "/" ]; then source="$FAKE_REMOTE/index.html"; fi
  [ -f "$source" ] || return 1
  cp "$source" "$output"
}
sleep() { :; }
EXPECTED_RELEASE_MARKER="2026-09-26-history-v2.2"
"""
    return subprocess.run(
        ["bash", "-c", mock + "\n" + gate],
        cwd=case,
        env={**os.environ, "FAKE_REMOTE": str(remote)},
        capture_output=True, text=True, timeout=20,
        check=False,
    )


def main():
    gate = extract_gate()
    cases = (
        ("matched", {}, True),
        ("stale_html_cache_bust_same_marker", {"tag": False}, False),
        ("stale_monthly_patch_same_marker", {"js": False}, False),
        ("stale_service_worker_same_marker", {"sw": False}, False),
        ("wrong_marker", {"marker": "previous-release"}, False),
        ("missing_monthly_patch", {"missing_js": True}, False),
    )
    with tempfile.TemporaryDirectory(prefix="swsi-netlify-readiness-") as tmp:
        for name, opts, should_pass in cases:
            result = run_fixture(Path(tmp), name, gate, **opts)
            is_pass = result.returncode == 0
            assert is_pass == should_pass, (
                f"{name}: expected pass={should_pass}, returncode={result.returncode}, "
                f"stdout={result.stdout[-1000:]}, stderr={result.stderr[-1000:]}"
            )
            if should_pass:
                assert "NETLIFY EXACT RUNTIME READY" in result.stdout, name
            else:
                assert "NO-GO" in result.stderr, (
                    f"{name} failed without exact-runtime NO-GO report: {result.stderr[-400:]}"
                )
    print("NETLIFY EXACT RUNTIME GATE SELFTEST OK: 1 matched + 5 strict NO-GO fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
