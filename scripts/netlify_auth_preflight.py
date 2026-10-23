#!/usr/bin/env python3
"""Read-only, fail-closed credential/site check before a Netlify deployment.

Never log authorization credentials or the API response body. This prevents
building/uploading a release when the token cannot access the intended site.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

EXPECTED_DOMAIN = "swsi-quiznetlify.netlify.app"
API_ROOT = "https://api.netlify.com/api/v1/sites/"


def assert_expected_site(data: object, site_id: str, domain: str = EXPECTED_DOMAIN) -> None:
    if not isinstance(data, dict):
        raise ValueError("Netlify site response must be an object")
    if str(data.get("id") or "") != site_id:
        raise ValueError("Netlify project ID differs from configured NETLIFY_SITE_ID")

    # Verify identity in addition to token access. A valid token for a different
    # project must never be able to deploy the SWSI release to that project.
    def host(value: object) -> str:
        try:
            url = urllib.parse.urlparse(str(value or ""))
            return (url.hostname or "").lower() if url.scheme in ("http", "https") else ""
        except ValueError:
            return ""

    hosts = {host(data.get("url")), host(data.get("ssl_url"))}
    name = str(data.get("name") or "").strip().lower()
    if domain.lower() not in hosts and name != domain.removesuffix(".netlify.app").lower():
        raise ValueError("Netlify project does not match SWSI fallback domain")


def check(token: str, site_id: str, *, opener=urllib.request.urlopen) -> None:
    if not token.strip():
        raise ValueError("NETLIFY_AUTH_TOKEN is missing")
    if not site_id.strip():
        raise ValueError("NETLIFY_SITE_ID is missing")

    # Do not put credentials in query parameters or CLI arguments.
    endpoint = API_ROOT + urllib.parse.quote(site_id.strip(), safe="")
    request = urllib.request.Request(endpoint, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "swsi-netlify-preflight/1.0",
    })
    try:
        with opener(request, timeout=15) as response:
            # Bound the read, and avoid including provider errors in our logs.
            payload = json.loads(response.read(131073))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(
                f"Netlify API HTTP {exc.code}: token invalid or lacks access to target project"
            ) from None
        if exc.code == 404:
            raise RuntimeError(
                "Netlify API HTTP 404: configured project not found or inaccessible to token"
            ) from None
        raise RuntimeError(f"Netlify API HTTP {exc.code}: cannot verify target project") from None
    except urllib.error.URLError:
        raise RuntimeError("Netlify API unreachable: no deployment attempted") from None
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("Netlify API returned invalid site metadata") from None

    assert_expected_site(payload, site_id)


def main() -> int:
    # Read environment only; secrets never enter log output, artifact or git.
    try:
        check(os.environ.get("NETLIFY_AUTH_TOKEN", ""), os.environ.get("NETLIFY_SITE_ID", ""))
    except (ValueError, RuntimeError) as exc:
        print(f"NETLIFY READ-ONLY PREFLIGHT FAILED: {exc}", file=sys.stderr)
        return 1
    print("NETLIFY READ-ONLY PREFLIGHT OK: token can access expected SWSI project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
