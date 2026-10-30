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
import subprocess
import unicodedata
from urllib.parse import urlsplit, parse_qs, urlunsplit, urlencode

from audit_moex_source_subjects import load_registry, url_identity
from official_essay_pdf_audit import normalize

ROOT=Path(__file__).resolve().parents[1]
TEXT_FIELDS=('question','opt_a','opt_b','opt_c','opt_d')


# Exact image-mask OCR templates visually inspected on the official PDF pages.
# Labels only: full-option images and unknown masks remain unresolved. These
# are machine extraction evidence, never independent human review.
IMAGE_LABEL_PDFS = {'104100-107-0601.pdf': '05771b264b7f310cd4be6720d73a25eb1b67411100a6376918c03c050b8ec42c',
 '105030-107-0605.pdf': '7eb6e221ff9dcb7df1f087600d089f60b083c2801b7ca20aec996d1d5ee2e791',
 '105030-107-0606.pdf': 'e219347d5b1bbe4ffa539bebf656ce196b72e569437e386fad078b37d7745687'}
IMAGE_LABEL_MASKS = {'70616a4c9c82a7c966107bdfcb5cab189b1696e27eea33255640a43fc84f5d17': {'label': 'A',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 31,
                                                                      'mask_xref': 32},
 '25036d1390d63c28d0d10d0687594fa523b102de53aaaf977fca89aa97347330': {'label': 'B',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 33,
                                                                      'mask_xref': 34},
 '347e1ac8130e7d14b0e235d437bda1f35119ecf67be4c6829bf74f80e643e87b': {'label': 'C',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 35,
                                                                      'mask_xref': 36},
 '38884caea8e67c642721c310e767ad49416c89bfe93e04122d33b9c8e9f4378f': {'label': 'D',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 37,
                                                                      'mask_xref': 38},
 '404cceaaf9dea7579ef7f7b02ba9cbfc7c9ae099c8252fb47a54eaa7a4070174': {'label': 'D',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 41,
                                                                      'mask_xref': 42},
 '09206bf33072f0f3033c01b45a53c699a28863dc5c105afdf5bd92199fc022ae': {'label': 'B',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 2,
                                                                      'image_xref': 52,
                                                                      'mask_xref': 53},
 'f70d356683d57fbd03c025decf902b2fb4ba00c1800ad8e73930e448f6ce809f': {'label': 'C',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 2,
                                                                      'image_xref': 54,
                                                                      'mask_xref': 55},
 'b538a6bdfbbaf3a1a61c36361bdd576cf2d0736d82d92978e4a11004c01376d6': {'label': 'C',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 2,
                                                                      'image_xref': 56,
                                                                      'mask_xref': 57},
 'd0edb7efa2e8df7d081726719eeb1d1dabd88f223985cb431fef998e360562e6': {'label': 'D',
                                                                      'example_pdf': '104100-107-0601.pdf',
                                                                      'page': 2,
                                                                      'image_xref': 58,
                                                                      'mask_xref': 59},
 '4cae4d913e7b1ca9c097462af32cfd5647d96adede80589a656156c7750983bf': {'label': 'B',
                                                                      'example_pdf': '105030-107-0605.pdf',
                                                                      'page': 2,
                                                                      'image_xref': 51,
                                                                      'mask_xref': 52},
 'e628c4950f2abc17fb565175d484bcecfb46b71086d4529d5a98971f65d8e614': {'label': 'A',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 29,
                                                                      'mask_xref': 30},
 '73290cb069a78eeef767bd41c62769fa7db4c18c8a26bb29b5a8fa7037b3b9b5': {'label': 'B',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 31,
                                                                      'mask_xref': 32},
 '22abe26ab950ef4afdbab284f1ce46c47005b5f1764dd16a1d6606ee4f2faf51': {'label': 'C',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 33,
                                                                      'mask_xref': 34},
 '958cc721e197cf6a292154e1623fca172dfb91183a62b6af28e3844f5d38f51f': {'label': 'D',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 35,
                                                                      'mask_xref': 36},
 'c6e0ccf9805daa227d0a1da3d70ede4b0aa32936603cba64886b7534f2f1b02b': {'label': 'A',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 1,
                                                                      'image_xref': 37,
                                                                      'mask_xref': 38},
 '9f1b921eaad319b34a879292beca41f38fdd82af7b5f6e810d9f866123363b8a': {'label': 'B',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 2,
                                                                      'image_xref': 65,
                                                                      'mask_xref': 66},
 'd1974c7fdb9b9683137227a486d78e4b662a70bdc79720ba8df6572454585cf0': {'label': 'A',
                                                                      'example_pdf': '105030-107-0606.pdf',
                                                                      'page': 3,
                                                                      'image_xref': 93,
                                                                      'mask_xref': 94}}


