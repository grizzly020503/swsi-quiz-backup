#!/usr/bin/env python3
"""Prioritize unresolved official PDF differences; never approve or edit questions."""
import argparse
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def compact(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(text or '')))


def flags(before, after):
    a, b = compact(before), compact(after)
    result = []
    if re.findall(r'\d+(?:\.\d+)?', a) != re.findall(r'\d+(?:\.\d+)?', b):
        result.append('numeric_tokens_differ')
    if Counter(c for c in a if c in '不未無非除') != Counter(c for c in b if c in '不未無非除'):
        result.append('negation_or_exception_characters_differ')
    if any(unicodedata.category(c) == 'Co' for c in a + b):
        result.append('private_use_font_glyph')
    strip = lambda value: ''.join(c for c in value if not unicodedata.category(c).startswith('P'))
    if a != b and strip(a) == strip(b):
        result.append('punctuation_only_difference_requires_review')
    elif a != b:
        result.append('wording_or_symbol_difference')
    return result


def build():
    from official_pdf_text_release_gate import inspect
    holds = inspect()  # Reject stale snapshots before creating a review queue.
    report = []
    inputs = {}
    for kind in ('mcq', 'essay'):
        path = ROOT / f'audit/official_{kind}_pdf_comparison_20261025.json'
        inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for row in json.loads(path.read_text())['rows']:
            if row['status'] != 'review':
                continue
            differences = []
            if kind == 'mcq':
                for field, delta in row.get('text_differences', {}).items():
                    a, b = delta['stored'], delta['official_extraction']
                    differences.append(dict(field=field, stored=a, official_extraction=b, flags=flags(a,b)))
            else:
                # Essay snapshots already contain exact normalized edit spans.
                for delta in row.get('differences', []):
                    a, b = delta['stored'], delta['official_extraction']
                    differences.append(dict(field='q', stored_span=a, official_span=b,
                                            context=delta.get('context'), flags=flags(a,b)))
            signals = sorted({flag for delta in differences for flag in delta['flags']})
            if row.get('reason') or row.get('reasons') == ['existing_parser_cannot_extract_exactly_two_essays']:
                signals.append('incomplete_pdf_extraction')
            if row.get('answer_difference'):
                signals.append('grading_difference')
            priority = 0 if set(signals) & {'grading_difference','numeric_tokens_differ','negation_or_exception_characters_differ'} else 1 if set(signals) & {'incomplete_pdf_extraction','private_use_font_glyph','wording_or_symbol_difference'} else 2
            report.append(dict(id=row['id'], kind=kind, priority=priority, flags=signals,
                               source_url=row.get('question_source_url',row.get('source_url')),
                               pdf_sha256=row.get('question_pdf_sha256',row.get('pdf_sha256')),
                               extraction_reason=row.get('reason',row.get('reasons')),
                               differences=differences, status='review', human_approval=False,
                               automatic_release_approval=False))
    if len(report) != sum(holds.values()) or len({r['id'] for r in report}) != len(report):
        raise ValueError('review queue identities/count do not match current release gate')
    report.sort(key=lambda row:(row['priority'],row['kind'],row['id']))
    return dict(schema_version=1, input_sha256=inputs, unresolved=len(report),
                priority_counts=dict(Counter(str(row['priority']) for row in report)),
                flag_counts=dict(Counter(flag for row in report for flag in row['flags'])),
                priority_meaning={'0':'check numbers, negation and grading first; may be layout artifacts',
                                  '1':'wording, symbol, font or extraction differences',
                                  '2':'punctuation-only differences; still require review'},
                scope='triage only; priority is not proof of an error or release approval',
                official_core_modified=False, release_approval=False, rows=report)


def selftest():
    assert 'numeric_tokens_differ' in flags('第12條','第21條')
    assert 'negation_or_exception_characters_differ' in flags('應介入','不應介入')
    assert flags('說明。','說明，') == ['punctuation_only_difference_requires_review']
    assert 'private_use_font_glyph' in flags('一','\ue129')
    assert flags('倫理 \n','倫理') == []
    assert 'wording_or_symbol_difference' in flags('及','與')
    print('PDF REVIEW TRIAGE SELFTEST OK: numeric/negation/font/punctuation signals; no approvals')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--selftest',action='store_true')
    args=parser.parse_args()
    if args.selftest:
        selftest()
        return
    result=build()
    if args.out:
        args.out.parent.mkdir(exist_ok=True,parents=True)
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))


if __name__ == '__main__':
    main()
