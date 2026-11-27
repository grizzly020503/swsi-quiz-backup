#!/usr/bin/env python3
"""Derive the watched-law list from the question bank (以題庫推法).

Every law or order the bank relies on should be watched, and nothing else.
A question relies on a law when its official text (question and options)
names the law, when its reviewed legal note names it, or when its reviewed
legal source URL points at it. Names are matched against the official MOJ
Open API corpus (laws and orders), so research-method words such as
內容分析法 never count: only exact MOJ names do.

--report  download the MOJ corpus and print what the watch list would gain
--write   also update data/legal_watch_names.json (never drops a name)
--selftest offline checks with a synthetic corpus

The list only grows. A watched name no longer cited keeps its place, so the
registry and earlier review evidence stay valid; its count shows 0.
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ROOT / 'data/legal_watch_names.json'
SHARDS = ROOT / 'cdn/question-shards'
# MOJ appends the enactment date to some names, e.g. 最低工資法（112.12.27制定）.
DATE_SUFFIX = re.compile(r'[（(][0-9０-９.．]+(?:制定|修正)[）)]$')
PCODE = re.compile(r'pcode=([A-Za-z0-9]+)')
CJK = re.compile(r'[㐀-鿿豈-﫿]')
# A short name (民法, 工會法) must stand as a citation, not inside another word
# (公民法治, 罪刑法定): a particle or non-CJK character before it, or a
# citation word after it.
SHORT = 3
LEFT_OK = set('依據照按之與及和或、「《〈（(：:於對在由為即與暨並及')
RIGHT_OK = ('第', '規定', '所稱', '所定', '之規定', '上', '中', '總則', '親屬', '繼承', '債編', '物權')
# Words that continue a name ending in 法 (法律, 法院, 法人, 法定, 法規 ...):
# not a citation. 規定 and 定義 after a name are citations (民法規定).
BAD_AFTER_FA = set('律院官人定規令源制治案務益理學網庭警系')
CITATION_AFTER_FA = ('規定', '定義')


def norm(text: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(text or '')))


def law_name(raw: str) -> str:
    return DATE_SUFFIX.sub('', norm(raw))


def load_corpus(path=None) -> dict:
    """{normalized name: pcode} for every current MOJ law and order."""
    if path:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    from legal_history_fetch import APIS, download
    out = {}
    for url in APIS:
        for law in download(url)['Laws']:
            m = PCODE.search(law.get('LawURL') or '')
            name = law_name(law.get('LawName') or '')
            if m and len(name) >= 2:
                out.setdefault(name, m.group(1).upper())
    return out


class Matcher:
    def __init__(self, corpus: dict, aliases: dict):
        self.names = dict(corpus)
        for old, new in aliases.items():
            if new in corpus:
                self.names[norm(old)] = corpus[new]
        self.aliases = {norm(k): v for k, v in aliases.items()}
        self.lengths = defaultdict(set)
        for name in self.names:
            self.lengths[name[-1]].add(len(name))

    def canonical(self, name: str) -> str:
        return self.aliases.get(name, name)

    def find(self, text: str) -> set:
        """Canonical names cited in text: longest match at each end, nested
        shorter matches dropped, short names only in citation context."""
        s = norm(text)
        spans = []
        for j in range(1, len(s) + 1):
            for n in sorted(self.lengths.get(s[j - 1], ()), reverse=True):
                k = j - n
                if k < 0 or s[k:j] not in self.names:
                    continue
                name = s[k:j]
                after = s[j:j + 4]
                if name.endswith('法') and after[:1] in BAD_AFTER_FA and not after.startswith(CITATION_AFTER_FA):
                    continue
                if n <= SHORT:
                    before = s[k - 1] if k else ''
                    if before and CJK.match(before) and before not in LEFT_OK and not after.startswith(RIGHT_OK):
                        continue
                spans.append((k, j, name))
                break
        kept = [a for a in spans if not any(b != a and b[0] <= a[0] and a[1] <= b[1] for b in spans)]
        return {self.canonical(name) for _, _, name in kept}


def load_questions(root: Path = ROOT) -> list:
    manifest = json.loads((root / 'cdn/question-shards/manifest.json').read_text(encoding='utf-8'))
    rows = []
    for entry in manifest['shards']:
        rows += json.loads((root / 'cdn/question-shards' / entry['file']).read_text(encoding='utf-8'))['questions']
    return rows


def derive(rows: list, corpus: dict, aliases: dict) -> dict:
    """{canonical name: {'ids': set, 'via': {'text': n, 'note': n, 'url': n}}}"""
    matcher = Matcher(corpus, aliases)
    by_pcode = {}
    for name, pcode in corpus.items():
        by_pcode.setdefault(pcode, name)
    out = defaultdict(lambda: {'ids': set(), 'via': defaultdict(int)})
    for row in rows:
        ident = row['id']
        official = ' '.join(str(row.get(k) or '') for k in ('question', 'opt_a', 'opt_b', 'opt_c', 'opt_d'))
        found = {'text': matcher.find(official)}
        reviewed = row.get('legal_status') in ('verified_current', 'changed')
        found['note'] = matcher.find(row.get('legal_note') or '') if reviewed else set()
        m = PCODE.search(str(row.get('legal_source_url') or '')) if reviewed else None
        found['url'] = {matcher.canonical(by_pcode[m.group(1).upper()])} if m and m.group(1).upper() in by_pcode else set()
        for via, names in found.items():
            for name in names:
                out[name]['ids'].add(ident)
                out[name]['via'][via] += 1
    return out


def dump(rows: list) -> str:
    """The file's existing layout: one compact entry per line."""
    return '[\n' + ',\n'.join('  ' + json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in rows) + '\n]\n'


