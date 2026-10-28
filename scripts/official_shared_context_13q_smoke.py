#!/usr/bin/env python3
"""Read-only MOEX 13-question and 4,800-core integration regression."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()
core_fields=("id","subject","year","round","qno","question","opt_a","opt_b","opt_c","opt_d")
def core(row):
 return sha(json.dumps({k:row.get(k) for k in core_fields},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
def main():
 audit=json.loads((ROOT/"audit/official_shared_context_13q_integration_20261028.json").read_text(encoding="utf-8"))
 manifest=json.loads((ROOT/"cdn/question-shards/manifest.json").read_text(encoding="utf-8"))
 lock=json.loads((ROOT/"data/official_exam_readonly.lock.json").read_text(encoding="utf-8"))
 assert audit["status"]=="DRAFT_NO_GO_NOT_DEPLOYED" and not audit["release_approved"]
 assert len(audit["changes"])==13 and manifest["total_questions"]==4800 and len(manifest["shards"])==24
 assert len(lock["mcq"])==4800
 assert sum(e["bytes"] for e in manifest["shards"])==manifest["total_uncompressed_bytes"]
 records={}
 for entry in manifest["shards"]:
  raw=(ROOT/"cdn/question-shards"/entry["file"]).read_bytes()
  assert sha(raw)==entry["sha256"] and len(raw)==entry["bytes"],entry["file"]
  questions=json.loads(raw)["questions"]
  assert len(questions)==entry["question_count"]==200
  for row in questions:
   assert row["id"] not in records
   records[row["id"]]=row
   assert core(row)==lock["mcq"][row["id"]],row["id"]
 assert len(records)==4800
 for change in audit["changes"]:
  row=records[change["id"]]
  assert core(row)==change["new_lock_sha256"]
  assert row["answer"]==change["answer"] and row.get("accepted_answers")==change["accepted_answers"]
  assert row["grading_mode"]==change["grading_mode"]
  for field,d in change["fields"].items():
   assert d["before"]!=d["after"]==row[field]
 for ident in ("R-105-2-12","R-105-2-20","R-107-2-04"):
  assert "情況：" not in records[ident]["opt_d"]
 for session,nums in (("105-2",(13,14,15,16,21,22)),("107-2",(5,6,7,8))):
  for n in nums:assert records[f"R-{session}-{n:02d}"]["question"].startswith("情況：")
 print("MOEX INTEGRATED 13-Q QA PASS (4800 core locks / 24 shards)")
if __name__=="__main__":main()
