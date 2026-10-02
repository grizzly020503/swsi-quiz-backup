#!/usr/bin/env python3
import importlib.util, json, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("pem",ROOT/"scripts/portable_evidence_manifest.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def policy(rules):
    return {
        "schema_version":1,
        "private_exclude_globs":[".env","**/.env","private/**"],
        "storage_classes":{
            "long_term_public_knowledge":{"retention":"long","rules":rules},
            "rebuild_contract":{"retention":"long","rules":[{"pattern":"contract/*.sql","required":True,"provider_independent":True}]},
            "short_term_diagnostic":{"retention":"14d","rules":[{"pattern":"tmp/*.log","required":False,"provider_independent":True}]}
        },
        "private_external":[{"name":"auth_users","payload_must_not_be_in_repo":True,"retention":"privacy"}]
    }

with tempfile.TemporaryDirectory() as td:
    r=Path(td); (r/"knowledge").mkdir(); (r/"contract").mkdir(); (r/"tmp").mkdir()
    (r/"knowledge/questions.json").write_text('{"q":1}', encoding="utf-8")
    (r/"contract/schema.sql").write_text("create table x(id int);", encoding="utf-8")
    (r/"tmp/run.log").write_text("diagnostic", encoding="utf-8")
    (r/".env").write_text("TOPSECRET", encoding="utf-8")
    p=r/"data/portable_evidence_policy.v1.json"; p.parent.mkdir()
    p.write_text(json.dumps(policy([
        {"pattern":"knowledge/*.json","required":True,"provider_independent":True},
        {"pattern":".env","required":False,"provider_independent":False}
    ])), encoding="utf-8")
    a=m.build(r); b=m.build(r); assert a==b
    out=json.dumps(a)
    assert "TOPSECRET" not in out and ".env" not in {x["path"] for x in a["entries"]}
    assert {x["storage_class"] for x in a["entries"]}=={"long_term_public_knowledge","rebuild_contract","short_term_diagnostic"}
    assert all(set(x)=={"path","size","sha256","storage_class","required","provider_independent","retention"} for x in a["entries"])

    p.write_text(json.dumps(policy([{"pattern":"missing/*.json","required":True,"provider_independent":True}])), encoding="utf-8")
    try: m.build(r); raise AssertionError("missing required rule did not fail")
    except ValueError as e: assert "required pattern" in str(e)

    bad=policy([
        {"pattern":"knowledge/*.json","required":True,"provider_independent":True},
        {"pattern":"knowledge/questions.json","required":True,"provider_independent":True}
    ])
    p.write_text(json.dumps(bad), encoding="utf-8")
    try: m.build(r); raise AssertionError("duplicate assignment did not fail")
    except ValueError as e: assert "duplicate path assignment" in str(e)

print("PORTABLE EVIDENCE MANIFEST SELFTEST OK")
