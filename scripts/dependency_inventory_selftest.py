#!/usr/bin/env python3
import importlib.util, json, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("di",ROOT/"scripts/dependency_inventory.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as td:
    r=Path(td); w=r/".github/workflows"; w.mkdir(parents=True)
    (w/"a.yml").write_text("""jobs:
  a:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npx playwright@1.55.0 test
""", encoding="utf-8")
    (w/"b.yml").write_text("""jobs:
  b:
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '22.13.0'
""", encoding="utf-8")
    f=r/"supabase/functions/demo"; f.mkdir(parents=True)
    (f/"index.ts").write_text('import { serve } from "https://deno.land/std@0.224.0/http/server.ts";\nimport x from "https://esm.sh/@supabase/supabase-js@2.45.4";\nimport y from "jsr:@std/assert@1.0.6";', encoding="utf-8")
    (r/"package.json").write_text("{}", encoding="utf-8")
    p=r/"data/dependency_lifecycle_policy.v1.json"; p.parent.mkdir()
    p.write_text((ROOT/"data/dependency_lifecycle_policy.v1.json").read_text(encoding="utf-8"), encoding="utf-8")

    a=m.build(r); b=m.build(r); assert a==b
    rec=a["records"]; d={(x["kind"],x["name"]):x for x in a["drift_findings"]}
    assert any(x["kind"]=="npm_cli" and x["name"]=="playwright" and x["ref"]=="1.55.0" for x in rec)
    assert any(x.get("source")=="esm.sh" and x["name"]=="@supabase/supabase-js" and x["ref"]=="2.45.4" for x in rec)
    assert any(x.get("source")=="jsr" and x["name"]=="@std/assert" and x["ref"]=="1.0.6" for x in rec)
    assert any(x.get("source")=="deno.land" and x["name"]=="deno_std" and x["ref"]=="0.224.0" for x in rec)
    assert d[("github_action","actions/checkout")]["majors"]==["3","4"]
    assert ("python_runtime","python") in d and ("node_runtime","node") in d
    assert a["policy"]["auto_upgrade"] is False
    assert all("upgrade_gate" in x and "paid_required" in x for x in rec)

print("DEPENDENCY INVENTORY SELFTEST OK")
