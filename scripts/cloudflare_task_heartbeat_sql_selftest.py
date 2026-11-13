#!/usr/bin/env python3
"""Exercise exact heartbeat SQL in SQLite, without production access."""
import re
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'cloudflare/wandering-wave-4418/worker.js').read_text()
db = sqlite3.connect(':memory:')
db.executescript((root/'cloudflare/wandering-wave-4418/d1/recovery_schema.sql').read_text())
create = re.search(r'const HEARTBEAT_SCHEMA = `([^`]+)`', source).group(1)
save = re.search(r'const HEARTBEAT_SAVE = `([^`]+)`', source).group(1)
db.execute(create)
for stamp in ('2026-11-13T14:15:00.000Z', '2026-11-13T14:00:00.000Z', '2026-11-13T14:15:00.000Z'):
    db.execute(save, (stamp, stamp, '{}'))
assert db.execute('SELECT count(*),scheduled_at FROM ops_task_heartbeat').fetchone() == (1, '2026-11-13T14:15:00.000Z')
assert db.execute('SELECT count(*) FROM ai_daily_client_usage').fetchone()[0] == 0
assert db.execute('SELECT count(*) FROM ai_daily_global_usage').fetchone()[0] == 0
print('HEARTBEAT SQLITE PASS: exact SQL, recovery bootstrap, monotonic one-row retention, quota tables untouched')
