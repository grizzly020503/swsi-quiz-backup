#!/usr/bin/env python3
"""Regression tests: detect 105-2/107-2 swallowed passages, never auto-edit."""
from __future__ import annotations

from copy import deepcopy

from official_option_scenario_guard import read_rows, scan

EXAMPLES = [
    ("R-105-2-12", "Chatili, D., Mary, E. K., Ching, M. L., and Lee, S. S. 情況：假想廖教授…請依上述資料回答下列第題至第題。"),
    ("R-105-2-20", "樣本數經常會不足 情況：假想某政府單位 3,757 95% 請依上述資料回答下列第題至第題。"),
    ("R-107-2-04", "沒有箭頭的線條表示兩端的變項沒有關係 情況：睡眠對健康至關重要…請依照上述資料，回答下列第 5 題至第 8 題。"),
]


def row(ident: str, choice: str) -> dict:
    return {
        "id": ident, "year": "107", "round": "第二次",
        "subject": "社會工作研究方法",
        "opt_a": "甲", "opt_b": "乙", "opt_c": "丙", "opt_d": choice,
    }


def main() -> int:
    verified_candidate = read_rows()
    base = scan(verified_candidate)
    assert base["scanned_questions"] == 4800
    assert base["scanned_options"] == 19200
    assert base["blocking_suspicions"] == 0, (
        "verified source candidate has newly detected option/context contamination",
        base["risks"][:10],
    )

    for ident, bad_choice in EXAMPLES:
        broken = scan([row(ident, bad_choice)])
        assert broken["blocking_suspicions"] == 1, (ident, broken)
        assert broken["risks"][0]["field"] == "opt_d"
        assert "case_label_inside_option" in broken["risks"][0]["flags"]
        assert "question_range_inside_option" in broken["risks"][0]["flags"]
        assert broken["risks"][0]["automatic_edit"] is False
        assert broken["release_approval"] is False

    # A legitimate short scenario example alone does not prove swallowed text.
    benign = scan([row("EXAMPLE-A", "在這種情況：社工應與案主討論選擇。")])
    assert benign["blocking_suspicions"] == 0
    # Even a long or generic directive without a scenario heading is review only.
    long_choice = scan([row("EXAMPLE-B", "這個研究方法具有下列特性：" + "說明" * 160)])
    assert long_choice["blocking_suspicions"] == 0
    assert "long_option_review" in long_choice["risks"][0]["flags"]
    directive = scan([row("EXAMPLE-C", "請依上述資料回答下列第5題至第8題。")])
    assert directive["blocking_suspicions"] == 0
    assert directive["review_signals"] == 1

    mutated = deepcopy(verified_candidate[:1])
    mutated[0]["opt_d"] = EXAMPLES[0][1]
    assert scan(mutated)["blocking_suspicions"] == 1
    assert mutated[0]["opt_d"] == EXAMPLES[0][1], "read-only scan changed its input"
    dupe = [row("DUPE", "甲"), row("DUPE", "乙")]
    try:
        scan(dupe)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate question ID was not rejected")
    print("OFFICIAL OPTION SCENARIO SELFTEST OK: 4800 checked, 3 source-bug examples detected, no writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
