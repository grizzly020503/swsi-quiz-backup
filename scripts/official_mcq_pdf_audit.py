#!/usr/bin/env python3
"""Read-only comparison of official MCQ text and observed final answer sheets.

Uses the existing MOEX import parser. Does not approve a correction, a rubric,
student-facing explanations or unresolved parser output. Never downloads files.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit, parse_qs, urlunsplit, urlencode

from audit_moex_source_subjects import load_registry, url_identity
from official_essay_pdf_audit import normalize

ROOT=Path(__file__).resolve().parents[1]
TEXT_FIELDS=('question','opt_a','opt_b','opt_c','opt_d')


def answer_identity(url):
    parsed=urlsplit(url)
    params=parse_qs(parsed.query,keep_blank_values=True)
    if params.get('t') not in (['S'],['M']):
        raise ValueError('not an official answer kind')
    kind=params['t'][0]
    params['t']=['Q']
    question_url=urlunsplit(parsed._replace(query=urlencode({k:v[0] if len(v)==1 else v for k,v in params.items()},doseq=True)))
    identity=url_identity(question_url)
    identity['t']=kind
    return identity


def grading_semantics(row):
    mode=row.get('grading_mode') or 'standard'
    accepted=row.get('accepted_answers')
    if mode=='standard':
        values=accepted if accepted else [row.get('answer')]
        if (not isinstance(values,list) or not values or any(not isinstance(v,str) or len(v)!=1 or v not in 'ABCD' for v in values)
                or len(set(values))!=len(values) or row.get('answer') not in values):
            return None
        return (mode,tuple(sorted(values)))
    if mode in ('all_credit','any_answer') and row.get('answer')=='一律給分' and not accepted:
        return (mode,)
    return None


def compare(stored,official):
    differences={k:{'stored':stored.get(k),'official_extraction':official.get(k)}
                 for k in TEXT_FIELDS if normalize(stored.get(k) or '')!=normalize(official.get(k) or '')}
    before,after=grading_semantics(stored),grading_semantics(official)
    different=before is None or after is None or before!=after
    # A legacy display answer may be any accepted answer; selecting B as the
    # parser's representative must not manufacture a C -> B answer correction.
    return {'status':'review' if differences or different else 'normalized_pdf_text_and_answer_match',
            'text_differences':differences,'answer_difference':{'stored':before,'official_extraction':after} if different else None,
            'primary_answer_differs_but_same_accepted_set':not different and stored.get('answer')!=official.get('answer'),
            'human_approval':False,'automatic_release_approval':False}


def answer_header_errors(text,record):
    compact=normalize(text)
    year,round_no=record['session'].split('-')
    errors=[]
    if f"{year}年第{'一' if round_no=='1' else '二'}次" not in compact:errors.append('answer year/round mismatch')
    # Check the exact subject label before its paper-code suffix, not a substring
    # such as 社會工作 matching 社會工作管理.
    subject=re.search(r'([^\n]+)[（(]試題代號',text)
    corrected_subject=re.search(r'科目名稱[:：][ \t]*([^\n]+)',text)
    label=subject.group(1) if subject else corrected_subject.group(1) if corrected_subject else ''
    if normalize(label)!=normalize(record['subject']):errors.append('answer subject label mismatch')
    if '社會工作師' not in compact or not any(s in compact for s in ('測驗式試題標準答案','更正答案','答案更正')):errors.append('answer class/type mismatch')
    return errors


def audit(question_dir,answer_dir):
    import moex_sync_v2 as parser
    registry=load_registry()
    fingerprint_paths=['scripts/official_mcq_pdf_audit.py','scripts/moex_sync.py','scripts/moex_sync_v2.py','cdn/question-shards/manifest.json','data/moex_source_subjects.v1.json','data/moex_answer_sources.v1.json']
    fingerprints={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in fingerprint_paths}
    transport=json.loads((answer_dir/'http.json').read_text())
    indexed={}
    for r in transport:
        key=(r['exam_code'],r['subject'],r.get('kind'))
        if key in indexed:raise ValueError('duplicate answer HTTP identity')
        indexed[key]=r
    stored={}
    for p in sorted((ROOT/'cdn/question-shards').glob('[0-9][0-9][0-9]-[12].json')):
        payload=json.loads(p.read_text());rows=payload if isinstance(payload,list) else payload['questions']
        for r in rows:
            key=(str(r['year']),r['round'],r['subject'],str(r['qno']))
            if key in stored:raise ValueError('duplicate stored MCQ identity')
            stored[key]=r
    if len(stored)!=4800:raise ValueError('expected 4800 distinct MCQs')

    def inspect(key):
        code,subject=key;r=registry[key];year,round_no=r['session'].split('-');round_name='第一次' if round_no=='1' else '第二次'
        base={'exam_code':code,'subject':subject,'session':r['session'],'question_source_url':r['url'],'question_pdf_sha256':r['pdf_sha256']}
        try:
            question_bytes=(question_dir/f"{code}-{r['c']}-{r['s']}.pdf").read_bytes()
            if hashlib.sha256(question_bytes).hexdigest()!=r['pdf_sha256']:raise ValueError('question PDF hash mismatch')
            directory=(question_dir/f'index-{code}.html').read_bytes()
            if hashlib.sha256(directory).hexdigest()!=r['index_sha256']:raise ValueError('official directory hash mismatch')
            observed={}
            for href in re.findall(r'href="([^"]+)"',directory.decode('utf-8-sig'),re.I):
                from urllib.parse import urljoin
                url=urljoin(r['index_url'],html.unescape(href))
                try:identity=answer_identity(url)
                except (ValueError,TypeError):continue
                if all(identity[k]==r[k] for k in ('c','s')) and identity['code']==code:
                    observed[identity['t']]=url
            if 'S' not in observed:raise ValueError('standard answer absent from observed directory')
            kind='M' if 'M' in observed else 'S'
            answer=indexed[(code,subject,kind)]
            if answer['status']!='downloaded' or answer['http_status']!=200 or 'pdf' not in answer['mime'].lower():raise ValueError('observed final answer PDF unavailable; do not fall back')
            if answer_identity(answer['url'])!=answer_identity(observed[kind]) or answer['index_sha256']!=r['index_sha256']:raise ValueError('answer source not bound to official directory')
            data=(answer_dir/answer['file']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=answer['sha256'] or not data.startswith(b'%PDF'):raise ValueError('answer PDF hash mismatch')
            answer_text=unicodedata.normalize('NFKC',parser.base.pdf_text(data))
            errors=answer_header_errors(answer_text,r)
            if errors:raise ValueError('; '.join(errors))
            rules=parser.base.parse_answers_pdf(data)
            text=unicodedata.normalize('NFKC',parser.base.pdf_text(question_bytes))
            profile=next(s for s in parser.base.SUBJECTS if s['name']==subject)
            text_parse_error=None
            try:
                rows=parser.base.parse_mc(text,profile,code,year,round_name,rules)
                if len(rows)!=40:raise ValueError('parser did not extract exactly 40 questions')
            except Exception as error:
                # A question-layout failure must not hide a successfully parsed
                # official answer table. Hold the text while comparing all rules.
                text_parse_error=str(error)
                rows=[]
                for q,rule in enumerate(rules,1):
                    current=stored[(year,round_name,subject,str(q))]
                    rows.append(dict(current,**rule,accepted_answers=rule.get('accepted_answers')) if 'accepted_answers' not in rule else dict(current,**rule))
            result=[]
            for official in rows:
                current=stored[(year,round_name,subject,str(official['qno']))]
                row=compare(current,official)
                if text_parse_error:row.update(status='review',reason=text_parse_error)
                row.update(answer_comparison_completed=True,id=current['id'],qno=str(official['qno']),answer_source_url=answer['url'],answer_pdf_sha256=answer['sha256'],answer_kind=kind,**base);result.append(row)
            return result
        except Exception as error:
            return [dict(id=stored[(year,round_name,subject,str(q))]['id'],qno=str(q),status='review',reason=str(error),human_approval=False,automatic_release_approval=False,**base) for q in range(1,41)]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=[r for group in pool.map(inspect,sorted(registry)) for r in group]
    return dict(schema_version=1,input_sha256=fingerprints,scope='normalized official MCQ text, options and observed final answer sheet; no explanation or human approval',questions=len(rows),counts=dict(Counter(r['status'] for r in rows)),parse_review_count=sum('reason' in r for r in rows),text_review_count=sum(bool(r.get('text_differences')) for r in rows),answer_comparison_count=sum(bool(r.get('answer_comparison_completed')) for r in rows),answer_review_count=sum(bool(r.get('answer_difference')) for r in rows),equivalent_multi_answer_representatives=sum(bool(r.get('primary_answer_differs_but_same_accepted_set')) for r in rows),automatic_release_approval=False,official_core_modified=False,rows=rows)


def selftest():
    a=dict(question='哪項正確？',opt_a='甲',opt_b='乙',opt_c='丙',opt_d='丁',answer='A',accepted_answers=None,grading_mode='standard')
    assert compare(a,dict(a,question='哪項正確?'))['status']=='normalized_pdf_text_and_answer_match'
    for b in (dict(a,question='哪項不正確？'),dict(a,opt_b='丁'),dict(a,answer='B'),dict(a,accepted_answers=['A','B']),dict(a,grading_mode='any_answer')):
        assert compare(a,b)['status']=='review'
    assert compare(dict(a,accepted_answers=['A','B']),dict(a,answer='B',accepted_answers=['A','B']))['status']=='normalized_pdf_text_and_answer_match'
    assert grading_semantics(dict(a,accepted_answers=['A','A'])) is None
    for kind in ('S','M'):
        assert answer_identity(f'https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?t={kind}&code=113030&c=103&s=0304&q=1')['t']==kind
    for bad in ('https://example.com/exam/wHandExamQandA_File.ashx?t=S&code=113030&c=103&s=0304&q=1','https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?t=S&t=M&code=113030&c=103&s=0304&q=1'):
        try:answer_identity(bad)
        except ValueError:pass
        else:raise AssertionError('untrusted or ambiguous URL accepted')
    header={'session':'113-1','subject':'社會工作'}
    for text in ('113年第一次社會工作師\n社會工作（試題代號：1103)\n測驗式試題標準答案','113年第一次社會工作師\n科目名稱： 社會工作\n測驗題標準答案更正'):
        assert not answer_header_errors(text,header)
        assert answer_header_errors(text,dict(header,subject='社會工作管理'))
    print('OFFICIAL MCQ PDF AUDIT SELFTEST OK: negation, options, answer, multi-answer and scoring differences held; sources strict')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-dir',type=Path);p.add_argument('--answer-evidence-dir',type=Path);p.add_argument('--out',type=Path);p.add_argument('--selftest',action='store_true');a=p.parse_args()
    if a.selftest:selftest();return
    if not a.evidence_dir or not a.answer_evidence_dir or not a.out:p.error('both evidence directories and --out required')
    report=audit(a.evidence_dir,a.answer_evidence_dir);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False))

if __name__=='__main__':main()
