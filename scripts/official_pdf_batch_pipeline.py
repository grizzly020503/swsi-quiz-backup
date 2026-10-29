#!/usr/bin/env python3
"""Resumable official-PDF audit pipeline. No production writes or novel answer edits.

Builds source-verified review packets and reproduces already-proven corrections.
Uncertain differences remain held by the existing independent release gates.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VERSION = 1
MAX_PDF_BYTES = 15 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_bytes(encoded(value)); os.replace(temp, path)


def inputs(root=ROOT):
    paths = set(root.glob('scripts/*.py')) | set(root.glob('audit/official*.json'))
    paths |= set((root/'cdn/question-shards').glob('*.json'))
    paths |= set((root/'official-figures').glob('*.png')) | set((root/'cdn/official-figures').glob('*.png'))
    paths |= {root/p for p in ('index.html','cdn/index.html','auto/essays_auto.json','data/official_exam_readonly.lock.json','data/moex_source_subjects.v1.json','data/moex_answer_sources.v1.json','data/official_figure_assets.v1.json')}
    fingerprints = {str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted(paths)}
    return digest(encoded({'version':VERSION,'inputs':fingerprints})), fingerprints


def external_output(out):
    out = Path(out).resolve()
    if out==ROOT or ROOT in out.parents:
        raise ValueError('output must be outside checkout')
    out.mkdir(parents=True, exist_ok=True)
    return out


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname!='wwwq.moex.gov.tw' or p.port not in (None,443) or p.username or p.password or p.path!='/exam/wHandExamQandA_File.ashx':
        raise ValueError('unapproved official PDF URL')


def source_pdf(source, work, evidence_dir=None, allow_download=False):
    validate_url(source['url'])
    sha=source['pdf_sha256']; target=work/'pdfs'/(sha+'.pdf')
    if target.exists():
        raw=target.read_bytes()
    elif evidence_dir:
        name=f"{source['exam_code']}-{source['c']}-{source['s']}.pdf"
        raw=(Path(evidence_dir)/name).read_bytes()
    elif allow_download:
        req=urllib.request.Request(source['url'],headers={'User-Agent':'SWSI-official-pdf-batch-audit/1.0'})
        with urllib.request.build_opener(OfficialRedirect()).open(req,timeout=30) as response:
            validate_url(response.geturl()); raw=response.read(MAX_PDF_BYTES+1)
    else:
        raise ValueError('official PDF unavailable offline; supply --evidence-dir or --download')
    if len(raw)>MAX_PDF_BYTES or not raw.startswith(b'%PDF-') or digest(raw)!=sha:
        raise ValueError('official PDF hash/content mismatch')
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True); temp=target.with_suffix('.tmp');temp.write_bytes(raw);os.replace(temp,target)
    text=subprocess.run(['pdftotext','-layout',str(target),'-'],check=True,capture_output=True,timeout=30).stdout.decode('utf-8')
    return target, text


def expected_packet(row, current):
    return {'id':row['id'],'kind':row['kind'],'priority':row['priority'],'baseline_difference':row,
            'current_official_record':current,'status':'requires_source_review','human_approval':False,'release_approval':False,'automatic_core_edit':False}


def cached_packet(path, expected, expected_sha):
    if not path.is_file() or digest(path.read_bytes())!=expected_sha:
        return False
    packet=json.loads(path.read_text())
    pdf=path.parents[1]/packet.get('pdf_file','missing')
    return (all(packet.get(k)==v for k,v in expected.items())
            and packet.get('pdf_file')=='pdfs/'+expected['baseline_difference']['pdf_sha256']+'.pdf'
            and pdf.is_file() and digest(pdf.read_bytes())==packet.get('pdf_sha256')
            and digest(packet.get('pdf_layout_text','').encode())==packet.get('pdf_layout_sha256'))


def checks(work):
    commands=[['official_exam_readonly_guard.py'],['official_combined_candidate_guard_selftest.py'],
              ['official_mcq_corrections_smoke.py'],['official_essay_correction_smoke.py'],
              ['official_pdf_stem_repairs_selftest.py'],['official_pdf_review_dispositions_selftest.py'],
              ['official_pdf_text_release_gate.py','--selftest'],
              ['full_corpus_qa.py','--out',str(work/'full-corpus.json'),'--fail-on','blocked']]
    results=[]
    for number,args in enumerate(commands):
        command=[sys.executable,str(ROOT/'scripts'/args[0]),*args[1:]]
        run=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180)
        log=work/f'check-{number:02}.log';log.write_bytes(run.stdout+run.stderr)
        result={'command':args,'returncode':run.returncode,'log':log.name,'sha256':digest(log.read_bytes())};results.append(result)
        atomic(work/'checks.json',results)
        if run.returncode:
            raise RuntimeError(f'failed required check: {args[0]}; see {log}')
    return results


def execute(out, batch_size=25, max_batches=0, evidence_dir=None, download=False, verify=True, reproduce=True, max_sources=0):
    if not 1<=batch_size<=50 or max_batches<0 or max_sources<0:
        raise ValueError('batch size must be1..50 and max batches nonnegative')
    out=external_output(out)
    with (out/'pipeline.lock').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        latest=out/'latest.json'
        if latest.exists():latest.unlink()
        key,fingerprints=inputs();work=out/key;work.mkdir(exist_ok=True)
        state_path=work/'checkpoint.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {'schema_version':VERSION,'input_fingerprint':key,'packets':{}}
        if state.get('schema_version')!=VERSION or state.get('input_fingerprint')!=key:
            raise ValueError('checkpoint input mismatch')
        atomic(work/'inputs.json',fingerprints)
        # Always rerun required checks: cached progress cannot bypass QA.
        if verify:checks(work)
        from official_pdf_review_queue import build
        queue=build();atomic(work/'queue.json',queue)
        from official_exam_readonly_guard import collect_essays
        manifest=json.loads((ROOT/'cdn/question-shards/manifest.json').read_text())
        current={q['id']:q for e in manifest['shards'] for q in json.loads((ROOT/'cdn/question-shards'/e['file']).read_text())['questions']}
        current.update(collect_essays())
        registry=json.loads((ROOT/'data/moex_source_subjects.v1.json').read_text())['records']
        sources={r['pdf_sha256']:r for r in registry}
        # Group by PDF after priority: fetch/extract each source once per run.
        rows=sorted(queue['rows'],key=lambda r:(r['priority'],r['pdf_sha256'],r['id']))
        reused=processed=failed=0; source_cache={};errors={}; batches=0
        for offset in range(0,len(rows),batch_size):
            chunk=rows[offset:offset+batch_size]
            todo=[]
            for row in chunk:
                filename='packets/'+digest(row['id'].encode())+'.json';path=work/filename
                expected=expected_packet(row,current[row['id']])
                if cached_packet(path,expected,state['packets'].get(row['id'],'')):
                    reused+=1
                else:
                    state['packets'].pop(row['id'],None)
                    todo.append((row,filename,path,expected))
            if not todo:continue
            if max_batches and batches>=max_batches:continue
            batches+=1
            for row,filename,path,packet in todo:
                try:
                    sha=row['pdf_sha256']
                    if sha in errors:raise RuntimeError(errors[sha])
                    if sha not in source_cache:
                        if max_sources and len(source_cache)+len(errors)>=max_sources:
                            continue
                        try:source_cache[sha]=source_pdf(sources[sha],work,evidence_dir,download)
                        except Exception as error:errors[sha]=str(error);raise
                    pdf,text=source_cache[sha]
                    # Extraction is diagnostic; font/layout equivalence never clears a review.
                    packet.update(pdf_file=str(pdf.relative_to(work)),pdf_sha256=sha,pdf_layout_text=text,
                                  pdf_layout_sha256=digest(text.encode()),official_source_url=sources[sha]['url'])
                    atomic(path,packet);state['packets'][row['id']]=digest(path.read_bytes());processed+=1
                    state.get('errors',{}).pop(row['id'],None)
                except Exception as error:
                    state.setdefault('errors',{})[row['id']]=str(error);failed+=1
                # Durable per-record checkpoint: interruption never loses a whole batch.
                atomic(state_path,state)
        atomic(state_path,state)
        candidate_status='not_requested'
        if reproduce:
            from official_pdf_stem_repairs import reproduce as build_candidate, load_proof
            candidate=work/'verified-candidate';proof=load_proof()
            if candidate.exists():
                if any(not (candidate/p).is_file() or digest((candidate/p).read_bytes())!=sha for p,sha in proof['output_sha256'].items()):
                    raise ValueError('cached verified candidate drift')
            else:build_candidate(candidate)
            candidate_status='43_existing_verified_corrections_reproduced'
        final_key,_=inputs()
        if final_key!=key:raise ValueError('source inputs changed during run; checkpoint cannot be published')
        total=len(rows); completed=len(set(state['packets']) & {r['id'] for r in rows})
        summary={'schema_version':VERSION,'input_fingerprint':key,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 'source_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
                 'queue_total':total,'prepared_packets':completed,'new_packets':processed,'reused_packets':reused,'failed_records_this_run':failed,
                 'not_yet_prepared':total-completed,'batches_executed':batches,'candidate':candidate_status,
                 'release_status':'NO-GO','unresolved_official_reviews':total,'human_approval':False,'official_core_modified':False,
                 'production_write':False,'backup_operation':False,'work_directory':str(work)}
        atomic(work/'summary.json',summary);atomic(out/'latest.json',summary)
        return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path);parser.add_argument('--evidence-dir',type=Path)
    parser.add_argument('--download',action='store_true');parser.add_argument('--batch-size',type=int,default=25);parser.add_argument('--max-batches',type=int,default=0);parser.add_argument('--fingerprint',action='store_true');parser.add_argument('--max-sources',type=int,default=0)
    args=parser.parse_args()
    if args.fingerprint:print(inputs()[0]);return 0
    if not args.out:parser.error('--out required')
    result=execute(args.out,args.batch_size,args.max_batches,args.evidence_dir,args.download,max_sources=args.max_sources)
    print(json.dumps(result,ensure_ascii=False));return 1 if result['failed_records_this_run'] else 0


if __name__=='__main__':raise SystemExit(main())
