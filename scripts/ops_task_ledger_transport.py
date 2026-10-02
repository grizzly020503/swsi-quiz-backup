#!/usr/bin/env python3
"""Server-side-only Supabase REST transport for the #274 durable ops ledger.

The service-role key is read only from process environment. This module exposes
no live-write CLI. Network writes are retried only for RPCs whose semantics are
explicitly replay-safe; ambiguous side effects fail closed for higher-level
ledger reconciliation instead of being blindly repeated.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
REPLAY_SAFE_RPCS = {
    "swsi_ops_checkpoint_task",
    "swsi_ops_heartbeat_task",
    "swsi_ops_upsert_review_item",
    "swsi_ops_resolve_review_item",
}


class OpsTransportError(RuntimeError):
    def __init__(self, category: str, message: str, *, status: int | None = None,
                 retryable: bool = False, ambiguous_write: bool = False) -> None:
        super().__init__(message)
        self.category = category
        self.status = status
        self.retryable = retryable
        self.ambiguous_write = ambiguous_write

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status,
            "retryable": self.retryable,
            "ambiguous_write": self.ambiguous_write,
            "message": str(self),
        }


@dataclass
class SupabaseRestTransport:
    base_url: str
    service_role_key: str = field(repr=False)
    timeout_seconds: float = 15.0
    max_attempts: int = 3
    backoff_seconds: float = 0.5
    request_fn: Callable[..., Any] = field(default=urllib.request.urlopen, repr=False)
    sleep_fn: Callable[[float], None] = field(default=time.sleep, repr=False)

    def __post_init__(self) -> None:
        self.base_url = str(self.base_url or "").strip().rstrip("/")
        self.service_role_key = str(self.service_role_key or "").strip()
        if not self.base_url.startswith("https://"):
            raise ValueError("Supabase base_url must use https://")
        if not self.service_role_key:
            raise ValueError("service-role key is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError("max_attempts must be 1..5")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")

    @classmethod
    def from_env(cls, *, url_env: str = "SUPABASE_URL",
                 key_env: str = "SUPABASE_SERVICE_ROLE_KEY", **kwargs: Any) -> "SupabaseRestTransport":
        url = str(os.getenv(url_env, "") or "").strip()
        key = str(os.getenv(key_env, "") or "").strip()
        if not url or not key:
            missing = [name for name, value in ((url_env, url), (key_env, key)) if not value]
            raise OpsTransportError("config", f"missing server environment: {','.join(missing)}")
        return cls(url, key, **kwargs)

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "User-Agent": "swsi-ops-ledger/1",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    @staticmethod
    def _safe_body(raw: bytes) -> str:
        text = raw.decode("utf-8", "replace").strip()
        if not text:
            return "empty response"
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text[:300]
        if isinstance(payload, dict):
            for key in ("message", "error", "details", "hint", "code"):
                value = payload.get(key)
                if value:
                    return str(value)[:300]
        return text[:300]

    def _request(self, *, method: str, url: str, body: bytes | None,
                 replay_safe: bool) -> Any:
        attempts = self.max_attempts if replay_safe else 1
        last: OpsTransportError | None = None
        for attempt in range(1, attempts + 1):
            req = urllib.request.Request(
                url,
                data=body,
                method=method,
                headers=self._headers(prefer="return=representation" if method != "GET" else None),
            )
            try:
                with self.request_fn(req, timeout=self.timeout_seconds) as response:
                    raw = response.read()
                    if not raw:
                        return None
                    try:
                        return json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise OpsTransportError(
                            "invalid_response",
                            "Supabase returned non-JSON response",
                            retryable=False,
                            ambiguous_write=method != "GET",
                        ) from exc
            except urllib.error.HTTPError as exc:
                detail = self._safe_body(exc.read())
                retryable = exc.code in RETRYABLE_HTTP
                ambiguous = method != "GET"
                err = OpsTransportError(
                    "http_retryable" if retryable else "http_terminal",
                    f"Supabase HTTP {exc.code}: {detail}",
                    status=exc.code,
                    retryable=retryable,
                    ambiguous_write=ambiguous,
                )
                last = err
                if not (replay_safe and retryable and attempt < attempts):
                    raise err from exc
            except (TimeoutError, urllib.error.URLError) as exc:
                err = OpsTransportError(
                    "network",
                    "Supabase request failed before a trusted response was received",
                    retryable=True,
                    ambiguous_write=method != "GET",
                )
                last = err
                if not (replay_safe and attempt < attempts):
                    raise err from exc
            if self.backoff_seconds:
                self.sleep_fn(self.backoff_seconds * attempt)
        assert last is not None
        raise last

    def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        rpc_name = str(name or "").strip()
        if not rpc_name or "/" in rpc_name:
            raise ValueError("invalid RPC name")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        url = f"{self.base_url}/rest/v1/rpc/{urllib.parse.quote(rpc_name, safe='')}"
        return self._request(
            method="POST",
            url=url,
            body=raw,
            replay_safe=rpc_name in REPLAY_SAFE_RPCS,
        )

    def select(self, table: str, query: dict[str, str]) -> Any:
        table_name = str(table or "").strip()
        if not table_name or "/" in table_name:
            raise ValueError("invalid table name")
        encoded = urllib.parse.urlencode(query)
        url = f"{self.base_url}/rest/v1/{urllib.parse.quote(table_name, safe='')}"
        if encoded:
            url += "?" + encoded
        return self._request(method="GET", url=url, body=None, replay_safe=True)


class FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def read(self) -> bytes:
        return self.raw


def http_error(code: int, body: dict[str, Any]) -> urllib.error.HTTPError:
    raw = json.dumps(body).encode("utf-8")
    return urllib.error.HTTPError(
        "https://example.supabase.co/rest/v1/test",
        code,
        "fixture",
        hdrs=None,
        fp=io.BytesIO(raw),
    )


def self_test() -> dict[str, Any]:
    calls: list[str] = []
    queue: list[Any] = [
        http_error(503, {"message": "temporary"}),
        FakeResponse([{"ok": True}]),
        http_error(503, {"message": "temporary"}),
        FakeResponse({"ok": True}),
        http_error(503, {"message": "temporary"}),
    ]

    def fake_request(req: urllib.request.Request, timeout: float) -> Any:
        assert timeout == 2
        calls.append(req.full_url)
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    transport = SupabaseRestTransport(
        "https://example.supabase.co",
        "fixture-secret-that-must-not-appear",
        timeout_seconds=2,
        max_attempts=2,
        backoff_seconds=0,
        request_fn=fake_request,
        sleep_fn=lambda _: None,
    )
    selected = transport.select("swsi_ops_task_runs", {"limit": "1"})
    assert selected == [{"ok": True}]
    checkpoint = transport.rpc("swsi_ops_checkpoint_task", {"p_processed_count": 1})
    assert checkpoint == {"ok": True}
    try:
        transport.rpc("swsi_ops_complete_task", {"p_outcome": "success"})
    except OpsTransportError as exc:
        assert exc.retryable is True
        assert exc.ambiguous_write is True
        assert "fixture-secret" not in str(exc)
    else:
        raise AssertionError("ambiguous complete RPC must not be blindly retried")
    assert len(calls) == 5
    assert not queue
    assert "swsi_ops_complete_task" not in REPLAY_SAFE_RPCS
    assert "swsi_ops_touch_review_item" not in REPLAY_SAFE_RPCS
    return {
        "ok": True,
        "bounded_retry": True,
        "ambiguous_write_fail_closed": True,
        "secret_redaction": True,
        "requests": len(calls),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SWSI ops ledger server-side transport")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        raise SystemExit("Only --self-test is exposed; no live network/write CLI is available.")
    print(json.dumps(self_test(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