def decode_image_labels(raw):
    if hashlib.sha256(raw).hexdigest() not in set(IMAGE_LABEL_PDFS.values()):
        return raw, []
    import fitz
    evidence=[]
    with fitz.open(stream=raw,filetype='pdf') as document:
        for page in document:
            # get_image_rects / get_image_info identify these white 2x2 base
            # images as duplicates and lose the distinct soft mask. The actual
            # displayed image blocks retain each mask and occurrence position.
            for block in page.get_text('dict')['blocks']:
                if block['type']!=1 or not block.get('mask'):
                    continue
                digest=hashlib.sha256(block['mask']).hexdigest()
                template=IMAGE_LABEL_MASKS.get(digest)
                if template is None:
                    continue
                x0,y0,x1,y1=block['bbox']
                if not (0<x1-x0<40 and 5<y1-y0<20):
                    raise ValueError('unexpected image label geometry')
                label=template['label']
                # Insert an extraction token in a disposable in-memory copy.
                # Preserve text height/baseline and fit within the glyph's ink
                # width; tiny text would sort AFTER the option in Poppler.
                origin=fitz.Point(x0,y1-2)
                page.insert_text(origin,f'@@{label}@@',fontsize=y1-y0,
                                 fontname='courier',morph=(origin,fitz.Matrix(.28,1)))
                evidence.append(dict(page=page.number+1,bbox=list(block['bbox']),
                                     mask_sha256=digest,label=label))
        return document.tobytes(), evidence


def layout_blocks(text, base):
    """Audit-only block splitting: whitespace must never swallow the next line.

    A raised exponent can occupy its own numeric line just before question 7.
    The import parser's ``\\s+`` consumes that newline and hides the real 7.
    Keep the importer untouched; this is read-only comparison, never import.
    """
    if '乙、測驗題部分' not in text:
        raise ValueError('missing MCQ section')
    text=base.strip_headers(text.split('乙、測驗題部分',1)[1])
    chosen=[]
    for match in re.finditer(r'(?m)^[ \t]*(\d{1,2})[ \t]+(?=\S)',text):
        if int(match.group(1))==len(chosen)+1:
            chosen.append(match)
            if len(chosen)==40:break
    if len(chosen)!=40:
        raise ValueError(f'layout question numbering incomplete: {len(chosen)}/40')
    return [(i+1,text[m.end():chosen[i+1].start() if i<39 else len(text)]) for i,m in enumerate(chosen)]


