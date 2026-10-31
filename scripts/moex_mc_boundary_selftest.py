#!/usr/bin/env python3
"""Zero-network tests of the actual MOEX MCQ parser's swallowed-case gate.

Fixtures mirror a documented class of 105-2 / 107-2 research PDF extraction
failure. They are SYNTHETIC and must not be treated as an official-PDF audit.
No Official Core, database, answer, or PDF files are written.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def actual_parser():
    tree = ast.parse((ROOT / "scripts/moex_sync.py").read_text(encoding="utf-8"))
    names = {
        "clean", "pdf_url", "normalize_option_markers",
        "option_contains_followup_case_passage", "parse_mc",
    }
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in nodes} == names
    env = {
        "re": re,
        "BASE": "https://wwwq.moex.gov.tw/exam",
        "OPTION_MARKERS": {
            "\ue18c": "A", "\ue18d": "B", "\ue18e": "C", "\ue18f": "D",
        },
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "moex_sync.py", "exec"), env)
    return env


def parse_one(env, *, qno=12, option_key="D", inserted="樣本數經常會不足"):
    options = {"A": "正常甲", "B": "正常乙", "C": "正常丙", "D": "正常丁"}
    options[option_key] = inserted
    raw = "請問下列何者正確？\n" + "\n".join(
        f"{key}. {val}" for key, val in options.items()
    )
    env["split_question_blocks"] = lambda _text: [(qno, raw)]
    subject = {"name": "社會工作研究方法", "prefix": "R", "s": "0305"}
    rules = [{"answer": "B"} for _ in range(40)]
    return env["parse_mc"]("synthetic fixture", subject, "105090", "105", "第二次", rules)


def main() -> int:
    parser = actual_parser()
    judge = parser["option_contains_followup_case_passage"]
    examples = [
        (
            "R-105-2-12",
            "Chatili, D., Mary, E. K. 情況：假想廖教授以協會會員普查。"
            "請依上述資料回答下列第題至第題。",
        ),
        (
            "R-105-2-20",
            "樣本數經常會不足 情況：假想某政府單位委託電話民調。"
            "請依上述資料回答下 列第題至第題。",
        ),
        (
            "R-107-2-04",
            "沒有箭頭的線條表示兩端的變項沒有關係 情況：睡眠對健康至關重要。"
            "請依照上述資料，回答下列第 5 題至第 8 題。",
        ),
    ]
    for ident, wrong in examples:
        assert judge(wrong), ident
        try:
            parse_one(parser, qno=int(ident.rsplit("-", 1)[-1]), inserted=wrong)
        except RuntimeError as exc:
            assert "共同情境被併入選項" in str(exc), (ident, exc)
            assert "須人工對照原始考選部 PDF" in str(exc), (ident, exc)
            assert "D 選項" in str(exc), (ident, exc)
        else:
            raise AssertionError(f"{ident}: future official import accepted contaminated D")

    # Guard applies to ALL choices, not just historic D.
    case = "情境：後續題目有共同資料。請根據上述資料作答下列第2題至第4題。"
    for option in "ABCD":
        try:
            parse_one(parser, option_key=option, inserted=case)
        except RuntimeError as exc:
            assert f"{option} 選項" in str(exc), exc
        else:
            raise AssertionError(f"swallowed next-case in {option} accepted")

    benign = [
        "在這種情況：社工應與案主討論選擇。",
        "請依上述資料回答下列第5題至第8題。",
        "研究情境：照顧者遇到困境，如何評估風險？",
        "原題選項包含案例描述，但沒有任何後續題目指令。",
    ]
    for choice in benign:
        assert not judge(choice), choice
        rows = parse_one(parser, inserted=choice)
        assert len(rows) == 1 and rows[0]["opt_d"] == choice
        assert rows[0]["answer"] == "B"
    assert parse_one(parser)[0]["answer"] == "B"

    print(
        "MOEX MCQ BOUNDARY SELFTEST OK: three known-class poisoned D cases, "
        "all A-D blocked; benign controls and official answer untouched"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
