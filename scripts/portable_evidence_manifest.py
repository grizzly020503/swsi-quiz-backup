#!/usr/bin/env python3
from __future__ import annotations
import argparse, fnmatch, glob, hashlib, json, sys
from pathlib import Path

POLICY_PATH=Path("data/portable_evidence_policy.v1.json")

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def load_policy(root: Path) -> dict:
    p=root/POLICY_PATH
    data=json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version")!=1: raise ValueError("unsupported portable evidence policy schema")
    classes=data.get("storage_classes")
    if not isinstance(classes,dict) or not classes: raise ValueError("storage_classes must be a non-empty object")
    for name,body in classes.items():
        if name not in {"long_term_public_knowledge","rebuild_contract","short_term_diagnostic"}:
            raise ValueError(f"unsupported storage class: {name}")
        if not isinstance(body.get("rules"),list): raise ValueError(f"{name} rules must be a list")
    for row in data.get("private_external",[]):
        if row.get("payload_must_not_be_in_repo") is not True:
            raise ValueError("private_external payloads must remain outside the repo")
    return data

def excluded(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel,p) or Path(rel).match(p) for p in patterns)

def matches(root: Path, pattern: str) -> list[Path]:
    found=[]
    for raw in glob.glob(str(root/pattern),recursive=True):
        p=Path(raw)
        if p.is_file(): found.append(p)
    return sorted(set(found), key=lambda p:p.relative_to(root).as_posix())

def build(root: Path) -> dict:
    policy=load_policy(root)
    excludes=policy.get("private_exclude_globs",[])
    assigned={}
    entries=[]
    class_counts={}
    for storage_class,body in policy["storage_classes"].items():
        count=0
        retention=body.get("retention")
        for rule in body["rules"]:
            pattern=rule["pattern"]; required=bool(rule.get("required"))
            candidates=[]
            for p in matches(root,pattern):
                rel=p.relative_to(root).as_posix()
                if excluded(rel,excludes): continue
                candidates.append((p,rel))
            if required and not candidates:
                raise ValueError(f"required pattern matched no non-private files: {pattern}")
            for p,rel in candidates:
                if rel in assigned:
                    raise ValueError(f"duplicate path assignment: {rel} -> {assigned[rel]} and {storage_class}")
                assigned[rel]=storage_class
                entries.append({
                    "path":rel,
                    "size":p.stat().st_size,
                    "sha256":sha256(p),
                    "storage_class":storage_class,
                    "required":required,
                    "provider_independent":bool(rule.get("provider_independent")),
                    "retention":retention,
                })
                count+=1
        class_counts[storage_class]=count
    entries.sort(key=lambda x:x["path"])
    return {
        "schema_version":1,
        "generator":"scripts/portable_evidence_manifest.py",
        "entry_count":len(entries),
        "class_counts":dict(sorted(class_counts.items())),
        "entries":entries,
        "private_external":[
            {"name":x["name"],"payload_must_not_be_in_repo":True,"retention":x["retention"]}
            for x in sorted(policy.get("private_external",[]),key=lambda x:x["name"])
        ],
    }

def main():
    ap=argparse.ArgumentParser(description="Deterministic zero-network portable evidence manifest")
    ap.add_argument("--root",default=".")
    ap.add_argument("--output")
    ap.add_argument("--check-determinism",action="store_true")
    a=ap.parse_args(); root=Path(a.root).resolve()
    first=build(root)
    if a.check_determinism and first!=build(root):
        print("portable evidence manifest is not deterministic",file=sys.stderr); return 2
    out=json.dumps(first,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if a.output: Path(a.output).write_text(out,encoding="utf-8")
    else: sys.stdout.write(out)
    return 0
if __name__=="__main__": raise SystemExit(main())
