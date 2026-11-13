#!/usr/bin/env python3
"""Observe a real Cloudflare Cron result; GET never starts a probe or modifies data."""
import json
import time
import urllib.error
import urllib.request

URL = 'https://wandering-wave-4418.c022050333.workers.dev/ops/task-heartbeat'
# Allow deployment + documented Cron propagation + the next 15-minute tick.
deadline = time.monotonic() + 32 * 60
while True:
    try:
        req = urllib.request.Request(URL, headers={'User-Agent': 'swsi-independent-heartbeat-acceptance'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.load(response)
        assert data['producer'] == 'cloudflare-cron'
        assert data['independent_of'] == 'github-actions'
        assert data['independent_monitoring_active'] is True
        assert data['observer_status'] == 'fresh'
        assert len(data['tasks']) == 6
        assert data['components']['task_heartbeat']['detail']['tasks_checked'] == 6
        assert all(row['status'] in ('healthy','failed','stale','missing','error') for row in data['tasks'])
        # A running observer is not proof that every monitored task is healthy.
        # API access failures are not accepted as completed source observations.
        assert all(row['status'] != 'error' for row in data['tasks'])
        print('CLOUDFLARE CRON ACTUALLY OBSERVED ' + json.dumps({
            'scheduled_at': data['scheduled_at'], 'observed_at': data['generated_at'],
            'tasks': [{'id':r['id'],'status':r['status']} for r in data['tasks']],
        }, ensure_ascii=False), flush=True)
        break
    except (urllib.error.URLError, ValueError, KeyError, AssertionError, TimeoutError) as error:
        if time.monotonic() >= deadline:
            raise SystemExit('No fresh, independently scheduled observation with valid GitHub source evidence within 32 minutes') from error
        print('Awaiting actual Cloudflare schedule / readable public evidence', flush=True)
        time.sleep(30)
