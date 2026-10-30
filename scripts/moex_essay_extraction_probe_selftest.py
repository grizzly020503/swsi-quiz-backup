#!/usr/bin/env python3
"""Zero-network checks of actual legacy MOEX parser and SHA-bound diagnostic."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys
from unittest.mock import patch

import moex_essay_extraction_probe as probe

ROOT = Path(__file__).resolve().parents[1]


def legacy_without_optional_pdf_deps():
    """Compile actual legacy parsing functions without importing PDF packages."""
    source = (ROOT / "scripts/moex_sync.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"clean", "strip_headers", "parse_essays", "pdf_url"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {x.name for x in nodes} == wanted
    env = {"re": re, "TARGET_EXAM_PHRASE": "專門職業及技術人員高等考試",
           "BASE": "https://wwwq.moex.gov.tw/exam"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "moex_sync.py", "exec"), env)
    def parse(text):
        return env["parse_essays"](
            text, {"prefix": "R", "name": "社會工作研究方法", "s": "0606"},
            "108110", "108", "第二次",
        )
    return parse


def main():
    parse = legacy_without_optional_pdf_deps()
    # SYNTHETIC short fixture based on public two-essay page structure;
    # it is NOT represented as actual SHA-verified pypdf output.
    clean = (
        "甲、申論題部分：（50 分）\n"
        "一、請說明德菲法的操作步驟與優缺點。（25 分）\n"
        "二、說明深入訪談的知情同意書應包括哪些內容。（25 分）\n"
        "乙、測驗題部分：（50 分）\n1 測驗第一題"
    )
    normal = probe.diagnose(clean, parse)
    assert normal["legacy_essay_count"] == 2
    assert normal["legacy_essay_points"] == ["25", "25"]
    assert normal["status"] == "EXTRACTED_BUT_REQUIRES_PDF_TEXT_REVIEW"
    assert [m["marker"] for m in normal["exact_question_markers"]] == ["一", "二"]
    assert not normal["human_approval"] and not normal["release_approved"]

    # An embedded section-label spacing change hides both valid questions.
    missing = clean.replace("乙、測驗題部分", "乙 、 測 驗 題 部 分")
    result = probe.diagnose(missing, parse)
    assert result["legacy_essay_count"] == 0
    assert "whitespace_or_linebreak_inside_section_boundary" in result["suspected_extraction_stages"]
    assert result["status"] == "PARSER_FAILURE_REVIEW_REQUIRED"

    # Pinned 108-2 PDF proved the real legacy parser lost the inline second
    # heading. The conservative fallback must now recover exactly 2 questions
    # only when both ordered prompts have explicit individual score marks.
    inline = clean.replace("\n二、說明", "二、說明")
    result = probe.diagnose(inline, parse)
    assert result["legacy_essay_count"] == 2
    assert result["legacy_essay_points"] == ["25", "25"]
    assert result["status"] == "EXTRACTED_BUT_REQUIRES_PDF_TEXT_REVIEW"
    assert "possible_inline_or_spaced_question_markers" in result["suspected_extraction_stages"]
    assert [x["marker"] for x in result["diagnostic_only_relaxed_markers"]] == ["一", "二"]

    # The real pinned 108-2 PDF text places whitespace between the second
    # numeral and its punctuation, not merely before an inline heading.
    pdf_spaced_heading = clean.replace("\n二、說明", "二  、說明")
    spaced = probe.diagnose(pdf_spaced_heading, parse)
    assert spaced["legacy_essay_count"] == 2
    assert spaced["legacy_essay_points"] == ["25", "25"]

    # Incomplete or ambiguous source markers must NOT trigger fallback.
    no_points = inline.replace("同意書應包括哪些內容。（25 分）", "同意書應包括哪些內容。")
    assert probe.diagnose(no_points, parse)["legacy_essay_count"] == 1
    ambiguous = inline.replace("德菲法的操作步驟", "德菲法的。 一、操作步驟")
    assert probe.diagnose(ambiguous, parse)["legacy_essay_count"] == 1

    no_second = clean.replace("二、說明", "題目補充說明")
    assert probe.diagnose(no_second, parse)["legacy_essay_count"] == 1

    # A forged file may have PDF magic but cannot bypass official SHA binding.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "official.pdf"
        fake.write_bytes(b"%PDF-FORGED-MATERIAL")
        with patch.object(probe, "registry_row", return_value={"pdf_sha256": "0" * 64}):
            try:
                probe.pdf_probe(fake, session="108-2", subject="社會工作研究方法")
            except ValueError as exc:
                assert "SHA256" in str(exc)
            else:
                raise AssertionError("forged PDF accepted")

    print("MOEX ESSAY PROBE SELFTEST OK: actual legacy parser 2/0/1, source-safe inline recovery; SHA fail-closed, no writes/approval")
    return 0


if __name__ == "__main__":
    sys.exit(main())
