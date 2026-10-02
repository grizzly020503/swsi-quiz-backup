#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, shlex, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

ACTION_RE = re.compile(r'^\s*(?:-\s*)?uses:\s*([^\s#]+)', re.M)
PYTHON_RE = re.compile(r"python-version:\s*['\"]?([^'\"\s#]+)")
NODE_RE = re.compile(r"node-version:\s*['\"]?([^'\"\s#]+)")
IMAGE_RE = re.compile(r'^\s*image:\s*[\'\"]?([^\'\"\s#]+)', re.M)
NPM_PIN_RE = re.compile(r'\b(playwright|axe-core|netlify-cli|wrangler)@([A-Za-z0-9._-]+)')
PIP_INSTALL_RE = re.compile(r'\b(?:python(?:3)?\s+-m\s+pip|pip(?:3)?)\s+install\s+([^\n]+)')
REMOTE_IMPORT_RE = re.compile(r'''from\s+["'](https://[^"']+|jsr:[^"']+)["']|import\s+["'](https://[^"']+|jsr:[^"']+)["']''')
MODEL_RE = re.compile(r'''(?:DRAFT_MODEL|AUDIT_MODEL|MODEL|MODEL_NAME)\s*=\s*["']([^"']+)["']''')
IGNORED_PIP_FLAGS_WITH_VALUE = {'--index-url','--extra-index-url','--find-links','-f','--target','-t','--prefix','--root','--cache-dir','--timeout','--retries'}
IGNORED_PIP_FLAGS = {'--disable-pip-version-check','--no-deps','--no-cache-dir','--upgrade','-U','--quiet','-q','--pre'}

def stable_id(kind: str, name: str) -> str:
    return f"dep1:{hashlib.sha256((kind + chr(10) + name).encode()).hexdigest()[:20]}"

def pin_strategy(value: str) -> str:
    v = str(value or '').strip()
    if re.fullmatch(r'[0-9a-fA-F]{40}', v): return 'exact_commit'
    if re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?', v): return 'exact_version'
    if re.fullmatch(r'v?\d+\.\d+', v): return 'minor_line'
    if re.fullmatch(r'v?\d+', v): return 'major_line'
    if v in {'latest','stable','main','master'}: return 'floating'
    return 'other'

def action_parts(ref: str) -> tuple[str,str]:
    return ref.rsplit('@',1) if '@' in ref else (ref,'')

def remote_identity(spec: str) -> tuple[str,str,str]:
    if spec.startswith('jsr:'):
        body=spec[4:]
        return (*body.rsplit('@',1), 'jsr') if '@' in body else (body,'','jsr')
    m=re.match(r'https://([^/]+)/(.+)', spec)
    if not m: return spec,'','https'
    host,path=m.groups(); path=path.split('?',1)[0]
    if host=='esm.sh':
        mm=re.match(r'(@[^/]+/[^@/]+)@([^/]+)', path) if path.startswith('@') else re.match(r'([^@/]+)@([^/]+)', path)
        if mm: return mm.group(1),mm.group(2),'esm.sh'
    return path,'',host

def add(records: list[dict[str,Any]], kind: str, name: str, version: str, source: str, path: str, pin: str|None=None, extra: dict[str,Any]|None=None):
    row={'id':stable_id(kind,name),'kind':kind,'name':name,'version':version,'pin_strategy':pin or pin_strategy(version),'source':source,'path':path}
    if extra: row.update(extra)
    records.append(row)

def parse_pip_packages(line: str) -> list[tuple[str,str]]:
    try: tokens=shlex.split(line)
    except ValueError: tokens=line.split()
    out=[]; i=0
    while i < len(tokens):
        tok=tokens[i]
        if tok in IGNORED_PIP_FLAGS_WITH_VALUE: i+=2; continue
        if tok in IGNORED_PIP_FLAGS or tok.startswith('-'): i+=1; continue
        if tok.startswith(('.', '/', 'git+', 'http://', 'https://')): i+=1; continue
        name=tok; version=''
        if '==' in tok: name,version=tok.split('==',1)
        elif '~=' in tok: name,v=tok.split('~=',1); version='~='+v
        elif '>=' in tok: name,v=tok.split('>=',1); version='>='+v
        if re.fullmatch(r'[A-Za-z0-9_.-]+', name): out.append((name.lower(),version))
        i+=1
    return out

