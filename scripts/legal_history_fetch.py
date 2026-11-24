#!/usr/bin/env python3
"""Read-only: fetch MOJ law history evidence for the watched laws.

Downloads the official MOJ Open API law/order corpora (ZIP with one JSON) and
keeps, for every watched law (data/legal_watch_state.json), its name, PCode,
modified date, LawHistories text and all current articles. Writes one JSON
report; never touches the repository, database or website.
"""
import argparse
import io
import json
import re
import time
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
APIS = ('https://law.moj.gov.tw/api/ch/law/json', 'https://law.moj.gov.tw/api/ch/order/json')
UA = 'swsi-legal-history-fetch/1.0 (+educational question bank)'


def download(url):
    last = None
    for attempt in range(6):
        try:
            r = requests.get(url, timeout=300, headers={'User-Agent': UA})
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                names = [n for n in z.namelist() if n.lower().endswith('.json')]
                assert len(names) == 1, names
                return json.loads(z.read(names[0]).decode('utf-8-sig'))
        except Exception as exc:  # noqa: BLE001
            # MOJ intermittently returns an HTML page instead of the ZIP; wait and retry.
            last = exc
            time.sleep(15 * (attempt + 1))
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    state = json.loads((ROOT / 'data/legal_watch_state.json').read_text(encoding='utf-8'))
    want = {}
    for name, rec in state['records'].items():
        m = re.search(r'pcode=([A-Za-z0-9]+)', rec.get('official_url') or '')
        if m:
            want[m.group(1).upper()] = name
    out = {'source': list(APIS), 'update_dates': [], 'laws': {}}
    for url in APIS:
        payload = download(url)
        out['update_dates'].append(payload.get('UpdateDate'))
        for law in payload['Laws']:
            m = re.search(r'pcode=([A-Za-z0-9]+)', law.get('LawURL') or '')
            if not m or m.group(1).upper() not in want:
                continue
            out['laws'][want[m.group(1).upper()]] = {
                'pcode': m.group(1).upper(), 'name': law.get('LawName'), 'url': law.get('LawURL'),
                'modified': law.get('LawModifiedDate'), 'effective': law.get('LawEffectiveDate'),
                'effective_note': law.get('LawEffectiveNote'), 'abandon': law.get('LawAbandonNote'),
                'histories': law.get('LawHistories'),
                'articles': [{'type': a.get('ArticleType'), 'no': a.get('ArticleNo'), 'text': a.get('ArticleContent')}
                             for a in law.get('LawArticles') or []],
            }
    out['missing'] = sorted(set(want.values()) - set(out['laws']))
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('laws:', len(out['laws']), 'missing:', out['missing'])


if __name__ == '__main__':
    main()
