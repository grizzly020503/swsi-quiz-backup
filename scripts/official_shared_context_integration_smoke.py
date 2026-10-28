#!/usr/bin/env python3
"""Read-only MOEX 13-question integrated core+manifest regression."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
J=lambda p:json.loads((P/p).read_text(encoding="utf8"))
H=lambda b:hashlib.sha256(b).hexdigest()
K=("id","subject","year","round","qno","question","opt_a","opt_b","opt_c","opt_d")
def row_hash(q):
 return H(json.dumps({k:q.get(k) for k in K},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8"))
def main():
 m=J("cdn/question-shards/manifest.json");lock=J("data/official_exam_readonly.lock.json")["mcq"]
 proof=J("audit/official_shared_context_13_integration_20261029.json")
 assert m["total_questions"]==4800 and m["shard_count"]==24 and len(lock)==4800
 assert sum(x["bytes"] for x in m["shards"])==m["total_uncompressed_bytes"]==proof["manifest_total_bytes"]
 qs={}
 for s in m["shards"]:
  body=(P/"cdn/question-shards"/s["file"]).read_bytes()
  assert len(body)==s["bytes"] and H(body)==s["sha256"],s["file"]
  entries=json.loads(body)["questions"];assert len(entries)==200
  for q in entries:
   assert q["id"] not in qs and row_hash(q)==lock[q["id"]],q["id"]
   qs[q["id"]]=q
 assert len(qs)==4800 and len(set(proof["changed_ids"]))==13
 for path in proof["source_proofs"]:
  doc=J(path)
  for x in doc["changes"]:
   q=qs[x["id"]];assert x["id"] in proof["changed_ids"]
   assert row_hash(q)==x["new_lock_sha256"] and q["answer"]==x["answer"]
   assert q.get("accepted_answers")==x["accepted_answers"] and q["grading_mode"]==x["grading_mode"]
   for k,d in x["fields"].items(): assert q[k]==d["after"]!=d["before"],x["id"]
 for n in ("R-105-2-12","R-105-2-20","R-107-2-04"):
  assert "情況：" not in qs[n]["opt_d"],n
 for n in proof["changed_ids"]:
  if n not in ("R-105-2-12","R-105-2-20","R-107-2-04"):assert qs[n]["question"].startswith("情況："),n
 assert not proof["merge_approval"] and not proof["backup_modified"] and not proof["production_mutation"]
 print("MOEX 13-question integration PASS: 4800 full-corpus lock + 24 manifest hashes")
if __name__=="__main__":main()
