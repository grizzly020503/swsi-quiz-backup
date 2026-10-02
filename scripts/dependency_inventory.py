#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from collections import defaultdict
from pathlib import Path

POLICY = Path("data/dependency_lifecycle_policy.v1.json")
WF = Path(".github/workflows")
CODE_EXT = {".ts", ".tsx", ".js", ".mjs", ".cjs"}
MANIFESTS = {
    "package.json","package-lock.json","npm-shrinkwrap.json","yarn.lock","pnpm-lock.yaml",
    "pyproject.toml","poetry.lock","Pipfile","Pipfile.lock","requirements.txt","deno.json","deno.jsonc",
}
USES = re.compile(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)")
PY = re.compile(r"(?m)^\s*python-version:\s*['\"]?([^'\"\s#]+)")
NODE = re.compile(r"(?m)^\s*node-version:\s*['\"]?([^'\"\s#]+)")
NPM = re.compile(r"(?<![\w./-])((?:@[\w.-]+/)?[\w.-]+)@((?:\d+\.){1,2}\d+(?:[-+][\w.-]+)?|\d+|latest|next)(?![\w.-])")
IMPORT = re.compile(r'''(?:from\s*|import\s*\(\s*|import\s+)(['\"])(https://[^'\"]+|jsr:[^'\"]+|npm:[^'\"]+)\1''')
SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
VER = re.compile(r"^[v~^]?\d+(?:\.\d+){0,2}(?:[-+][\w.-]+)?$")

def text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def pin(ref: str) -> str:
    if SHA40.fullmatch(ref): return "commit_sha"
    if ref in {"main","master","latest","next","stable","canary","beta"}: return "floating"
    if ref.startswith(("refs/","${{")): return "dynamic"
    if VER.fullmatch(ref):
        n = len(ref.lstrip("v~^").split("."))
        return ("major_only","minor_pin","exact_version")[min(n,3)-1]
    return "other"

def major(ref: str):
    m = re.match(r"^[v~^]?(\d+)", ref)
    return m.group(1) if m else None

def rid(kind, name, ref):
    return hashlib.sha256(f"{kind}\0{name}\0{ref}".encode()).hexdigest()[:20]

def load_policy(root: Path):
    p = root / POLICY
    data = json.loads(text(p))
    if data.get("schema_version") != 1: raise ValueError("unsupported policy schema")
    for kind in ("github_action","python_runtime","node_runtime","npm_cli","remote_import","manifest"):
        row = data.get("kind_defaults",{}).get(kind)
        if not isinstance(row,dict): raise ValueError(f"policy missing {kind}")
        for key in ("criticality","core_or_enhancement","fallback","paid_required","upgrade_gate"):
            if key not in row: raise ValueError(f"policy {kind} missing {key}")
    return data

def add(rows, policy, kind, name, ref, loc, **extra):
    rows.append({
        "id": rid(kind,name,ref), "kind": kind, "name": name, "ref": ref,
        "pin_kind": pin(ref), "location": loc,
        **policy["kind_defaults"][kind],
        "owner_role": "repository_maintainer",
        "replacement_path": "review_and_validate_supported_alternative_before_change",
        "last_verified_date": None, **extra,
    })

def remote(spec: str):
    if spec.startswith("jsr:"):
        body=spec[4:]; i=body.rfind("@")
        return (body[:i], body[i+1:].split("/",1)[0], "jsr") if i>0 else (body.split("/",1)[0],"floating","jsr")
    if spec.startswith("npm:"):
        body=spec[4:]; i=body.rfind("@")
        return (body[:i], body[i+1:].split("/",1)[0], "npm") if i>0 else (body.split("/",1)[0],"floating","npm")
    m=re.match(r"https://([^/]+)/(.+)",spec); host,rest=m.group(1),m.group(2)
    if host=="esm.sh":
        parts=rest.split("/"); pkg="/".join(parts[:2]) if rest.startswith("@") else parts[0]
        i=pkg.rfind("@"); return (pkg[:i],pkg[i+1:],"esm.sh") if i>0 else (pkg,"floating","esm.sh")
    if host=="deno.land":
        first=rest.split("/",1)[0]; m=re.fullmatch(r"std@(.+)",first)
        return ("deno_std",m.group(1),"deno.land") if m else (first,"floating","deno.land")
    return (f"{host}/{rest.split('/',1)[0]}","floating",host)

