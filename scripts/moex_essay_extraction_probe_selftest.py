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

    # Official PDF points can contain whitespace inside the parentheses.
    # Both markers must be interpreted as 25, not silently replaced by 20.
    odd_spacing = clean.replace("（25 分）", "（ 25 分 ）")
    normalized = probe.diagnose(odd_spacing, parse)
    assert normalized["legacy_essay_count"] == 2
    assert normalized["legacy_essay_points"] == ["25", "25"]

    # Existing old behavior guessed a default of 20 for scoreless Official Core.
    # New behavior MUST fail closed for a normally segmented two-essay PDF.
    no_explicit_score = clean.replace("內容。（25 分）", "內容。")
    try:
        parse(no_explicit_score)
    except RuntimeError as exc:
        assert "配分無法從 PDF 確認" in str(exc), str(exc)
        assert "第 2 題" in str(exc), str(exc)
    else:
        raise AssertionError("scoreless official essay was wrongly accepted")

    # Several explicit point markers are not interchangeable with a single
    # official question score. The former parser silently selected the last
    # marker when their sum exceeded 40, e.g. 25+10+15 -> *15*.
    ambiguous_points = clean.replace(
        "德菲法的操作步驟與優缺點。（25 分）",
        "德菲法的操作步驟與優缺點。（25 分）分項：（10 分）（15 分）",
    )
    try:
        parse(ambiguous_points)
    except RuntimeError as exc:
        assert "配分標記互相矛盾" in str(exc), str(exc)
        assert "第 1 題" in str(exc), str(exc)
    else:
        raise AssertionError("contradictory official score markers were wrongly accepted")

    duplicate_points = clean.replace(
        "德菲法的操作步驟與優缺點。（25 分）",
        "德菲法的操作步驟與優缺點。（25 分）（25 分）",
    )
    try:
        parse(duplicate_points)
    except RuntimeError as exc:
        assert "配分標記互相矛盾" in str(exc), str(exc)
    else:
        raise AssertionError("ambiguous repeated official scores were wrongly accepted")

    # Preserve intentional subquestion aggregation (10+15=25). A complete
    # source audit remains mandatory; this synthetic case only tests arithmetic.
    split_explicit_points = clean.replace(
        "德菲法的操作步驟與優缺點。（25 分）",
        "德菲法的操作步驟與優缺點：甲（10 分）、乙（15 分）。",
    )
    assert [row["points"] for row in parse(split_explicit_points)] == ["25", "25"]

    zero_points = clean.replace(
        "德菲法的操作步驟與優缺點。（25 分）",
        "德菲法的操作步驟與優缺點。（0 分）",
    )
    try:
        parse(zero_points)
    except RuntimeError as exc:
        assert "配分標記無效" in str(exc), str(exc)
        assert "第 1 題" in str(exc), str(exc)
    else:
        raise AssertionError("zero-point official essay was wrongly accepted")

    # Two individually explicit points can still disagree with the printed
    # total for the essay section; do not silently import 25+20 as "valid".
    wrong_section_sum = clean.replace(
        "內容。（25 分）", "內容。（20 分）"
    )
    try:
        parse(wrong_section_sum)
    except RuntimeError as exc:
        assert "申論分數合計不符" in str(exc), str(exc)
        assert "原卷申論總分=50" in str(exc), str(exc)
        assert "逐題合計=45" in str(exc), str(exc)
    else:
        raise AssertionError("mismatched explicit essay section total was accepted")

    wrong_header_total = clean.replace(
        "甲、申論題部分：（50 分）", "甲、申論題部分：（60 分）"
    )
    try:
        parse(wrong_header_total)
    except RuntimeError as exc:
        assert "申論分數合計不符" in str(exc), str(exc)
    else:
        raise AssertionError("unmatched explicit section header score was accepted")

    duplicate_header_total = clean.replace(
        "甲、申論題部分：（50 分）",
        "甲、申論題部分：（50 分）（50 分）",
    )
    try:
        parse(duplicate_header_total)
    except RuntimeError as exc:
        assert "申論總分標記不明" in str(exc), str(exc)
    else:
        raise AssertionError("duplicate section score markers were accepted")

    # If the source text did not preserve a section total, never fabricate
    # it based on historical expectations. Per-question markers are still
    # mandatory and any discrepancy stays for official source review.
    no_total_header = clean.replace(
        "甲、申論題部分：（50 分）", "甲、申論題部分："
    )
    assert [row["points"] for row in parse(no_total_header)] == ["25", "25"]
    assert [row["points"] for row in parse(
        clean.replace("甲、申論題部分：（50 分）", "甲、申論題部分：（ 50 分 ）")
    )] == ["25", "25"]

    # This check is deliberately not an 'approved official content' test.
    # It guards import safety only; normal source comparison stays manual.

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
    # The malformed extra first-question marker suppresses bounded heading
    # recovery. Its single remaining body then contains both 25-point markers.
    # A parser hard-fail is safer than silently attaching both to one essay.
    try:
        result = probe.diagnose(ambiguous, parse)
    except RuntimeError as exc:
        assert "配分標記互相矛盾" in str(exc), str(exc)
    else:
        assert result["legacy_essay_count"] == 1, result

    no_second = clean.replace("二、說明", "題目補充說明")
    # Removing the second marker also folds two scored question bodies into
    # one. It must be rejected, not scored using the final 25-point marker.
    try:
        parse(no_second)
    except RuntimeError as exc:
        assert "配分標記互相矛盾" in str(exc), str(exc)
    else:
        raise AssertionError("merged two-score body was wrongly accepted")

    # A third top-level essay heading would be silently discarded by the old
    # matches[:2] loop, and a repeated first heading would masquerade as Q2.
    # Neither may be imported as a two-question official PDF.
    extra_heading = clean.replace(
        "二、說明深入訪談",
        "一、辨識出多餘的大題標記。（5 分）\\n二、說明深入訪談",
    ).replace("。（5 分）\\n二、", "。（5 分）\n二、")
    try:
        parse(extra_heading)
    except RuntimeError as exc:
        assert "申論題號界線不明" in str(exc), str(exc)
    else:
        raise AssertionError("third essay heading was silently truncated")

    repeated_heading = clean.replace("二、說明深入訪談", "一、說明深入訪談")
    try:
        parse(repeated_heading)
    except RuntimeError as exc:
        assert "申論題號界線不明" in str(exc), str(exc)
    else:
        raise AssertionError("repeated first essay heading was wrongly accepted")

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
