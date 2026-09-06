from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
usage = (ROOT / 'supabase/functions/swsi-usage/index.ts').read_text(encoding='utf-8')
admin = (ROOT / 'supabase/functions/swsi-admin/index.ts').read_text(encoding='utf-8')

# Collection endpoint must fail closed outside the single official production origin.
assert 'origin !== PRODUCTION_ORIGIN' in usage
assert 'status: 403' in usage
assert 'req.method === "OPTIONS"' in usage
assert 'req.method !== "POST"' in usage
assert 'body.event !== "page_view"' in usage
assert 'new TextEncoder().encode(raw).byteLength > 1024' in usage

# Raw anonymous id must be hashed before the service-role RPC. Avoid regressions that
# accidentally pass the browser id directly to Postgres.
hash_pos = usage.index('const clientHash = await sha256Hex(clientId);')
rpc_pos = usage.index('db.rpc("record_swsi_usage", { p_client_hash: clientHash })')
assert hash_pos < rpc_pos
assert 'p_client_hash: clientId' not in usage

# Admin may return only the aggregate summary; it does not query analytics rows directly.
assert 'admin.rpc("swsi_usage_summary")' in admin
assert 'from("swsi_usage_daily")' not in admin

print('USAGE ANALYTICS EDGE CONTRACT OK')
