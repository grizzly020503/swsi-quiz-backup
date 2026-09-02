from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

migration = (ROOT / 'supabase/migrations/20260902143000_add_anonymous_usage_analytics.sql').read_text(encoding='utf-8')
usage_fn = (ROOT / 'supabase/functions/swsi-usage/index.ts').read_text(encoding='utf-8')
admin_fn = (ROOT / 'supabase/functions/swsi-admin/index.ts').read_text(encoding='utf-8')
owner = (ROOT / 'monthly_patch_parts/99_p0_mobile_ai_guardrails.part').read_text(encoding='utf-8')
cdn_patch = (ROOT / 'cdn/monthly_patch.js').read_text(encoding='utf-8')

for path in [ROOT / 'admin/index.html', ROOT / 'cdn/admin/index.html']:
    text = path.read_text(encoding='utf-8')
    for marker in ['analyticsTodayUsers', 'analyticsTodayViews', 'analytics7dUsers', 'analyticsTotalUsers', 'analyticsTotalViews', 'function renderAnalytics(){']:
        assert marker in text, (path, marker)
    assert '匿名使用統計尚未啟用' not in text, path
    assert '不保存姓名、Email、原始 IP、User-Agent 或裝置指紋' in text, path

assert 'create table if not exists public.swsi_usage_daily' in migration
assert 'enable row level security' in migration.lower()
assert 'revoke all on table public.swsi_usage_daily from anon, authenticated' in migration
assert 'grant execute on function public.swsi_usage_summary() to service_role' in migration
assert 'grant execute on function public.record_swsi_usage(text) to service_role' in migration
for forbidden in ['ip_address', 'user_agent text', 'email text', 'name text', 'fingerprint']:
    assert forbidden not in migration.lower(), forbidden

assert 'PRODUCTION_ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev"' in usage_fn
assert 'body.event !== "page_view"' in usage_fn
assert 'sha256Hex(clientId)' in usage_fn
assert 'User-Agent' not in usage_fn
assert 'record_swsi_usage' in usage_fn
assert 'swsi_usage_summary' in admin_fn
assert 'analyticsRes.error ? "unavailable" : "enabled"' in admin_fn

for text in [owner, cdn_patch]:
    assert 'SWSI Anonymous Usage Analytics V1 2026-09-02' in text
    assert "if(location.origin!==PRODUCTION_ORIGIN)return;" in text
    assert "'X-SWSI-Client-ID':client" in text
    assert "body:'{\"event\":\"page_view\"}'" in text
    assert 'window.swsiGetClientId()' in text

root_index = (ROOT / 'index.html').read_text(encoding='utf-8')
for tracker in ['googletagmanager', 'google-analytics', 'plausible.io', 'umami']:
    assert tracker not in root_index.lower(), tracker

print('USAGE ANALYTICS V1 SMOKE OK')
