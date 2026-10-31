#!/usr/bin/env python3
"""Zero-network regression for independent Cloudflare vs Netlify uptime signals."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import urllib.error
from unittest.mock import patch

import public_uptime_smoke as uptime


def fake_status(log):
    def check(label, url, expected=200, *, method="GET", headers=None):
        log.append(label)
        mapping = {
            "Cloudflare home": b"<html>SWSI primary</html>",
            "PWA manifest": json.dumps({"display": "standalone", "start_url": "/"}).encode(),
            "Service Worker": b"const VERSION = 'v7';",
            "Question manifest": json.dumps({
                "total_questions": 4800, "shard_count": 24, "shards": [{}] * 24,
            }).encode(),
            "AI preflight": b"",
            "Feedback preflight": b"",
            "Netlify fallback": b'<html><meta name="swsi-netlify-release" content="frozen-release">SWSI backup</html>',
        }
        assert label in mapping, f"unexpected live network check: {label}"
        if label.endswith("preflight"):
            assert method == "OPTIONS", (label, method)
            return mapping[label], {"Access-Control-Allow-Origin": uptime.PRIMARY}
        assert method == "GET", (label, method)
        return mapping[label], {}
    return check


def run_mode(flags, checker, *, mock_runtime=False):
    output = io.StringIO()
    with patch.object(sys, "argv", ["public_uptime_smoke.py", *flags]), \
         patch.object(uptime, "require_status", side_effect=checker), \
         patch.object(uptime, "expected_netlify_release_marker", return_value="frozen-release"), \
         patch.object(uptime, "expected_netlify_runtime", return_value=(b"canonical-patch", "abcd" * 16, b"canonical-sw")), \
         contextlib.redirect_stdout(output):
        return uptime.main(), output.getvalue()


def main() -> int:
    primary = []
    ok, message = run_mode(["--primary-only"], fake_status(primary))
    assert ok == 0 and "[primary]" in message, message
    assert "Cloudflare home" in primary and "AI preflight" in primary
    assert not any("Netlify" in name for name in primary), primary

    backup = []
    ok, message = run_mode(["--backup-only"], fake_status(backup))
    assert ok == 0 and "[backup-availability]" in message, message
    assert backup == ["Netlify fallback"], backup

    legacy = []
    ok, _ = run_mode([], fake_status(legacy))
    assert ok == 0 and "Cloudflare home" in legacy and "Netlify fallback" in legacy

    drift_calls = []
    try:
        run_mode(["--backup-only", "--fallback-parity"], fake_status(drift_calls))
    except AssertionError as exc:
        assert "monthly_patch cache-bust" in str(exc), str(exc)
    else:
        raise AssertionError("frozen-backup drift was falsely accepted")
    assert drift_calls == ["Netlify fallback"], drift_calls

    def missing_backup(label, url, expected=200, *, method="GET", headers=None):
        assert label == "Netlify fallback", label
        raise urllib.error.URLError("synthetic backup unavailable")

    try:
        run_mode(["--backup-only"], missing_backup)
    except urllib.error.URLError:
        pass
    else:
        raise AssertionError("missing backup must fail its independent uptime gate")

    # Neither incompatible mode combination may silently skip a requested test.
    for flags in (
        ["--primary-only", "--fallback-parity"],
        ["--backup-only", "--monitoring-v2"],
        ["--backup-only", "--primary-only"],
    ):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                run_mode(flags, fake_status([]))
            except SystemExit as exc:
                assert exc.code == 2, (flags, exc.code)
            else:
                raise AssertionError(f"conflicting switches silently accepted: {flags}")

    print(
        "SWSI UPTIME MODE SELFTEST OK: primary remains independent of frozen "
        "backup reachability and drift; backup loss is still detected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
