#!/usr/bin/env python3
"""Focused tests for MOEX grading-mode semantics."""

from moex_sync_v2 import parse_correction_rules_with_grading


def main() -> int:
    raw = ["A"] * 40
    raw[15] = "#"  # Q16
    raw[16] = "#"  # Q17
    raw[17] = "#"  # Q18

    note = (
        "第16題一律給分，"
        "第17題除未作答者不給分外，其餘均給分，"
        "第18題答Ａ或Ｃ者均給分。"
    )
    rules = parse_correction_rules_with_grading(note, raw)

    assert len(rules) == 40
    assert rules[0] == {"answer": "A", "grading_mode": "standard"}
    assert rules[15] == {"answer": "一律給分", "grading_mode": "all_credit"}
    assert rules[16] == {"answer": "一律給分", "grading_mode": "any_answer"}
    assert rules[17] == {
        "answer": "A",
        "accepted_answers": ["A", "C"],
        "grading_mode": "standard",
    }

    direct = ["A"] * 40
    direct[3] = "一律給分"
    direct_rules = parse_correction_rules_with_grading("", direct)
    assert direct_rules[3] == {"answer": "一律給分", "grading_mode": "all_credit"}

    print("MOEX grading-mode parser tests OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
