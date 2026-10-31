#!/usr/bin/env python3
"""Regression tests: detect 105-2/107-2 swallowed passages, never auto-edit."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from official_option_scenario_guard import read_rows, scan, validate_live_baseline, verified_shared_case_groups

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
    validate_live_baseline(verified_candidate)
    shared = verified_shared_case_groups(verified_candidate)
    assert shared["required_groups"] == 3 and shared["required_dependent_questions"] == 10, shared
    assert shared["context_blocking_suspicions"] == 0, shared
    assert shared["groups_with_source_context"] == 3, shared
    def context_broken(ident: str, value: str, expected_reason: str) -> None:
        mutated = [dict(r) for r in verified_candidate]
        victim = next(row for row in mutated if row["id"] == ident)
        original = victim["question"]
        victim["question"] = value
        result = verified_shared_case_groups(mutated)
        assert result["context_blocking_suspicions"] >= 1, result
        assert any(x["id"] == ident and x["reason"] == expected_reason
                   for x in result["context_risks"]), result["context_risks"]
        assert original != victim["question"]
    source_q14 = next(r for r in verified_candidate if r["id"] == "R-105-2-14")
    # The dependent Q14 can no longer be answered in a shuffled one-question drill.
    context_broken("R-105-2-14", source_q14["question"].split("\n\n", 1)[-1],
                   "shared_case_context_missing")
    source_q22 = next(r for r in verified_candidate if r["id"] == "R-105-2-22")
    context_broken("R-105-2-22", source_q22["question"].replace("第21題至第22題", "第20題至第22題"),
                   "shared_case_context_incomplete_or_wrong_range")
    source_q8 = next(r for r in verified_candidate if r["id"] == "R-107-2-08")
    context_broken("R-107-2-08", source_q8["question"].replace("睡眠對健康至關重要", "睡眠無關緊要"),
                   "shared_case_context_mismatch")
    # A missing dependent record cannot quietly pass the shared context gate.
    incomplete = [row for row in verified_candidate if row["id"] != "R-105-2-16"]
    missing = verified_shared_case_groups(incomplete)
    assert any(x["id"] == "R-105-2-16" and x["reason"] ==
               "missing_or_wrong_dependent_question_identity" for x in missing["context_risks"])

    for invalid in ([], verified_candidate[:-1], verified_candidate + [verified_candidate[0]]):
        try:
            validate_live_baseline(invalid)
        except ValueError as exc:
            assert "historical scope incomplete" in str(exc)
        else:
            raise AssertionError("live audit cannot accept partial/empty/duplicate baseline")
    # A 200-item shard or 40-row subject count is not sufficient evidence:
    # duplicate/missing qno values must fail even with unique IDs and 4800 rows.
    for invalid_number in ("15", "not-a-number", "41"):
        duplicate_number = [dict(row) for row in verified_candidate]
        victim = next(row for row in duplicate_number if row["id"] == "R-105-2-16")
        victim["qno"] = invalid_number
        assert len(duplicate_number) == 4800
        try:
            validate_live_baseline(duplicate_number)
        except ValueError as exc:
            assert "historical scope incomplete" in str(exc), str(exc)
        else:
            raise AssertionError(f"corrupt historical qno passed full scope: {invalid_number}")

    # Future official years may be appended without invalidating the historical set.
    future = dict(verified_candidate[0], id="FUTURE-FIXTURE", year="116")
    validate_live_baseline(verified_candidate + [future])
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
    # Exercise the exact production-shaped CLI using a bounded local export,
    # without network or credentials. Detect drift and preserve the report.
    with TemporaryDirectory(prefix="swsi-option-audit-test-") as tmp:
        input_file = Path(tmp) / "live-fixture.json"
        report_file = Path(tmp) / "report.json"
        mutated_full = [dict(r) for r in verified_candidate]
        victim = next(i for i, r in enumerate(mutated_full) if r["id"] == "R-107-2-04")
        mutated_full[victim]["opt_d"] = EXAMPLES[2][1]
        input_file.write_text(json.dumps(mutated_full, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("official_option_scenario_guard.py")),
             "--input", str(input_file), "--out", str(report_file), "--fail-on-blocked"],
            capture_output=True, text=True, timeout=90, check=False,
        )
        assert proc.returncode == 2, (proc.stdout, proc.stderr)
        report = json.loads(report_file.read_text(encoding="utf-8"))
        assert report["dataset_scope"] == "input_export"
        assert report["scanned_questions"] == 4800
        assert report["blocking_suspicions"] >= 1
        assert any(x["id"] == "R-107-2-04" and x["field"] == "opt_d" for x in report["risks"])
        assert report["official_core_modified"] is False and report["release_approval"] is False
        assert report["shared_case_groups"]["context_blocking_suspicions"] == 0
        assert report["shared_case_groups"]["required_dependent_questions"] == 10

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
