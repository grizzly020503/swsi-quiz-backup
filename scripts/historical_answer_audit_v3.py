#!/usr/bin/env python3
"""Historical SWSI answer audit v3: use MOEX per-subject answer PDFs.

Why v3:
MOEX consolidated t=A sheets can interleave subject headings and answer rows in
multi-column layouts. The exam search page already exposes one official answer PDF
per subject (t=S) and, where applicable, a corrected-answer PDF (t=M). This wrapper
discovers those links and parses each subject independently.

READ-ONLY: no Supabase writes are performed.
"""

from __future__ import annotations

import io
import re
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

import historical_answer_audit as base

ALL = {"A", "B", "C", "D"}
BASE_SITE = "https://wwwq.moex.gov.tw/exam/"
UA = "Mozilla/5.0 (compatible; swsi-historical-answer-audit/3.0)"

# Correct one legacy code in the original audit list: 106111 is a regional
# make-up exam; the normal second exam is 106110.
base.EXAMS = [
    (year, round_name, "106110" if code == "106111" else code)
    for year, round_name, code in base.EXAMS
]


def correction_sets(text: str, row: str) -> dict[int, set[str]]:
    """Resolve A/B/C/D/# row using the official correction note."""
    note = base.compact(text).upper().translate(base.FW)
    accepted: dict[int, set[str]] = {}

    for m in re.finditer(r"第(\d{1,2})題([^第]*)", note):
        qno = int(m.group(1))
        body = m.group(2)

        if "一律給分" in body or ("未作答者不給分" in body and "其餘均給分" in body):
            accepted[qno] = set(ALL)
            continue

        # Official wording includes variants such as:
        # 答Ａ給分 / 答Ａ或Ｃ者均給分 / 答Ａ或Ｃ或AC者均給分.
        if "給分" in body and "答" in body:
            between = body.split("答", 1)[1].split("給分", 1)[0]
            letters = set(re.findall(r"[ABCD]", between))
            if letters:
                accepted[qno] = letters

    for qno, ch in enumerate(row, start=1):
        if ch != "#":
            accepted.setdefault(qno, {ch})
        elif qno not in accepted:
            marker = f"第{qno}題"
            p = note.find(marker)
            excerpt = note[p : p + 120] if p >= 0 else note[:200]
            raise RuntimeError(
                f"q{qno} is # but final correction note was not parsed; excerpt={excerpt!r}"
            )

    if len(accepted) != 40:
        raise RuntimeError(f"resolved {len(accepted)} / 40 answers")
    return accepted


def row_matches_subject(row_text: str, subject: str) -> bool:
    compact = base.compact(row_text)
    if subject == "社會工作":
        # Do not mistake 社會工作直接服務 / 社會工作管理 / 社會工作師 for the
        # plain subject row. On MOEX the subject name is followed by 試題/答案.
        return bool(re.search(r"(?:^|[_：:])社會工作(?=(?:試題|答案|$))", compact)) or compact.startswith("社會工作試題")
    return subject in compact


def discover_subject_urls(code: str, roc_year: str) -> dict[str, str]:
    gregorian = int(roc_year) + 1911
    page_url = f"{BASE_SITE}wFrmExamQandASearch.aspx?e={code}&y={gregorian}"
    r = requests.get(page_url, timeout=45, headers={"User-Agent": UA})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    found: dict[str, dict[str, str]] = {s: {} for s in base.SUBJECTS}
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        if "wHandExamQandA_File.ashx" not in href or "t=" not in href:
            continue
        parent = a.find_parent("tr") or a.parent
        text = parent.get_text(" ", strip=True) if parent else ""
        for subject in sorted(base.SUBJECTS, key=len, reverse=True):
            if not row_matches_subject(text, subject):
                continue
            full = urljoin(page_url, href)
            if re.search(r"[?&]t=M(?:&|$)", full, flags=re.I):
                found[subject]["M"] = full
            elif re.search(r"[?&]t=S(?:&|$)", full, flags=re.I):
                found[subject]["S"] = full

    result = {}
    missing = []
    for subject in base.SUBJECTS:
        links = found[subject]
        chosen = links.get("M") or links.get("S")
        if not chosen:
            missing.append(subject)
        else:
            result[subject] = chosen
    if missing:
        raise RuntimeError(f"{code}: exam page missing answer links for {missing}")
    return result


def download_pdf(url: str) -> bytes:
    r = requests.get(url, timeout=45, headers={"User-Agent": UA})
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"not PDF: {url} ({r.headers.get('content-type')})")
    return r.content


def token_answer(raw: str) -> str | None:
    t = base.clean_line(raw).upper().translate(base.FW)
    if t in {"A", "B", "C", "D", "#"}:
        return t
    return None


def parse_subject_pdf(data: bytes, subject: str, url: str) -> dict[int, set[str]]:
    text = base.pdf_text(data)
    compact = base.compact(text)
    if "社會工作師" not in compact:
        raise RuntimeError(f"{subject}: PDF is not 社會工作師: {url}")
    if base.compact(subject) not in compact:
        raise RuntimeError(f"{subject}: subject name missing in PDF: {url}")

    found: dict[int, str] = {}
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=2,
                y_tolerance=2,
            ) or []
            qwords = []
            awords = []
            for w in words:
                raw = base.clean_line(w.get("text", ""))
                qm = re.fullmatch(r"第(\d+)題", base.compact(raw))
                if qm:
                    qno = int(qm.group(1))
                    if 1 <= qno <= 40:
                        qwords.append({
                            "qno": qno,
                            "cx": (float(w["x0"]) + float(w["x1"])) / 2,
                            "bottom": float(w["bottom"]),
                        })
                    continue
                ans = token_answer(raw)
                if ans:
                    awords.append({
                        "answer": ans,
                        "cx": (float(w["x0"]) + float(w["x1"])) / 2,
                        "top": float(w["top"]),
                    })

            for q in qwords:
                candidates = []
                for a in awords:
                    dx = abs(a["cx"] - q["cx"])
                    dy = a["top"] - q["bottom"]
                    if dx <= 28 and -4 <= dy <= 34:
                        candidates.append((dx + abs(dy) * 0.20, a))
                if not candidates:
                    continue
                candidates.sort(key=lambda x: x[0])
                ans = candidates[0][1]["answer"]
                old = found.get(q["qno"])
                if old and old != ans:
                    raise RuntimeError(f"{subject} q{q['qno']} answer coordinate conflict {old}/{ans}")
                found[q["qno"]] = ans

    missing = [n for n in range(1, 41) if n not in found]
    if missing:
        raise RuntimeError(f"{subject}: per-subject PDF missing coordinate answers {missing}: {url}")

    row = "".join(found[n] for n in range(1, 41))
    return correction_sets(text, row)


def parse_official_exam(_data: bytes, year: str, _round_name: str, code: str):
    urls = discover_subject_urls(code, year)
    out: dict[tuple[str, int], set[str]] = {}
    for subject in base.SUBJECTS:
        data = download_pdf(urls[subject])
        answers = parse_subject_pdf(data, subject, urls[subject])
        for qno in range(1, 41):
            out[(subject, qno)] = answers[qno]
    return out


# The base audit loop calls get_pdf() for the consolidated sheet before invoking
# parse_official_exam(). v3 intentionally does not use that sheet, so avoid the
# redundant download.
base.get_pdf = lambda _code: b""
base.parse_official_exam = parse_official_exam

if __name__ == "__main__":
    raise SystemExit(base.main())
