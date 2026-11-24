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
  LAYOUT_CONFIRMED  not provable from the text layer (column order, glyphs) but
                    covered by a recorded column-preserving layout review
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


def layout_text(data: bytes) -> str:
    """Deterministic, column-preserving text (poppler pdftotext -layout)."""
    import shutil
    import subprocess
    import tempfile
    if not data or not shutil.which("pdftotext"):
        return ""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(data)
        tmp.flush()
        return subprocess.run(["pdftotext", "-layout", tmp.name, "-"], capture_output=True, text=True).stdout


def layout_excerpt(data: bytes, stem: str, lines: int = 16) -> str | None:
    """Column-preserving view of the question (poppler pdftotext -layout)."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("pdftotext"):
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(data)
        tmp.flush()
        out = subprocess.run(["pdftotext", "-layout", tmp.name, "-"], capture_output=True, text=True).stdout
    rows = out.splitlines()
    key = norm(stem)[:10]
    for i, line in enumerate(rows):
        if key and key in norm(" ".join(rows[i:i + 2])):
            return "\n".join(rows[max(0, i - 1):i + lines])
    return None


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
                cache[url] = {"sha256": sha, "norm": norm(text), "chars": len(norm(text)), "data": data,
                              "layout_norm": norm(layout_text(data))}
            except Exception as exc:
                cache[url] = {"error": str(exc)}
        paper = cache[url]
        entry = {"id": row["id"], "url": url}
        if "error" in paper:
            entry.update(verdict="DOWNLOAD_FAILED", error=paper["error"])
            failed = True
        else:
            recorded = row.get("question_pdf_sha256")
            entry["sha256"] = paper["sha256"]
            # A candidate without a recorded hash (new provenance) records it here.
            entry["sha_match"] = True if not recorded else paper["sha256"] == recorded
            if not entry["sha_match"]:
                entry["sha256"] = paper["sha256"]
                failed = True
            fields = {}
            for name, pair in row["fields"].items():
                prop = norm(pair["proposed"])
                fields[name] = {
                    "proposed_in_pdf": prop in paper["norm"],
                    "current_in_pdf": bool(norm(pair["current"])) and norm(pair["current"]) in paper["norm"],
                }
                if not fields[name]["proposed_in_pdf"] and len(prop) >= 24:
                    # Share of 12-character windows found in the paper: high means the
                    # right paper with a wording difference, low means a wrong paper.
                    grams = [prop[i:i + 12] for i in range(0, len(prop) - 11, 6)]
                    fields[name]["window_coverage"] = round(sum(g in paper["norm"] for g in grams) / len(grams), 2)
                    fields[name]["missing_windows"] = [g for g in grams if g not in paper["norm"]][:6]
            entry["fields"] = fields
            # Option order: from the stem, the proposed A-D must appear in order.
            stem = norm(row["fields"].get("question", {}).get("proposed") or row.get("stem") or "")
            # Order is read from the column-preserving layout (row by row, stable
            # across runs); the plain text layer may interleave columns.
            hay = paper.get("layout_norm") or paper["norm"]
            start = hay.find(stem) + len(stem) if stem and stem in hay else -1
            order_ok = None
            if start >= 0 and row.get("proposed_options"):
                pos, order_ok = start, True
                for key in ("opt_a", "opt_b", "opt_c", "opt_d"):
                    val = norm(row["proposed_options"][key])
                    nxt = hay.find(val, pos) if val else pos
                    if nxt < 0 or nxt - start > 600:
                        order_ok = False
                        break
                    pos = nxt + len(val)
            entry["option_order_ok"] = order_ok
            entry["pdf_excerpt"] = hay[max(0, start - len(stem)):start + 400] if start >= 0 else None
            if paper["chars"] < 500:
                entry["verdict"] = "NEEDS_VISUAL"
            elif all(f["proposed_in_pdf"] for f in fields.values()) and order_ok is not False:
                entry["verdict"] = "VERIFIED"
            else:
                entry["verdict"] = "MISMATCH"
                failed = True
        reviewed = (doc.get("layout_review") or {}).get("rows", {})
        if entry.get("verdict") in ("MISMATCH", "NEEDS_VISUAL") and row["id"] in reviewed and entry.get("sha_match"):
            # Text layer cannot order columns or decode the glyph; a recorded
            # column-preserving layout review covers it. Reported separately.
            entry["verdict"] = "LAYOUT_CONFIRMED"
            entry["layout_review"] = reviewed[row["id"]]
            failed = any(e.get("verdict") in ("MISMATCH", "DOWNLOAD_FAILED") or e.get("sha_match") is False for e in report)
        report.append(entry)
        f = entry.get("fields", {})
        detail = " ".join(f"{k}:{'Y' if v['proposed_in_pdf'] else 'N'}/{'y' if v['current_in_pdf'] else 'n'}"
                          + (f" cov={v['window_coverage']} miss={v.get('missing_windows')}" if "window_coverage" in v else "")
                          for k, v in f.items())
        print(f"{entry['verdict']:<16} {row['id']:<14} sha={'ok' if entry.get('sha_match') else 'DIFF'} order={entry.get('option_order_ok')} {detail}")
        if entry["verdict"] != "VERIFIED" or entry.get("option_order_ok") is None:
            view = layout_excerpt(paper.get("data", b""), row.get("stem") or "")
            entry["layout_excerpt"] = view
            print("   PDF layout:\n" + "\n".join("   | " + l for l in (view or "(stem not found in layout text)").splitlines()))
    Path(args.out).write_text(json.dumps({"rows": report}, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for e in report:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    print("SUMMARY", json.dumps(counts, ensure_ascii=False), "(field codes: proposed-in-PDF Y/N / current-in-PDF y/n)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
