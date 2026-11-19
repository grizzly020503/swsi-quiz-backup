#!/usr/bin/env python3
"""Observe a real Cloudflare Cron and verify its hosted task policy, without writes."""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = 'https://wandering-wave-4418.c022050333.workers.dev/ops/task-heartbeat'
REGISTRY = Path(__file__).resolve().parents[1] / 'data/ops_task_registry.v1.json'


def verify_hosted_policy(tasks: object, registry_tasks: object) -> dict:
    """Reject stale Worker thresholds, omissions, duplicates and unexpected tasks."""
    if not isinstance(tasks, list) or not isinstance(registry_tasks, list):
        raise AssertionError('Cloudflare heartbeat task lists must be arrays')
    expected = {}
    for task in registry_tasks:
        ident = task['id']
        if ident in expected or task.get('accepted_events') != ['schedule']:
            raise AssertionError('invalid local registry task policy: ' + str(ident))
        expected[ident] = (task['workflow_file'], task['max_age_hours'])
    observed = {}
    for task in tasks:
        ident = task['id']
        if ident in observed:
            raise AssertionError('duplicate hosted heartbeat task: ' + str(ident))
        observed[ident] = (task['workflow_file'], task['max_age_hours'])
    if observed != expected:
        mismatch = sorted(ident for ident in set(expected) | set(observed)
                          if observed.get(ident) != expected.get(ident))
        raise AssertionError('hosted heartbeat schedule policy does not match main registry: '
                             + ','.join(mismatch))
    return dict(sorted((ident, max_age) for ident, (_, max_age) in expected.items()))


def selftest() -> None:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))['tasks']
    hosted = [{'id': r['id'], 'workflow_file': r['workflow_file'],
               'max_age_hours': r['max_age_hours']} for r in registry]
    assert verify_hosted_policy(hosted, registry)['official-pdf-batch-pipeline'] == 192
    assert verify_hosted_policy(list(reversed(hosted)), registry)
    mutants = []
    stale = [dict(r) for r in hosted]
    next(r for r in stale if r['id'] == 'official-pdf-batch-pipeline')['max_age_hours'] = 36
    mutants.append(stale)
    mutants.append(hosted[:-1])
    mutants.append(hosted + [dict(hosted[0])])
    wrong_file = [dict(r) for r in hosted]
    wrong_file[0]['workflow_file'] = 'unexpected.yml'
    mutants.append(wrong_file)
    for bad in mutants:
        try:
            verify_hosted_policy(bad, registry)
        except AssertionError:
            pass
        else:
            raise AssertionError('unsafe hosted task policy accepted by selftest')
    print('CLOUDFLARE LIVE POLICY SELFTEST OK: exact six tasks, 192h, drift/missing/duplicate rejected')


def observe() -> None:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))['tasks']
    # Retain the documented Cloudflare deployment and next 15-minute Cron window.
    deadline = time.monotonic() + 32 * 60
    while True:
        try:
            req = urllib.request.Request(
                URL, headers={'User-Agent': 'swsi-independent-heartbeat-acceptance'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)
            assert data['producer'] == 'cloudflare-cron'
            assert data['independent_of'] == 'github-actions'
            assert data['independent_monitoring_active'] is True
            assert data['observer_status'] == 'fresh'
            assert len(data['tasks']) == len(registry) == 6
            assert data['components']['task_heartbeat']['detail']['tasks_checked'] == 6
            assert all(row['status'] in ('healthy','failed','stale','missing','error')
                       for row in data['tasks'])
            # A running observer is not proof that every monitored task is healthy.
            # API failures must not count as healthy source observations.
            assert all(row['status'] != 'error' for row in data['tasks'])
            policy = verify_hosted_policy(data['tasks'], registry)
            print('CLOUDFLARE CRON ACTUALLY OBSERVED ' + json.dumps({
                'scheduled_at': data['scheduled_at'],
                'observed_at': data['generated_at'],
                'tasks': [{'id': r['id'], 'status': r['status']} for r in data['tasks']],
                'verified_policy_max_age_hours': policy,
            }, ensure_ascii=False), flush=True)
            return
        except (urllib.error.URLError, ValueError, KeyError, AssertionError,
                TypeError, TimeoutError) as error:
            if time.monotonic() >= deadline:
                raise SystemExit(
                    'Cloudflare heartbeat unavailable or hosted policy not aligned '
                    'with reviewed registry within 32 minutes') from error
            print('Awaiting Cloudflare schedule / exact hosted policy evidence', flush=True)
            time.sleep(30)


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    elif len(sys.argv) == 1:
        observe()
    else:
        raise SystemExit('usage: cloudflare_task_heartbeat_live.py [--selftest]')
