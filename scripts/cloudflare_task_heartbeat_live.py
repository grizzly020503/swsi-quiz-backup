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



def verify_observation(data: object, registry_tasks: list) -> dict:
    """Validate hosted independent schedule evidence; never require all tasks green."""
    if not isinstance(data, dict):
        raise AssertionError('invalid_payload')
    if data.get('producer') != 'cloudflare-cron':
        raise AssertionError('wrong_producer')
    if data.get('independent_of') != 'github-actions':
        raise AssertionError('not_independent')
    if data.get('independent_monitoring_active') is not True:
        raise AssertionError('observer_inactive')
    if data.get('observer_status') != 'fresh':
        raise AssertionError('observer_not_fresh')
    tasks = data.get('tasks')
    if not isinstance(tasks, list) or len(tasks) != len(registry_tasks) or len(tasks) != 6:
        raise AssertionError('task_count_mismatch')
    checked = (data.get('components') or {}).get('task_heartbeat', {}).get('detail', {}).get('tasks_checked')
    if checked != 6:
        raise AssertionError('observed_count_mismatch')
    if any(not isinstance(row, dict) or
           row.get('status') not in ('healthy', 'failed', 'stale', 'missing', 'error')
           for row in tasks):
        raise AssertionError('invalid_task_status')
    # Running observer != healthy source observations; failures/stale remain visible.
    if any(row['status'] == 'error' for row in tasks):
        raise AssertionError('github_source_error')
    return verify_hosted_policy(tasks, registry_tasks)


def classify_failure(error: Exception) -> str:
    """Bounded safe diagnoses; never print public upstream bodies, URLs, or credentials."""
    if isinstance(error, urllib.error.HTTPError):
        return 'http_' + str(error.code) if 400 <= error.code <= 599 else 'http_unexpected'
    if isinstance(error, urllib.error.URLError):
        return 'network_unavailable'
    if isinstance(error, TimeoutError):
        return 'network_timeout'
    if isinstance(error, json.JSONDecodeError):
        return 'invalid_json'
    if isinstance(error, AssertionError):
        msg = str(error)
        if msg.startswith('hosted heartbeat schedule policy does not match main registry: '):
            return 'hosted_policy_drift'
        return msg if msg in {
            'invalid_payload', 'wrong_producer', 'not_independent', 'observer_inactive',
            'observer_not_fresh', 'task_count_mismatch', 'observed_count_mismatch',
            'invalid_task_status', 'github_source_error'
        } else 'observation_contract_error'
    return 'invalid_observation_data'


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
    # Realistic synthetic observation: failed/stale jobs are accepted as *visible*
    # health signals, while source errors, stale observations and config drift fail.
    baseline = {
        'producer': 'cloudflare-cron', 'independent_of': 'github-actions',
        'independent_monitoring_active': True, 'observer_status': 'fresh',
        'tasks': [{**row, 'status': 'healthy'} for row in hosted],
        'components': {'task_heartbeat': {'detail': {'tasks_checked': 6}}}
    }
    assert len(verify_observation(baseline, registry)) == 6
    failed = {**baseline, 'tasks': [dict(row) for row in baseline['tasks']]}
    failed['tasks'][0]['status'] = 'failed'
    assert verify_observation(failed, registry)
    changes = [
        ({**baseline, 'observer_status': 'stale'}, 'observer_not_fresh'),
        ({**baseline, 'tasks': [{**baseline['tasks'][0], 'status': 'error'}, *baseline['tasks'][1:]]}, 'github_source_error'),
        ({**baseline, 'tasks': [{**baseline['tasks'][0], 'max_age_hours': 36}, *baseline['tasks'][1:]]}, 'hosted_policy_drift'),
        ({**baseline, 'tasks': baseline['tasks'][:-1]}, 'task_count_mismatch'),
        ({**baseline, 'producer': 'untrusted'}, 'wrong_producer')
    ]
    for payload, expected in changes:
        try:
            verify_observation(payload, registry)
        except AssertionError as exc:
            assert classify_failure(exc) == expected, (expected, classify_failure(exc))
        else:
            raise AssertionError('unsafe hosted observation accepted: ' + expected)
    assert classify_failure(urllib.error.HTTPError(URL, 503, '', {}, None)) == 'http_503'
    assert classify_failure(urllib.error.URLError('synthetic')) == 'network_unavailable'
    assert classify_failure(TimeoutError()) == 'network_timeout'
    print('CLOUDFLARE LIVE POLICY SELFTEST OK: six tasks, 192h, drift/missing/source-error/stale rejected')


def observe() -> None:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))['tasks']
    # Keep the post-merge deployment and next 15-minute Cloudflare Cron window.
    deadline = time.monotonic() + 32 * 60
    attempts = 0
    last_reason = 'not_started'
    while True:
        attempts += 1
        try:
            req = urllib.request.Request(
                URL, headers={'User-Agent': 'swsi-independent-heartbeat-acceptance'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)
            policy = verify_observation(data, registry)
            print('CLOUDFLARE CRON ACTUALLY OBSERVED ' + json.dumps({
                'scheduled_at': data['scheduled_at'],
                'observed_at': data['generated_at'],
                'tasks': [{'id': r['id'], 'status': r['status']} for r in data['tasks']],
                'verified_policy_max_age_hours': policy,
            }, ensure_ascii=False), flush=True)
            return
        except (urllib.error.URLError, ValueError, KeyError, AssertionError,
                TypeError, TimeoutError) as error:
            reason = classify_failure(error)
            # Emit first/new reason, then a bounded heartbeat every ten attempts.
            # Do not flood public Actions logs or leak raw response bodies.
            if attempts == 1 or reason != last_reason or attempts % 10 == 0:
                print('CLOUDFLARE HEARTBEAT WAIT reason=' + reason +
                      ' attempts=' + str(attempts), flush=True)
            last_reason = reason
            if time.monotonic() >= deadline:
                raise SystemExit(
                    'CLOUDFLARE HEARTBEAT ACCEPTANCE FAILED after 32 minutes'
                    ' last_reason=' + reason + ' attempts=' + str(attempts)
                ) from None
            time.sleep(30)


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    elif len(sys.argv) == 1:
        observe()
    else:
        raise SystemExit('usage: cloudflare_task_heartbeat_live.py [--selftest]')
