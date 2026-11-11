#!/usr/bin/env python3
"""Capture four original MOEX PDF pages as review-only PNG evidence in CI.

There is no production write, approval, or automated PDF visual signoff.
If official PDFs are unavailable or drift from the reviewed source SHA, fail
closed; this external-source diagnostic job does not gate other offline tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "audit/official_p0_option_order_candidate_20261110.json"
PAGES = {
    "SP104-2-37": {"question_page": 4, "answer_page": 9},
    "SP107-1-40": {"question_page": 4, "answer_page": 1},
}

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def retrieve(url: str, out: Path, expected_sha: str | None = None) -> dict:
    u = urlsplit(url)
    assert u.scheme == "https" and u.hostname == "wwwq.moex.gov.tw"
    assert u.path == "/exam/wHandExamQandA_File.ashx"
    params = parse_qs(u.query)
    assert params.get("t") in (["Q"],["A"])
    request = Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; SWSI-SourceReview/1.0)","Accept":"application/pdf"})
    with urlopen(request,timeout=45) as reply:
        assert reply.status == 200
        raw = reply.read(16*1024*1024+1)
    assert raw.startswith(b"%PDF-"), "source is not a PDF"
    assert 1000 < len(raw) < 16*1024*1024, "unexpected PDF length"
    digest=sha(raw)
    if expected_sha is not None:
        assert digest == expected_sha, f"official PDF changed: expected {expected_sha}, got {digest}"
    out.write_bytes(raw)
    return {"url":url,"pdf_sha256":digest,"pdf_bytes":len(raw)}

def render(pdf: Path, dest: Path, page: int) -> dict:
    assert 1 <= page <= 20
    # Rendering all PDF glyphs directly avoids interpretation by OCR or LLM.
    cmd=["pdftoppm","-f",str(page),"-l",str(page),"-singlefile",
         "-r","180","-png",str(pdf),str(dest.with_suffix(""))]
    subprocess.run(cmd,check=True,timeout=75,capture_output=True)
    img=dest.with_suffix(".png")
    raw=img.read_bytes()
    assert raw.startswith(b"\x89PNG\r\n\x1a\n"), "render did not produce PNG"
    assert len(raw)>10000, "suspiciously small image"
    return {"page_number_one_based":page,"image_sha256":sha(raw),"image_bytes":len(raw)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    out=args.out.resolve()
    assert not str(out).startswith(str(ROOT)),"no writing to repository"
    out.mkdir(parents=True,exist_ok=False)
    pdfdir=out/"temporary_pdfs"
    pdfdir.mkdir()
    p=json.loads(PROOF.read_text(encoding="utf-8"))
    assert p["status"] == "DRAFT_NO_GO" and not p["independent_human_approval"]
    assert {r["id"] for r in p["rows"]} == set(PAGES)
    entries=[]
    for row in p["rows"]:
        ident=row["id"]
        tag=ident.replace("-","_")
        question_pdf=pdfdir/f"{tag}_question.pdf"
        answer_pdf=pdfdir/f"{tag}_answer.pdf"
        q=retrieve(row["pdf_url"],question_pdf,row["pdf_sha"])
        a=retrieve(row["official_answer_url"],answer_pdf)
        qimg=out/f"{tag}_official_question_page.png"
        aimg=out/f"{tag}_official_answer_page.png"
        eq=render(question_pdf,qimg,PAGES[ident]["question_page"])
        ea=render(answer_pdf,aimg,PAGES[ident]["answer_page"])
        entries.append({"id":ident,"official_answer_letter":row["answer"],
                        "question":{"source":q,"image":str(qimg.name),"render":eq},
                        "answer":{"source":a,"image":str(aimg.name),"render":ea},
                        "reviewed_by_human":False})
    assert len(entries)==2
    meta={"status":"VISUAL_REVIEW_PENDING_NO_GO",
          "warning":"Machine-rendered official PDF pages for human review only. Not a signed source approval, not permission to publish.",
          "rows":entries,"production_modified":False,
          "source_queue_unresolved":428,
          "original_pdf_hashes_pinned":True}
    (out/"VISUAL_REVIEW_PENDING_NO_GO.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Only images and metadata may be uploaded; raw PDFs stay on runner.
    print(json.dumps({"status":meta["status"],"images":4,
                      "question_ids":sorted(PAGES),
                      "human_approved":False},ensure_ascii=False))
if __name__=="__main__":
    main()