def scan(root: Path) -> dict[str,Any]:
    records=[]; files_scanned=0
    wf=root/'.github'/'workflows'
    if wf.is_dir():
        for path in sorted(list(wf.glob('*.yml'))+list(wf.glob('*.yaml'))):
            files_scanned+=1; text=path.read_text(encoding='utf-8',errors='replace'); rel=path.relative_to(root).as_posix()
            for ref in ACTION_RE.findall(text):
                name,version=action_parts(ref); add(records,'github_action',name,version,'workflow',rel)
            for version in PYTHON_RE.findall(text): add(records,'runtime','python',version,'workflow',rel)
            for version in NODE_RE.findall(text): add(records,'runtime','node',version,'workflow',rel)
            for image in IMAGE_RE.findall(text):
                name,version=image.rsplit(':',1) if ':' in image else (image,''); add(records,'container_image',name,version,'workflow',rel)
            for name,version in NPM_PIN_RE.findall(text): add(records,'npm_cli',name,version,'workflow_command',rel)
            for tail in PIP_INSTALL_RE.findall(text):
                for name,version in parse_pip_packages(tail):
                    pin='exact_version' if version and not version.startswith(('>=','~=')) else ('range' if version else 'unpinned')
                    add(records,'python_package',name,version,'workflow_command',rel,pin=pin)
    for base in (root/'supabase'/'functions', root/'workers', root/'scripts'):
        if not base.exists(): continue
        for path in sorted(base.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in {'.ts','.js','.mjs','.cjs'}: continue
            files_scanned+=1; text=path.read_text(encoding='utf-8',errors='replace'); rel=path.relative_to(root).as_posix()
            for m in REMOTE_IMPORT_RE.finditer(text):
                spec=m.group(1) or m.group(2); name,version,remote=remote_identity(spec); add(records,'remote_import',name,version,remote,rel,extra={'specifier':spec})
            for model in MODEL_RE.findall(text): add(records,'ai_model',model,'','source_constant',rel,pin='provider_model_id')
    candidates=['requirements.txt','requirements-dev.txt','pyproject.toml','package.json','package-lock.json','pnpm-lock.yaml','yarn.lock','deno.json','deno.jsonc','import_map.json']
    manifests=[rel for rel in candidates if (root/rel).is_file()]
    records.sort(key=lambda r:(r['kind'],r['name'],r['version'],r['source'],r['path']))
    groups=defaultdict(list)
    for row in records: groups[(row['kind'],row['name'])].append(row)
    drift=[]
    for (kind,name),rows in sorted(groups.items()):
        versions=sorted({r['version'] for r in rows if r['version']}); sources=sorted({r['source'] for r in rows}); pins=sorted({r['pin_strategy'] for r in rows}); reasons=[]
        if len(versions)>1: reasons.append('multiple_versions')
        if kind=='remote_import' and len(sources)>1: reasons.append('multiple_remote_sources')
        if any(p in {'floating','other','unpinned','range'} for p in pins): reasons.append('non_exact_pin')
        if reasons: drift.append({'id':stable_id(kind,name),'kind':kind,'name':name,'reasons':reasons,'versions':versions,'sources':sources,'pin_strategies':pins,'occurrences':len(rows)})
    return {'schema_version':1,'files_scanned':files_scanned,'manifest_files_present':manifests,'records':records,'drift':drift,'summary':{'records':len(records),'unique_dependencies':len(groups),'drift_groups':len(drift)}}

def self_test() -> dict[str,Any]:
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); wf=root/'.github'/'workflows'; wf.mkdir(parents=True)
        (wf/'a.yml').write_text("""steps:\n- uses: actions/checkout@v4\n- uses: actions/setup-python@v5\n  with:\n    python-version: '3.11'\n- run: npm install --no-save playwright@1.55.0\n- run: python -m pip install requests pypdf==5.0.0\n""",encoding='utf-8')
        (wf/'b.yml').write_text("""steps:\n- uses: actions/checkout@v7\n- uses: actions/setup-python@v7\n  with:\n    python-version: '3.12'\n""",encoding='utf-8')
        fn=root/'supabase/functions/demo'; fn.mkdir(parents=True); (fn/'index.ts').write_text('import { createClient } from "jsr:@supabase/supabase-js@2";\nconst DRAFT_MODEL = "vendor/model-a";\n',encoding='utf-8')
        fn2=root/'supabase/functions/demo2'; fn2.mkdir(parents=True); (fn2/'index.ts').write_text('import { createClient } from "https://esm.sh/@supabase/supabase-js@2";\n',encoding='utf-8')
        out=scan(root); by={(d['kind'],d['name']):d for d in out['drift']}
        assert ('github_action','actions/checkout') in by and set(by[('github_action','actions/checkout')]['versions'])=={'v4','v7'}
        assert ('runtime','python') in by
        assert ('remote_import','@supabase/supabase-js') in by and 'multiple_remote_sources' in by[('remote_import','@supabase/supabase-js')]['reasons']
        assert any(r['kind']=='python_package' and r['name']=='requests' and r['pin_strategy']=='unpinned' for r in out['records'])
        assert any(r['name']=='pypdf' and r['version']=='5.0.0' for r in out['records'])
        assert any(r['kind']=='ai_model' and r['name']=='vendor/model-a' for r in out['records'])
        assert out==scan(root)
        return {'ok':True,'records':out['summary']['records'],'drift_groups':out['summary']['drift_groups'],'deterministic':True}

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path('.')); p.add_argument('--out',type=Path); p.add_argument('--self-test',action='store_true'); args=p.parse_args()
    payload=self_test() if args.self_test else scan(args.root.resolve()); text=json.dumps(payload,ensure_ascii=False,indent=2)+'\n'; print(text,end='')
    if args.out: args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(text,encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