def merged_list(current: list, derived: dict) -> list:
    names = {(c if isinstance(c, str) else c['name']) for c in current}
    names |= set(derived)
    rows = [{'name': n, 'question_count': len(derived[n]['ids']) if n in derived else 0} for n in names]
    return sorted(rows, key=lambda r: (-r['question_count'], r['name']))


ALIASES = {
    # Old or short names in exam questions -> the current MOJ name.
    '性別工作平等法': '性別平等工作法',
    '兩公約施行法': '公民與政治權利國際公約及經濟社會文化權利國際公約施行法',
    '人權公約施行法': '公民與政治權利國際公約及經濟社會文化權利國際公約施行法',
    '社會工作師執業登記及繼續教育辦法': '社會工作師接受繼續教育及執業執照更新辦法',
}


def report(current: list, derived: dict) -> None:
    watched = {(c if isinstance(c, str) else c['name']) for c in current}
    added = sorted((n for n in derived if n not in watched), key=lambda n: (-len(derived[n]['ids']), n))
    print(f'questions cite {len(derived)} MOJ laws/orders; watched now {len(watched)}; would add {len(added)}')
    for n in added:
        d = derived[n]
        via = ', '.join(f'{k} {v}' for k, v in sorted(d['via'].items()))
        print(f'  + {len(d["ids"]):3d}  {n}  ({via})  e.g. {", ".join(sorted(d["ids"])[:4])}')
    idle = sorted(n for n in watched if n not in derived)
    print(f'watched but not cited by any question: {len(idle)}', ' '.join(idle))


def selftest() -> None:
    corpus = {'民法': 'B0000001', '社會救助法': 'D0050078', '社會救助法施行細則': 'D0050079',
              '最低工資法': 'N0030028', '工會法': 'N0020001', '性別平等工作法': 'N0030014',
              '公民與政治權利國際公約及經濟社會文化權利國際公約施行法': 'I0020028'}
    m = Matcher(corpus, ALIASES)
    cases = {
        '依民法第1084條規定': {'民法'},
        '我國民法規定成年年齡': {'民法'},
        '公民法治教育': set(),
        '罪刑法定主義': set(),
        '依社會救助法施行細則第5條': {'社會救助法施行細則'},
        '社會救助法與社會救助法施行細則': {'社會救助法', '社會救助法施行細則'},
        '內容分析法與焦點團體法': set(),
        '依性別工作平等法規定': {'性別平等工作法'},
        '依兩公約施行法': {'公民與政治權利國際公約及經濟社會文化權利國際公約施行法'},
        '依最低工資法（112.12.27制定）': {'最低工資法'},
        '加入工會法所定之工會': {'工會法'},
        '法律與法院': set(),
        '社會福利法規': set(),
        '依民法定義': {'民法'},
        '依民 法 第 12 條': {'民法'},
    }
    for text, want in cases.items():
        got = m.find(text)
        assert got == want, (text, got, want)
    assert law_name('最低工資法（112.12.27制定）') == '最低工資法'
    rows = [
        {'id': 'Q1', 'question': '依社會救助法第8條', 'legal_status': 'changed',
         'legal_note': '依最低工資法第18條', 'legal_source_url': 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0030028'},
        {'id': 'Q2', 'question': '公民法治', 'legal_status': 'unreviewed', 'legal_note': '依民法第12條',
         'legal_source_url': 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0000001'},
        {'id': 'Q3', 'opt_a': '性別工作平等法', 'legal_status': 'not_applicable'},
    ]
    d = derive(rows, corpus, ALIASES)
    assert {n: sorted(v['ids']) for n, v in d.items()} == {
        '社會救助法': ['Q1'], '最低工資法': ['Q1'], '性別平等工作法': ['Q3']}, d
    assert dict(d['最低工資法']['via']) == {'note': 1, 'url': 1}
    merged = merged_list([{'name': '老人福利法', 'question_count': 61}, {'name': '社會救助法', 'question_count': 48}], d)
    assert merged == [{'name': '性別平等工作法', 'question_count': 1}, {'name': '最低工資法', 'question_count': 1},
                      {'name': '社會救助法', 'question_count': 1}, {'name': '老人福利法', 'question_count': 0}], merged
    current = json.loads(NAMES.read_text(encoding='utf-8'))
    assert dump(current) == NAMES.read_text(encoding='utf-8'), 'watch list layout changed'
    print(f'LEGAL WATCH FROM BANK SELFTEST PASS: {len(cases)} matching cases; reviewed-only notes and URLs; list only grows')


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--report', action='store_true')
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--selftest', action='store_true')
    ap.add_argument('--corpus', help='cached {name: pcode} JSON instead of downloading the MOJ corpus')
    ap.add_argument('--save-corpus', help='write the downloaded {name: pcode} map here')
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    corpus = load_corpus(args.corpus)
    if len(corpus) < 1000:
        raise SystemExit(f'MOJ corpus too small ({len(corpus)} names); refusing to derive the watch list')
    if args.save_corpus:
        Path(args.save_corpus).write_text(json.dumps(corpus, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    current = json.loads(NAMES.read_text(encoding='utf-8'))
    derived = derive(load_questions(), corpus, ALIASES)
    report(current, derived)
    if args.write:
        NAMES.write_text(dump(merged_list(current, derived)), encoding='utf-8')
        print('wrote', NAMES.relative_to(ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
