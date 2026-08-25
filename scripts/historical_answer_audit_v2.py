#!/usr/bin/env python3
"""Compatibility wrapper for historical_answer_audit.

Only replaces compatibility-sensitive MOEX details:
- old correction-note wording
- one legacy exam code that points to a regional make-up exam in the base list

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


base.parse_corrections = parse_corrections

if __name__ == "__main__":
    raise SystemExit(base.main())
