#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def table_columns(sql: str, table: str) -> list[str]:
    m = re.search(
        rf"create table if not exists public\.{re.escape(table)}\s*\((.*?)\n\);",
        sql,
        flags=re.I | re.S,
    )
    if not m:
        raise AssertionError(f"missing table {table}")
    cols = []
    column_re = re.compile(r'^([a-z_][a-z0-9_]*)\\s+(date|text|integer|bigint|timestamptz)\\b', re.I)
    for raw in m.group(1).splitlines():
        line = raw.strip().rstrip(",")
        match = column_re.match(line)
        if match:
            cols.append(match.group(1))
    return cols


def main() -> int:
    migration = read("supabase/migrations/20260915151500_add_ai_telemetry.sql")
    ingest = read("supabase/functions/swsi-ai-telemetry/index.ts")
    admin_edge = read("supabase/functions/swsi-admin/index.ts")
    admin = read("admin/index.html")
    p99 = read("monthly_patch_parts/99_p0_mobile_ai_guardrails.part")
    p99z = read("monthly_patch_parts/99z.essay-trust-layer.part")

    assert table_columns(migration, "swsi_ai_telemetry_client_daily") == [
        "usage_date", "client_hash", "event_count", "last_seen_at"
    ]
    assert table_columns(migration, "swsi_ai_telemetry_5m") == [
        "bucket_start", "mode", "outcome", "request_count", "latency_total_ms", "latency_max_ms"
    ]
    for marker in (
        "alter table public.swsi_ai_telemetry_client_daily enable row level security",
        "alter table public.swsi_ai_telemetry_5m enable row level security",
        "revoke all on table public.swsi_ai_telemetry_client_daily from anon, authenticated",
        "revoke all on table public.swsi_ai_telemetry_5m from anon, authenticated",
        "revoke all on function public.record_swsi_ai_telemetry(text,text,text,integer) from public, anon, authenticated",
        "revoke all on function public.swsi_ai_telemetry_summary() from public, anon, authenticated",
        "set search_path = public, pg_temp",
        "outcome in ('success','rate_limited','service_error','timeout','network_error','client_error')",
    ):
        assert marker in migration, marker

    assert 'const allowedKeys = new Set(["event", "mode", "outcome", "latency_ms"])' in ingest
    assert 'body.event !== "ai_request"' in ingest
    assert 'db.rpc("record_swsi_ai_telemetry"' in ingest
    assert "PRODUCTION_ORIGIN" in ingest
    assert "X-SWSI-Client-ID" in ingest
    for forbidden in ("body.prompt", "body.answer", "body.image", "CF-Connecting-IP", "User-Agent"):
        assert forbidden not in ingest, forbidden

    assert "swsi-ai-telemetry" in p99
    assert "window.swsiRecordAITelemetry" in p99
    assert "event:'ai_request',mode:mode,outcome:outcome,latency_ms:ms" in p99
    assert "location.origin!==AI_TELEMETRY_ORIGIN" in p99

    for marker in (
        "async function postAI(payload,timeoutMs,mode)",
        "record('success')",
        "record('rate_limited')",
        "record('service_error')",
        "record('client_error')",
        "record(err&&err.name==='AbortError'?'timeout':'network_error')",
        "45000,'text'",
        "60000,'photo'",
    ):
        assert marker in p99z, marker

    assert 'admin.rpc("swsi_ai_telemetry_summary")' in admin_edge
    assert 'ai_telemetry: aiTelemetryRes.error ? "unavailable" : "enabled"' in admin_edge
    assert "ai_telemetry: aiTelemetryRes.error" in admin_edge

    for marker in (
        'id="aiDot"',
        'id="aiHealth"',
        "function renderAITelemetry()",
        "最近 60 分鐘",
        "監測已啟用",
    ):
        assert marker in admin, marker

    parts = sorted((ROOT / "monthly_patch_parts").glob("*.part"), key=lambda p: p.name)
    generated = "".join(p.read_text(encoding="utf-8") for p in parts)
    runtime = read("cdn/monthly_patch.js")
    assert generated == runtime, "generated monthly_patch.js drifted from canonical parts"

    print("AI TELEMETRY V1 CONTRACT OK: privacy-safe aggregate pipeline + dynamic admin health")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
