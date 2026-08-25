#!/usr/bin/env python3
"""MOEX sync v2: preserve official unanswered-scoring semantics.

The proven question/PDF parser remains in ``moex_sync.py``. This thin wrapper only
replaces correction-rule resolution and adds ``grading_mode`` to normalized MC
rows, so the two official MOEX rules below are no longer collapsed:

- 一律給分 -> all_credit (blank also receives the point)
- 除未作答者不給分外，其餘均給分 -> any_answer (A-D score; blank does not)

All ordinary and multiple-answer questions remain ``standard``.
"""

from __future__ import annotations

import re

import moex_sync as base

ALL = set(base.ALL_ANSWERS)


def parse_correction_rules_with_grading(text, raw_answers):
    """Resolve final answers plus the official scoring mode for all 40 items."""
    note = base.compact_text(text).upper().translate(base.FW)
    accepted: dict[int, set[str]] = {}
    modes: dict[int, str] = {}

    for m in re.finditer(r"第(\d{1,2})題([^第]*)", note):
        qno = int(m.group(1))
        body = m.group(2)
        if not 1 <= qno <= 40:
            continue

        if "一律給分" in body:
            accepted[qno] = set(ALL)
            modes[qno] = "all_credit"
            continue

        if "未作答者不給分" in body and "其餘均給分" in body:
            accepted[qno] = set(ALL)
            modes[qno] = "any_answer"
            continue

        if "給分" in body and "答" in body:
            between = body.split("答", 1)[1].split("給分", 1)[0]
            letters = set(re.findall(r"[ABCD]", between))
            if letters:
                accepted[qno] = letters
                modes[qno] = "standard"

    for qno, token in enumerate(raw_answers, start=1):
        if token == "一律給分":
            accepted.setdefault(qno, set(ALL))
            modes.setdefault(qno, "all_credit")
        elif token in ALL:
            accepted.setdefault(qno, {token})
            modes.setdefault(qno, "standard")
        elif token == "#":
            if qno not in accepted:
                marker = f"第{qno}題"
                p = note.find(marker)
                excerpt = note[p:p + 160] if p >= 0 else note[:240]
                raise RuntimeError(
                    f"官方更正答案第 {qno} 題為 #，但無法解析最終給分規則：{excerpt!r}"
                )
            modes.setdefault(qno, "standard")
        else:
            raise RuntimeError(f"官方答案第 {qno} 題出現未知標記：{token!r}")

    if len(accepted) != 40 or len(modes) != 40:
        raise RuntimeError(
            f"官方更正答案只解析出 answers={len(accepted)} / modes={len(modes)} / 40 題"
        )

    rules = []
    for qno in range(1, 41):
        answers = sorted(accepted[qno])
        mode = modes[qno]

        if mode in {"all_credit", "any_answer"}:
            if set(answers) != ALL:
                raise RuntimeError(
                    f"官方第 {qno} 題 grading_mode={mode} 但可接受答案不是 A-D 全部：{answers}"
                )
            rules.append({"answer": "一律給分", "grading_mode": mode})
        elif len(answers) == 1:
            rules.append({"answer": answers[0], "grading_mode": "standard"})
        else:
            rules.append({
                "answer": answers[0],
                "accepted_answers": answers,
                "grading_mode": "standard",
            })
    return rules


_original_parse_mc = base.parse_mc


def parse_mc_with_grading(text, subject, exam_code, roc_year, round_name, answer_rules):
    rows = _original_parse_mc(
        text,
        subject,
        exam_code,
        roc_year,
        round_name,
        answer_rules,
    )
    if len(rows) != len(answer_rules):
        raise RuntimeError(
            f"選擇題與官方答案規則數量不一致：rows={len(rows)} rules={len(answer_rules)}"
        )
    for row, rule in zip(rows, answer_rules):
        mode = rule.get("grading_mode", "standard")
        if mode not in {"standard", "all_credit", "any_answer"}:
            raise RuntimeError(f"未知 grading_mode：{mode!r}")
        row["grading_mode"] = mode
    return rows


# Patch only the two narrow extension points; everything else stays on the proven v1 parser.
base._parse_correction_rules = parse_correction_rules_with_grading
base.parse_mc = parse_mc_with_grading


def main():
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