def layout_question(raw, rule, base):
    if set(rule)-{'answer','accepted_answers','grading_mode'}:
        raise ValueError('answer rule must not supply question text')
    parts=re.split(r'@@([ABCD])@@',base.normalize_option_markers(raw))
    if parts[1::2]!=list('ABCD'):
        raise ValueError('layout requires exactly one A/B/C/D marker in order')
    values=[base.clean(parts[i]) for i in (0,2,4,6,8)]
    if any(not value for value in values):
        raise ValueError('layout stem or option is empty')
    return dict(zip(TEXT_FIELDS,values),**rule)


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
    # Position-aware text fixes source stream ordering such as "254613<A>".
    # This is one fixed extractor, never choose whichever output matches stored
    # content. Missing image-only labels remain review; do not infer A-D.
    extractor_version=subprocess.run(['pdftotext','-v'],capture_output=True,text=True,check=True).stderr.splitlines()[0]
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

    image_decodings={}

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
            extraction_bytes,image_markers=decode_image_labels(question_bytes)
            extracted=subprocess.run(['pdftotext','-layout','-','-'],input=extraction_bytes,capture_output=True,check=True).stdout.decode('utf-8')
            text=unicodedata.normalize('NFKC',extracted)
            if image_markers:image_decodings[code+'/'+subject]=dict(pdf_sha256=r['pdf_sha256'],decoder='PyMuPDF '+__import__('fitz').VersionBind,markers=image_markers)
            text_parse_error=None
            try:
                blocks=layout_blocks(text,parser.base)
            except Exception as error:
                text_parse_error=str(error)
                blocks=[(q,None) for q in range(1,41)]
            result=[]
            for q,raw in blocks:
                current=stored[(year,round_name,subject,str(q))]
                try:
                    if raw is None:raise ValueError(text_parse_error)
                    official=layout_question(raw,rules[q-1],parser.base)
                    row=compare(current,official)
                    row['pdf_text_sha256']=hashlib.sha256(json.dumps({k:official[k] for k in TEXT_FIELDS},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                except ValueError as error:
                    # Failed extraction has no official text. Compare the real
                    # answer rule separately, never copy stored text as evidence.
                    before,after=grading_semantics(current),grading_semantics(rules[q-1])
                    row=dict(status='review',reason=str(error),text_differences={},
                             answer_difference={'stored':before,'official_extraction':after} if before is None or after is None or before!=after else None,
                             primary_answer_differs_but_same_accepted_set=before==after and current.get('answer')!=rules[q-1].get('answer'),
                             human_approval=False,automatic_release_approval=False)
                row.update(answer_comparison_completed=True,id=current['id'],qno=str(q),answer_source_url=answer['url'],answer_pdf_sha256=answer['sha256'],answer_kind=kind,**base);result.append(row)
            return result
        except Exception as error:
            return [dict(id=stored[(year,round_name,subject,str(q))]['id'],qno=str(q),status='review',reason=str(error),human_approval=False,automatic_release_approval=False,**base) for q in range(1,41)]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=[r for group in pool.map(inspect,sorted(registry)) for r in group]
    return dict(schema_version=1,input_sha256=fingerprints,scope='normalized official MCQ text, options and observed final answer sheet; no explanation or human approval',text_extractor=dict(engine=extractor_version,mode='-layout',question_failure_scope='single_question'),image_marker_decodings=dict(sorted(image_decodings.items())),questions=len(rows),counts=dict(Counter(r['status'] for r in rows)),parse_review_count=sum('reason' in r for r in rows),text_review_count=sum(bool(r.get('text_differences')) for r in rows),answer_comparison_count=sum(bool(r.get('answer_comparison_completed')) for r in rows),answer_review_count=sum(bool(r.get('answer_difference')) for r in rows),equivalent_multi_answer_representatives=sum(bool(r.get('primary_answer_differs_but_same_accepted_set')) for r in rows),automatic_release_approval=False,official_core_modified=False,rows=rows)


def selftest():
    assert len(IMAGE_LABEL_PDFS)==3 and set(x['label'] for x in IMAGE_LABEL_MASKS.values())==set('ABCD')
    assert decode_image_labels(b'unknown PDF or changed bytes')==(b'unknown PDF or changed bytes',[])
    # Keep deterministic CI independent of the PDF importer's live-sync deps.
    from types import SimpleNamespace
    def markers(text):
        for glyph,letter in zip('\ue18c\ue18d\ue18e\ue18f','ABCD'):
            text=text.replace(glyph,f'@@{letter}@@')
        return text
    base=SimpleNamespace(strip_headers=lambda text:text,clean=lambda text:text.strip(),normalize_option_markers=markers)
    raw='哪項正確？\n\ue18c甲 \ue18d乙 \ue18e丙 \ue18f丁'
    assert layout_question(raw,{'answer':'A'},base)['opt_d']=='丁'
    for bad in (raw.replace('\ue18f',''),raw.replace('\ue18c','\ue18d'),raw.replace('丁',''),raw+'\ue18c多出的選項'):
        try:layout_question(bad,{'answer':'A'},base)
        except ValueError:pass
        else:raise AssertionError('missing/duplicate/out-of-order/empty option accepted')
    try:layout_question(raw,dict(answer='A',question='stored text must never overwrite PDF text'),base)
    except ValueError:pass
    else:raise AssertionError('stored text accepted as an official answer rule')
    text='乙、測驗題部分\n'+'\n'.join(('      2\n' if n==7 else '')+f'{n} 題幹\n\ue18c甲 \ue18d乙 \ue18e丙 \ue18f丁' for n in range(1,41))
    assert [q for q,raw in layout_blocks(text,base)]==list(range(1,41))
    try:layout_blocks(text.replace('13 題幹','13X 題幹'),base)
    except ValueError:pass
    else:raise AssertionError('incomplete numbering accepted')
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
    report=audit(a.evidence_dir,a.answer_evidence_dir);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('rows','image_marker_decodings')},ensure_ascii=False))

if __name__=='__main__':main()
