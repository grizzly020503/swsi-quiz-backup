from pathlib import Path
import re

sql = Path('supabase/migrations/20260902143000_add_anonymous_usage_analytics.sql').read_text(encoding='utf-8').lower()

# Keep the storage model intentionally tiny. This guards against later adding silent
# tracking columns without an explicit privacy review.
match = re.search(r'create table if not exists public\.swsi_usage_daily\s*\((.*?)\n\);', sql, re.S)
assert match, 'usage table definition not found'
table = match.group(1)
required = ['usage_date date', 'client_hash text', 'page_views integer', 'first_seen_at timestamptz', 'last_seen_at timestamptz']
for column in required:
    assert column in table, column

for forbidden in ['ip_', 'email', 'user_agent', 'fingerprint', 'latitude', 'longitude', 'referrer', 'screen_', 'account_id', 'user_id']:
    assert forbidden not in table, forbidden

assert "client_hash ~ '^[0-9a-f]{64}$'" in table
assert 'page_views between 0 and 500' in table
print('USAGE ANALYTICS SCHEMA MINIMIZATION OK')
