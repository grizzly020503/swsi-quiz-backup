#!/usr/bin/env python3
"""MOEX sync v2: preserve grading semantics and normalize official PDF glyphs.

The proven question/PDF parser remains in ``moex_sync.py``. This thin wrapper
keeps the official unanswered-scoring semantics and normalizes a few MOEX
private-use glyphs that otherwise leak into essay text on browsers without the
official PDF font.

Official grading rules:
- 一律給分 -> all_credit (blank also receives the point)
- 除未作答者不給分外，其餘均給分 -> any_answer (A-D score; blank does not)
- ordinary / multiple-answer questions -> standard
"""

from __future__ import annotations

import re

import moex_sync as base

ALL = set(base.ALL_ANSWERS)

# MOEX PDFs sometimes encode sub-question labels with private-use glyphs tied to
# the PDF's embedded font. Persist semantic Unicode instead so JSON, web views,
# exports, and future re-syncs are stable on every device.
MOEX_TEXT_REPLACEMENTS = {
    "\uE129": "（一）",
    "\uE12A": "（二）",
    "\uE12B": "（三）",
}


def normalize_moex_text(value: str) -> str:
    text = str(value or "")
    for src, dst in MOEX_TEXT_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


_original_clean = base.clean


def clean_with_moex_unicode(value) -> str:
    """Run the proven cleaner, then replace font-dependent MOEX PUA labels."""
    return normalize_moex_text(_original_clean(value))


# parse_essays / parse_mc resolve ``clean`` from moex_sync's module globals at
# call time, so this narrow hook fixes both without duplicating the parser.
base.clean = clean_with_moex_unicode


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


# Patch only narrow extension points; everything else stays on the proven v1 parser.
base._parse_correction_rules = parse_correction_rules_with_grading
base.parse_mc = parse_mc_with_grading


def main():
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