def build(root: Path):
    policy=load_policy(root); rows=[]
    wf=root/WF
    if wf.exists():
        for p in sorted(x for x in wf.rglob("*") if x.is_file() and x.suffix in {".yml",".yaml"}):
            rel=p.relative_to(root).as_posix(); s=text(p)
            for spec in USES.findall(s):
                if "@" in spec and not spec.startswith("./"):
                    name,ref=spec.rsplit("@",1); add(rows,policy,"github_action",name,ref,rel)
            for ref in PY.findall(s): add(rows,policy,"python_runtime","python",ref,rel)
            for ref in NODE.findall(s): add(rows,policy,"node_runtime","node",ref,rel)
            for pkg,ref in NPM.findall(s): add(rows,policy,"npm_cli",pkg,ref,rel)
    froot=root/"supabase/functions"
    if froot.exists():
        for p in sorted(x for x in froot.rglob("*") if x.is_file() and x.suffix in CODE_EXT):
            rel=p.relative_to(root).as_posix()
            for _,spec in IMPORT.findall(text(p)):
                name,ref,source=remote(spec); add(rows,policy,"remote_import",name,ref,rel,source=source,spec=spec)
    skip={".git","node_modules",".venv","venv","dist","build"}
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        if any(part in skip for part in p.parts): continue
        if p.name not in MANIFESTS and not p.name.startswith("requirements-"): continue
        rel=p.relative_to(root).as_posix(); h=hashlib.sha256(p.read_bytes()).hexdigest()
        add(rows,policy,"manifest",p.name,h,rel,sha256=h)
    grouped={}
    for r in rows:
        k=(r["kind"],r["name"],r["ref"],r.get("source"),r.get("spec"))
        if k not in grouped:
            grouped[k]={x:y for x,y in r.items() if x!="location"}; grouped[k]["locations"]=[]
        grouped[k]["locations"].append(r["location"])
    records=[]
    for r in grouped.values():
        r["locations"]=sorted(set(r["locations"])); records.append(r)
    records.sort(key=lambda r:(r["kind"],r["name"],r["ref"],r["id"]))
    by=defaultdict(list)
    for r in records:
        if r["kind"]!="manifest": by[(r["kind"],r["name"])].append(r)
    drift=[]
    for (kind,name),rs in sorted(by.items()):
        refs=sorted({r["ref"] for r in rs})
        if len(refs)<2: continue
        majors=sorted({m for ref in refs if (m:=major(ref))})
        drift.append({
            "kind":kind,"name":name,"refs":refs,"majors":majors,
            "pin_kinds":sorted({r["pin_kind"] for r in rs}),
            "severity":"high" if len(majors)>1 and kind in {"github_action","python_runtime","node_runtime"} else "medium",
            "action":"review_only_do_not_auto_upgrade",
        })
    return {"schema_version":1,"generator":"scripts/dependency_inventory.py","root":".",
            "records":records,"drift_findings":drift,"policy":dict(policy.get("global",{}))}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=".")
    ap.add_argument("--output")
    ap.add_argument("--check-determinism",action="store_true")
    a=ap.parse_args(); root=Path(a.root).resolve(); first=build(root)
    if a.check_determinism and first!=build(root):
        print("dependency inventory is not deterministic",file=sys.stderr); return 2
    out=json.dumps(first,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if a.output: Path(a.output).write_text(out,encoding="utf-8")
    else: sys.stdout.write(out)
    return 0
if __name__=="__main__": raise SystemExit(main())
