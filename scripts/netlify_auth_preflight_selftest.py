#!/usr/bin/env python3
"""Offline regressions for Netlify credential/site preflight: no network or secrets."""
from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import patch

import netlify_auth_preflight as preflight


def fake_response(site_id: str, *, name="swsi-quiznetlify", url="https://swsi-quiznetlify.netlify.app"):
    return io.BytesIO(json.dumps({"id": site_id, "name": name, "ssl_url": url}).encode())


def main() -> int:
    configured = "fixture-opaque-project-id"
    seen = []

    def approved(req, timeout=15):
        seen.append((req.full_url, req.get_header("Authorization"), timeout))
        return fake_response(configured)

    preflight.check("fixture-token", configured, opener=approved)
    assert seen and seen[0][1] == "Bearer fixture-token"
    assert seen[0][0].endswith("/fixture-opaque-project-id")
    assert seen[0][2] == 15

    for label, response in [
        ("other project id", {"id": "wrong", "name": "swsi-quiznetlify"}),
        ("unrelated domain", {"id": configured, "name": "not-swsi", "ssl_url": "https://other.netlify.app"}),
        ("empty response", {}),
    ]:
        try:
            preflight.assert_expected_site(response, configured)
        except ValueError:
            pass
        else:
            raise AssertionError(label + " must fail closed")

    for status in (401, 403, 404, 500):
        def fail(req, timeout=15, status=status):
            raise urllib.error.HTTPError(req.full_url, status, "private vendor details", {}, None)
        try:
            preflight.check("fixture-token", configured, opener=fail)
        except RuntimeError as exc:
            msg = str(exc)
            assert str(status) in msg and "private vendor details" not in msg
            assert "fixture-token" not in msg
            assert configured not in msg
        else:
            raise AssertionError(f"HTTP {status} must fail closed")

    for missing_token, missing_site in [("", configured), ("fixture-token", "")]:
        try:
            preflight.check(missing_token, missing_site, opener=approved)
        except ValueError:
            pass
        else:
            raise AssertionError("missing credential must fail closed")

    with patch.object(preflight.urllib.request, "urlopen") as no_network:
        try:
            preflight.check("", configured)
        except ValueError:
            pass
        else:
            raise AssertionError("no token must fail")
        no_network.assert_not_called()

    print("NETLIFY AUTH PREFLIGHT SELFTEST OK: success/missing/wrong-project/401/403/404/500")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
