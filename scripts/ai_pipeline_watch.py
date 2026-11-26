#!/usr/bin/env python3
"""Read-only watch of the AI explanation pipeline (Supabase queue -> website).

The scheduled job fails, which makes GitHub notify the owner, when:

* stalled: the queue has work (pending or analyzing, fewer than 3 attempts)
  but nothing was claimed for 2 hours. Before reporting, the check waits for
  the next */30 cron tick and looks again, so a queue that was refilled a few
  minutes ago is not reported. While the free-tier cap (25 completions per
  24 hours) is reached a pause is normal; only a pause longer than 26 hours is
  reported then.
* parked: questions failed three times and were moved to `review` since the
  previous run.
* unpublished: an explanation finished 9 days ago is still not `ready` in the
  website shards (cdn/question-shards), i.e. the weekly publish missed it.
* unlabelled: a question whose explanation finished 14 days ago still has
  legal_status `unreviewed`, i.e. the daily automatic legal label
  (public.legal_auto_label_apply) could not decide it and a person must.

Except for a stalled queue, each question is reported once, when it crosses its
threshold (window 6.5 hours, the job runs every 6 hours), so an unresolved case
does not send a notice four times a day; the job summary always shows totals.

2026-11-23..26 the queue stopped for three days without anyone noticing; this
watch exists so that does not happen silently again.

It uses only the public read access the website itself uses (Supabase URL and
publishable key from cdn/index.html) and never writes anything.

  python scripts/ai_pipeline_watch.py --selftest
  python scripts/ai_pipeline_watch.py --out /tmp/ai-pipeline.json --fail-on-problem
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'cdn/index.html'
SHARDS = ROOT / 'cdn/question-shards'

STALL_AFTER = timedelta(hours=2)
CAP_PER_24H = 25
CAP_STALL_AFTER = timedelta(hours=26)
WINDOW = timedelta(hours=6, minutes=30)
PUBLISH_GRACE = timedelta(days=9)
PUBLISH_LOOKBACK = timedelta(days=60)
LABEL_GRACE = timedelta(days=14)
UA = 'swsi-ai-pipeline-watch/1.0 (+read-only)'


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_time(value) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip().replace(' ', 'T')
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    raw = re.sub(r'([+-]\d\d)$', r'\1:00', raw)
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- rules

def judge_queue(facts: dict, now: datetime) -> dict:
    """First look at the queue. Returns ok / suspect / stalled."""
    active = int(facts['active'])
    last = parse_time(facts.get('last_attempt_at'))
    idle = (now - last) if last else None
    out = {'active': active, 'completed_24h': int(facts['completed_24h']),
           'last_attempt_at': iso(last) if last else None,
           'idle_minutes': round(idle.total_seconds() / 60) if idle else None}
    if active == 0:
        return {**out, 'verdict': 'ok', 'reason': 'queue empty'}
    if out['completed_24h'] >= CAP_PER_24H:
        if idle is None or idle > CAP_STALL_AFTER:
            return {**out, 'verdict': 'stalled', 'reason': 'daily cap reached and idle over 26h'}
        return {**out, 'verdict': 'ok', 'reason': 'paused by the 25-per-24h cap'}
    if idle is None or idle > STALL_AFTER:
        return {**out, 'verdict': 'suspect', 'reason': 'work waiting and nothing claimed for 2h'}
    return {**out, 'verdict': 'ok', 'reason': 'recent claim'}


def confirm_queue(first: dict, recheck: Callable[[], dict], now: Callable[[], datetime],
                  wait: Callable[[], None]) -> dict:
    """Re-check a suspect queue after the next cron tick."""
    if first['verdict'] != 'suspect':
        return first
    wait()
    second = judge_queue(recheck(), now())
    if second['verdict'] == 'ok':
        reason = 'claimed after the next cron tick' if second['active'] else second['reason']
        return {**second, 'reason': reason}
    return {**second, 'verdict': 'stalled',
            'reason': 'work waiting and nothing claimed for 2h, still idle after the next cron tick'}


def judge_parked(rows: list[dict]) -> dict:
    ids = sorted(str(r['id']) for r in rows)
    return {'verdict': 'parked' if ids else 'ok', 'ids': ids,
            'errors': sorted({str(r.get('analysis_error') or '')[:80] for r in rows} - {''})}


def judge_unpublished(prod_rows: list[dict], shard_status: dict[str, str], since: datetime) -> dict:
    """prod_rows: finished 9-60 days ago. Only rows that crossed the 9-day mark
    within the last window are new; the rest are totals for the summary."""
    missing = [r for r in prod_rows
               if str(r['id']) in shard_status and shard_status[str(r['id'])] != 'ready']
    new = sorted(str(r['id']) for r in missing
                 if (parse_time(r.get('analysis_completed_at')) or since) + PUBLISH_GRACE >= since)
    return {'verdict': 'unpublished' if new else 'ok', 'ids': new,
            'total': len(missing), 'checked': len(prod_rows)}


def judge_unlabelled(rows: list[dict], total: int) -> dict:
    ids = sorted(str(r['id']) for r in rows)
    return {'verdict': 'unlabelled' if ids else 'ok', 'ids': ids, 'total': total}


def load_shard_status(root: Path = SHARDS) -> dict[str, str]:
    status = {}
    for path in sorted(root.glob('*.json')):
        if path.name == 'manifest.json':
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        rows = data if isinstance(data, list) else (data.get('questions') or data.get('rows') or [])
        for row in rows:
            if isinstance(row, dict) and row.get('id'):
                status[str(row['id'])] = str(row.get('analysis_status') or '')
    return status


# ---------------------------------------------------------------- live reads

def supabase_config() -> tuple[str, str]:
    text = INDEX.read_text(encoding='utf-8')
    url = re.search(r'\burl\s*:\s*["\']([^"\']+supabase\.co)["\']', text)
    key = re.search(r'\bkey\s*:\s*["\']([^"\']+)["\']', text)
    if not url or not key:
        raise SystemExit('cdn/index.html: Supabase URL / publishable key not found')
    return url.group(1).rstrip('/'), key.group(1)


class Questions:
    def __init__(self, base: str, key: str):
        self.base, self.key = base, key

    def _get(self, query: str, count: bool = False):
        headers = {'apikey': self.key, 'Authorization': 'Bearer ' + self.key,
                   'Accept': 'application/json', 'User-Agent': UA}
        if count:
            headers.update({'Prefer': 'count=exact', 'Range': '0-0'})
        url = self.base + '/rest/v1/questions?' + query
        last = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                    body = json.loads(r.read().decode('utf-8') or '[]')
                    if count:
                        rng = r.headers.get('Content-Range') or ''
                        total = rng.rsplit('/', 1)[-1]
                        if not total.isdigit():
                            raise RuntimeError('no exact count in Content-Range: %r' % rng)
                        return int(total)
                    return body
            except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as exc:
                last = exc
                time.sleep(5 * (attempt + 1))
        raise SystemExit('Supabase read failed: %s: %s' % (type(last).__name__, last))

    @staticmethod
    def q(**params) -> str:
        return urllib.parse.urlencode(params, safe='(),.:*')

    def queue_facts(self, now: datetime) -> dict:
        active = self._get(self.q(select='id', analysis_status='in.(pending,analyzing)',
                                  analysis_attempts='lt.3'), count=True)
        done = self._get(self.q(select='id', analysis_completed_at='gte.' + iso(now - timedelta(hours=24))),
                         count=True)
        last = self._get(self.q(select='analysis_last_attempt_at', analysis_last_attempt_at='not.is.null',
                                order='analysis_last_attempt_at.desc', limit='1'))
        return {'active': active, 'completed_24h': done,
                'last_attempt_at': last[0]['analysis_last_attempt_at'] if last else None}

    def parked_since(self, since: datetime) -> list[dict]:
        return self._get(self.q(select='id,analysis_error', analysis_status='eq.review',
                                analysis_last_attempt_at='gte.' + iso(since)))

    def finished_between(self, start: datetime, end: datetime, unreviewed: bool = False) -> list[dict]:
        extra = {'legal_status': 'eq.unreviewed'} if unreviewed else {}
        return self._get(self.q(select='id,analysis_completed_at', analysis_status='eq.ready', **extra,
                                **{'and': '(analysis_completed_at.gte.%s,analysis_completed_at.lt.%s)'
                                   % (iso(start), iso(end))}, limit='1000'))

    def unlabelled_total(self) -> int:
        return self._get(self.q(select='id', analysis_status='eq.ready', legal_status='eq.unreviewed'),
                         count=True)


def seconds_to_next_tick(now: datetime) -> int:
    minute = now.minute % 30
    return (30 - minute) * 60 - now.second + 240


def run_live(args) -> dict:
    base, key = supabase_config()
    src = Questions(base, key)
    now = datetime.now(timezone.utc)
    first = judge_queue(src.queue_facts(now), now)
    queue = confirm_queue(
        first,
        recheck=lambda: src.queue_facts(datetime.now(timezone.utc)),
        now=lambda: datetime.now(timezone.utc),
        wait=lambda: time.sleep(min(args.max_wait, seconds_to_next_tick(datetime.now(timezone.utc)))),
    )
    parked = judge_parked(src.parked_since(now - WINDOW))
    unpublished = judge_unpublished(src.finished_between(now - PUBLISH_LOOKBACK, now - PUBLISH_GRACE),
                                    load_shard_status(), now - WINDOW)
    unlabelled = judge_unlabelled(
        src.finished_between(now - LABEL_GRACE - WINDOW, now - LABEL_GRACE, unreviewed=True),
        src.unlabelled_total())
    return {'checked_at': iso(now), 'queue': queue, 'parked': parked,
            'unpublished': unpublished, 'unlabelled': unlabelled}


def problems(report: dict) -> list[str]:
    out = []
    q = report['queue']
    if q['verdict'] == 'stalled':
        when = ('%s（%d 分鐘前）' % (q['last_attempt_at'], q['idle_minutes'])
                if q['last_attempt_at'] else '從來沒有處理過')
        out.append('AI 解析停住了：還有 %d 題在排隊，最後一次處理是 %s。' % (q['active'], when))
    if report['parked']['verdict'] == 'parked':
        out.append('%d 題解析連續失敗 3 次，已被擱置：%s。錯誤：%s'
                   % (len(report['parked']['ids']), '、'.join(report['parked']['ids']),
                      '；'.join(report['parked']['errors']) or '（無訊息）'))
    if report['unpublished']['verdict'] == 'unpublished':
        out.append('%d 題的新解析完成已滿 9 天，網站題庫檔還沒更新：%s。'
                   % (len(report['unpublished']['ids']), '、'.join(report['unpublished']['ids'][:30])))
    if report['unlabelled']['verdict'] == 'unlabelled':
        out.append('%d 題解析完成已滿 14 天，法規狀態自動判斷不了，需要人工確認：%s。'
                   % (len(report['unlabelled']['ids']), '、'.join(report['unlabelled']['ids'][:30])))
    return out


def summary_markdown(report: dict, found: list[str]) -> str:
    q = report['queue']
    lines = ['## AI 解析流程檢查', '',
             '- 排隊中：%d 題；24 小時內完成：%d 題；最後處理：%s'
             % (q['active'], q['completed_24h'], q['last_attempt_at'] or '—'),
             '- 判斷：%s（%s）' % (q['verdict'], q['reason']),
             '- 新擱置：%d 題；解析完成 9 天以上仍未上網站：%d 題'
             % (len(report['parked']['ids']), report['unpublished']['total']),
             '- 法規狀態尚未標記（解析已完成）：%d 題' % report['unlabelled']['total'], '']
    if found:
        lines += ['### 需要處理', ''] + ['- ' + f for f in found] + [
            '', '通常不用自己動手：把這個執行結果的連結交給 Claude，請它查原因。']
    else:
        lines.append('一切正常，不用處理。')
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- selftest

def selftest() -> None:
    now = datetime(2026, 11, 27, 6, 45, tzinfo=timezone.utc)
    ago = lambda **kw: iso(now - timedelta(**kw))
    check = lambda cond, label: None if cond else sys.exit('SELFTEST FAIL: ' + label)

    check(judge_queue({'active': 0, 'completed_24h': 0, 'last_attempt_at': ago(days=9)}, now)['verdict'] == 'ok',
          'empty queue is fine even when idle for days')
    check(judge_queue({'active': 5, 'completed_24h': 3, 'last_attempt_at': ago(minutes=40)}, now)['verdict'] == 'ok',
          'recent claim is fine')
    check(judge_queue({'active': 5, 'completed_24h': 3, 'last_attempt_at': ago(hours=3)}, now)['verdict'] == 'suspect',
          'idle queue with work is suspect first')
    check(judge_queue({'active': 5, 'completed_24h': 3, 'last_attempt_at': None}, now)['verdict'] == 'suspect',
          'never-claimed queue is suspect')
    check(judge_queue({'active': 5, 'completed_24h': 25, 'last_attempt_at': ago(hours=10)}, now)['verdict'] == 'ok',
          'pause under the daily cap is fine')
    check(judge_queue({'active': 5, 'completed_24h': 25, 'last_attempt_at': ago(hours=27)}, now)['verdict'] == 'stalled',
          'cap cannot explain a 27h pause')

    waited = []
    suspect = judge_queue({'active': 22, 'completed_24h': 0, 'last_attempt_at': ago(days=3)}, now)
    stalled = confirm_queue(suspect, lambda: {'active': 22, 'completed_24h': 0, 'last_attempt_at': ago(days=3)},
                            lambda: now + timedelta(minutes=19), lambda: waited.append(1))
    check(stalled['verdict'] == 'stalled' and waited == [1],
          'the 2026-11-23 stall (22 waiting, idle 3 days, still idle after a tick) is reported')
    refilled = confirm_queue(suspect, lambda: {'active': 22, 'completed_24h': 0,
                                               'last_attempt_at': iso(now + timedelta(minutes=15))},
                             lambda: now + timedelta(minutes=19), lambda: None)
    check(refilled['verdict'] == 'ok', 'a queue refilled minutes ago is not reported once it is claimed')
    fine = judge_queue({'active': 5, 'completed_24h': 3, 'last_attempt_at': ago(minutes=5)}, now)
    check(confirm_queue(fine, lambda: sys.exit('must not re-check a healthy queue'), lambda: now,
                        lambda: sys.exit('must not wait for a healthy queue'))['verdict'] == 'ok',
          'healthy queue needs no wait')

    check(judge_parked([])['verdict'] == 'ok', 'nothing parked')
    parked = judge_parked([{'id': 'DS-110-2-14', 'analysis_error': 'exp_others 空白'}])
    check(parked['verdict'] == 'parked' and parked['ids'] == ['DS-110-2-14'], 'parked question reported')

    shards = {'A': 'ready', 'B': 'pending', 'C': 'pending', 'D': 'pending'}
    since = now - WINDOW
    out = judge_unpublished([{'id': 'A', 'analysis_completed_at': ago(days=9, hours=1)},
                             {'id': 'B', 'analysis_completed_at': ago(days=9, hours=1)},
                             {'id': 'C', 'analysis_completed_at': ago(days=20)},
                             {'id': 'Z', 'analysis_completed_at': ago(days=9, hours=1)}], shards, since)
    check(out['ids'] == ['B'], 'only the question that just crossed 9 days is new; unknown ids ignored')
    check(out['total'] == 2, 'older unpublished questions still count in the total')
    quiet = judge_unpublished([{'id': 'C', 'analysis_completed_at': ago(days=20)}], shards, since)
    check(quiet['verdict'] == 'ok' and quiet['total'] == 1, 'an old unpublished case is not re-notified')
    check(judge_unpublished([], shards, since)['verdict'] == 'ok', 'no finished rows in the window')

    check(judge_unlabelled([], 16)['verdict'] == 'ok', 'backlog below 14 days is only a total')
    unl = judge_unlabelled([{'id': 'SP113-1-31'}], 9)
    check(unl['verdict'] == 'unlabelled' and unl['ids'] == ['SP113-1-31'], 'a question crossing 14 days is reported')

    check(seconds_to_next_tick(datetime(2026, 1, 1, 6, 45, 0, tzinfo=timezone.utc)) == 19 * 60,
          'wait reaches 4 minutes past the :00 tick')
    check(seconds_to_next_tick(datetime(2026, 1, 1, 6, 5, 30, tzinfo=timezone.utc)) == 25 * 60 - 30 + 240,
          'wait reaches 4 minutes past the :30 tick')

    report = {'queue': stalled, 'parked': parked, 'unpublished': out, 'unlabelled': unl}
    found = problems(report)
    check(len(found) == 4 and '停住' in found[0] and '人工確認' in found[3],
          'all four problems are explained in Chinese')
    check('需要處理' in summary_markdown(report, found), 'summary lists the problems')
    check('一切正常' in summary_markdown({'queue': fine, 'parked': judge_parked([]),
                                          'unpublished': judge_unpublished([], shards, since),
                                          'unlabelled': judge_unlabelled([], 0)}, []),
          'healthy summary')

    status = load_shard_status()
    check(len(status) >= 4800 and set(status.values()) <= {'ready', 'pending', 'review', 'analyzing', ''},
          'repository shards load with an analysis status per question')
    print('AI_PIPELINE_WATCH_SELFTEST_PASS')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--fail-on-problem', action='store_true')
    ap.add_argument('--max-wait', type=int, default=35 * 60,
                    help='longest wait (seconds) before re-checking a suspect queue')
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    report = run_live(args)
    found = problems(report)
    report['problems'] = found
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md = summary_markdown(report, found)
    print(md)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as fh:
            fh.write(md)
    return 1 if (found and args.fail_on_problem) else 0


if __name__ == '__main__':
    raise SystemExit(main())
