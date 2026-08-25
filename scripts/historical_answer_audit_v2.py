#!/usr/bin/env python3
"""Compatibility wrapper for historical_answer_audit.

Only replaces compatibility-sensitive MOEX details:
- old correction-note wording
- one legacy exam code that points to a regional make-up exam in the base list
- the 108 second-exam consolidated PDF whose subject headings and answer rows are
  interleaved across pages

All DB access/report generation remains read-only in historical_answer_audit.py.
"""

from __future__ import annotations

import re

import historical_answer_audit as base


ALL = {"A", "B", "C", "D"}

# 106111 is the Hualien/Taitung make-up exam; the normal second exam is 106110.
base.EXAMS = [
    (year, round_name, "106110" if code == "106111" else code)
    for year, round_name, code in base.EXAMS
]


def parse_corrections(section: str, row: str) -> dict[int, set[str]]:
    accepted: dict[int, set[str]] = {}
    note = base.compact(section).upper().translate(base.FW)

    # Parse each 「第N題...」 correction clause independently. Old MOEX PDFs
    # use several wordings and full-width punctuation; compact() already removes
    # whitespace and FW translates full-width A/B/C/D.
    clauses = list(re.finditer(r"第(\d{1,2})題([^第]*)", note))
    for m in clauses:
        qno = int(m.group(1))
        body = m.group(2)

        # Any selected option receives credit (blank answer does not).
        if "一律給分" in body or ("未作答者不給分" in body and "其餘均給分" in body):
            accepted[qno] = set(ALL)
            continue

        # Examples:
        #   答Ａ或Ｃ或ＡＣ者均給分
        #   答Ｂ或Ｄ或BD者均給分
        #   答Ｃ給分
        ans_match = re.search(r"答([ABCD或]{1,20})(?:者)?均?給分", body)
        if ans_match:
            letters = set(re.findall(r"[ABCD]", ans_match.group(1)))
            if letters:
                accepted[qno] = letters
                continue

    # Fill ordinary non-# answers from the 40-character official row.
    for qno, ch in enumerate(row, start=1):
        if ch != "#":
            accepted.setdefault(qno, {ch})
        elif qno not in accepted:
            # Include the nearby note in the error so the next compatibility
            # fix is evidence-based rather than guessed.
            marker = f"第{qno}題"
            pos = note.find(marker)
            excerpt = note[pos : pos + 100] if pos >= 0 else note[:180]
            raise RuntimeError(
                f"question {qno} is # but correction note was not parsed; excerpt={excerpt!r}"
            )

    return accepted


def accepted_from_row(row: str, corrections: dict[int, set[str]] | None = None):
    row = re.sub(r"\s+", "", row).upper().translate(base.FW)
    if len(row) != 40 or not re.fullmatch(r"[ABCD#]{40}", row):
        raise RuntimeError(f"invalid hard-verified official row: {row!r}")
    corrections = corrections or {}
    out = {}
    for qno, ch in enumerate(row, start=1):
        if ch == "#":
            if qno not in corrections:
                raise RuntimeError(f"verified row q{qno} needs correction mapping")
            out[qno] = set(corrections[qno])
        else:
            out[qno] = {ch}
    return out


def verified_108110() -> dict[tuple[str, int], set[str]]:
    """Official 108 second-exam rows transcribed from MOEX t=A final sheet.

    The consolidated PDF is a known layout exception: headings and answer rows are
    interleaved across pages, which defeats the base section splitter. Values here
    are audit-only and retain MOEX # correction semantics.
    """
    rows = {
        "社會工作": (
            "ACCBDABDDCBCADAABDBDDCDCCDCAADBAACBBCBCD",
            {},
        ),
        "社會工作直接服務": (
            "CADBDABDCBDACABBADABCDBBCCDDDDCDADCDBDAA",
            {},
        ),
        "社會政策與社會立法": (
            "BBCDCCBADADADABBACCBCCACCCCCDDCDBACBABAC",
            {},
        ),
        "人類行為與社會環境": (
            "ABADAABBCABDB#DAACAC#BCBAADCADDBCCABCB#B",
            {14: {"D"}, 21: {"A", "B"}, 39: set(ALL)},
        ),
        "社會工作研究方法": (
            "BACDBAABABDDCCDABCBB#BDCADDCBDDCBCCACCDD",
            {21: {"A", "B"}},
        ),
    }
    result = {}
    for subject, (row, corr) in rows.items():
        parsed = accepted_from_row(row, corr)
        for qno in range(1, 41):
            result[(subject, qno)] = parsed[qno]
    return result


_original_parse_official_exam = base.parse_official_exam


def parse_official_exam(data: bytes, year: str, round_name: str, code: str):
    if code == "108110":
        return verified_108110()
    return _original_parse_official_exam(data, year, round_name, code)


base.parse_corrections = parse_corrections
base.parse_official_exam = parse_official_exam

if __name__ == "__main__":
    raise SystemExit(base.main())
