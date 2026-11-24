#!/usr/bin/env python3
"""Read-only: print article texts of requested old MOJ law versions (LawOldVer).

Reads audit/legal_history_oldver_requests.json and prints one @@OLD JSON line
per version with its articles. No repository, database or website writes.
"""
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode={pcode}&lnndate={lnndate}&lser=001'
UA = 'swsi-legal-oldver-fetch/1.0 (+educational question bank)'
HEAD = re.compile(r'<div[^>]*class="[^"]*\bcol-no\b[^"]*"[^>]*>\s*(?:<a[^>]*>)?\s*第\s*([^<]+?)\s*條', re.S)
BODY = re.compile(r'<div[^>]*class="[^"]*\blaw-article\b[^"]*"[^>]*>(.*?)</div>\s*</div>', re.S)


def text(fragment):
    fragment = re.sub(r'<br\s*/?>', '\n', fragment)
    fragment = re.sub(r'</div>', '\n', fragment)
    fragment = re.sub(r'<[^>]+>', '', fragment)
    return '\n'.join(l.strip() for l in html.unescape(fragment).splitlines() if l.strip())


def fetch(url):
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=60, headers={'User-Agent': UA})
            r.raise_for_status()
            if '全國法規資料庫' not in r.text:
                raise RuntimeError('not an MOJ page')
            return r.text
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 ** attempt)
    raise last


def main():
    req = json.loads((ROOT / 'audit/legal_history_oldver_requests.json').read_text(encoding='utf-8'))
    bad = 0
    for v in req['versions']:
        url = URL.format(**v)
        page = fetch(url)
        heads = list(HEAD.finditer(page))
        arts = []
        for i, m in enumerate(heads):
            seg = page[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(page)]
            b = BODY.search(seg)
            if b:
                arts.append({'no': m.group(1).strip().replace(' ', ''), 'text': text(b.group(1))})
        title = re.search(r'<title[^>]*>(.*?)</title>', page, re.S)
        ok = len(arts) > 0 and v['law'] in page
        bad += not ok
        print('@@OLD', json.dumps({**v, 'url': url, 'title': title.group(1).strip() if title else '',
                                   'ok': ok, 'articles': arts}, ensure_ascii=False))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
