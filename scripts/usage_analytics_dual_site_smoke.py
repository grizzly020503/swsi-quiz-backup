#!/usr/bin/env python3
"""SWSI two-site analytics contract: no old rows erased, no new personal data."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
migration = (ROOT / "supabase/migrations/20261107090000_split_usage_analytics_by_site.sql").read_text("utf-8").lower()
edge = (ROOT / "supabase/functions/swsi-usage/index.ts").read_text("utf-8")
owner = (ROOT / "monthly_patch_parts/99_p0_mobile_ai_guardrails.part").read_text("utf-8")
cdn = (ROOT / "cdn/monthly_patch.js").read_text("utf-8")
doc = (ROOT / "ANALYTICS_V1_PRIVACY.md").read_text("utf-8")

primary = "https://wandering-wave-4418.c022050333.workers.dev"
backup = "https://swsi-quiznetlify.netlify.app"

for url in (primary, backup):
    assert url in migration and url in edge and url in owner, url
assert "add column if not exists site_origin text not null" in migration
assert "default '" + primary + "'" in migration, "Existing rows must remain attributed to Cloudflare"
assert "delete from public.swsi_usage_daily" not in migration
assert "truncate public.swsi_usage_daily" not in migration
assert "drop table" not in migration
assert "primary key (usage_date, site_origin, client_hash)" in migration
assert "on conflict (usage_date, site_origin, client_hash)" in migration
assert "create or replace function public.record_swsi_usage(p_client_hash text)" in migration, "Old RPC must remain callable"
assert "p_client_hash text, p_site_origin text" in migration, "New per-site RPC"
assert "revoke all on function public.record_swsi_usage(text,text)" in migration
assert "grant execute on function public.record_swsi_usage(text,text) to service_role" in migration
assert "revoke all on table public.swsi_usage_daily from anon, authenticated" in migration
assert "count(distinct (site_origin,client_hash))" in migration, "Combined count cannot accidentally collapse site pairs"
assert "'sites'" in migration and "'primary'" in migration and "'backup'" in migration
for term in ["ip_address text", "email text", "user_agent text", "fingerprint text", "name text"]:
    assert term not in migration, term

assert "const ALLOWED_ORIGINS = new Set([PRODUCTION_ORIGIN, BACKUP_ORIGIN])" in edge
assert "if (!ALLOWED_ORIGINS.has(origin))" in edge
assert "ALLOWED_ORIGINS.has(origin) ? origin : \"\"" in edge
assert "p_site_origin: origin" in edge
assert "body.event !== \"page_view\"" in edge
assert "p_site_origin: body" not in edge
assert "const clientHash = await sha256Hex(clientId)" in edge
assert "credentials:'omit'" in owner
assert "if(location.origin!==PRODUCTION_ORIGIN&&location.origin!==BACKUP_ORIGIN)return;" in owner
assert owner in cdn, "Cloudflare must ship canonical frontend tracker"
assert "Cloudflare previews" in doc and "not deduplicated humans" in doc
for file in ("admin/index.html", "cdn/admin/index.html"):
    source=(ROOT/file).read_text("utf-8")
    for fragment in ("analyticsPrimaryTodayUsers", "analyticsBackupTodayUsers", "analyticsPrimaryTotalUsers",
                     "analyticsBackupTotalUsers", "analyticsPrimaryTotalViews", "analyticsBackupTotalViews",
                     "sites.primary", "sites.backup", "兩站合計"):
        assert fragment in source, (file, fragment)
    assert "不保存姓名、Email、原始 IP、User-Agent 或裝置指紋" in source

print("USAGE DUAL-SITE CONTRACT OK: allowlist, legacy rows, per-site counts, combined and privacy")
