#!/usr/bin/env python3
"""Read-only check of candidate official-text repairs against MOEX question PDFs.

For every candidate row: download its official question PDF (GET only), confirm
the bytes match the recorded SHA-256, extract the text layer, and report whether
each proposed field text occurs in the paper and whether the current text does.
Comparison ignores whitespace, punctuation width and line breaks only.

Verdicts per row:
  VERIFIED          every proposed field is in the paper
  NEEDS_VISUAL      the paper has no usable text layer (scanned image)
  MISMATCH          a proposed field is not in a text-layer paper
Exit status is 1 if any row is MISMATCH or a PDF hash differs, else 0.
Never writes to the repository, database or websites.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

PUNCT = {
    "，": ",", "。": ".", "：": ":", "；": ";", "？": "?", "！": "!", "（": "(", "）": ")",
    "「": "", "」": "", "『": "", "』": "", "、": ",", "－": "-", "–": "-", "—": "-",
    "＜": "<", "＞": ">", "％": "%", "＋": "+", "／": "/", "．": ".", "～": "~",
}
CIRCLED = {chr(0x2460 + i): f"({i + 1})" for i in range(20)}


def norm(text: str) -> str:
    s = str(text or "")
    s = "".join(chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else c for c in s)
    s = "".join(PUNCT.get(c, CIRCLED.get(c, c)) for c in s)
    s = s.replace("χ²", "χ2").replace("χ 2", "χ2")
    s = re.sub(r"[\s　 ​﻿]+", "", s)
    s = re.sub(r"[,.:;?!()\"'`]", "", s)
    return s.lower()


def fetch(url: str) -> bytes:
    import requests
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "SWSI-official-source-verify/1.0"})
            r.raise_for_status()
            if not r.content.startswith(b"%PDF"):
                raise RuntimeError(f"not a PDF (status={r.status_code}, prefix={r.content[:12]!r})")
            return r.content
        except Exception as exc:  # network retry with backoff
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"download failed: {last}")


def pdf_text(data: bytes) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(data)) or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--out", default="/tmp/official-source-repair-verify.json")
    args = ap.parse_args()
    doc = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    cache: dict[str, dict] = {}
    report, failed = [], False
    for row in doc["rows"]:
        url = row["question_source_url"]
        if url not in cache:
            try:
                data = fetch(url)
                sha = hashlib.sha256(data).hexdigest()
                text = pdf_text(data)
                cache[url] = {"sha256": sha, "norm": norm(text), "chars": len(norm(text))}
            except Exception as exc:
                cache[url] = {"error": str(exc)}
        paper = cache[url]
        entry = {"id": row["id"], "url": url}
        if "error" in paper:
            entry.update(verdict="DOWNLOAD_FAILED", error=paper["error"])
            failed = True
        else:
            entry["sha_match"] = paper["sha256"] == row.get("question_pdf_sha256")
            if not entry["sha_match"]:
                entry["sha256"] = paper["sha256"]
                failed = True
            fields = {}
            for name, pair in row["fields"].items():
                fields[name] = {
                    "proposed_in_pdf": norm(pair["proposed"]) in paper["norm"],
                    "current_in_pdf": bool(norm(pair["current"])) and norm(pair["current"]) in paper["norm"],
                }
            entry["fields"] = fields
            if paper["chars"] < 500:
                entry["verdict"] = "NEEDS_VISUAL"
            elif all(f["proposed_in_pdf"] for f in fields.values()):
                entry["verdict"] = "VERIFIED"
            else:
                entry["verdict"] = "MISMATCH"
                failed = True
        report.append(entry)
        f = entry.get("fields", {})
        detail = " ".join(f"{k}:{'Y' if v['proposed_in_pdf'] else 'N'}/{'y' if v['current_in_pdf'] else 'n'}" for k, v in f.items())
        print(f"{entry['verdict']:<16} {row['id']:<14} sha={'ok' if entry.get('sha_match') else 'DIFF'} {detail}")
    Path(args.out).write_text(json.dumps({"rows": report}, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for e in report:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    print("SUMMARY", json.dumps(counts, ensure_ascii=False), "(field codes: proposed-in-PDF Y/N / current-in-PDF y/n)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
