#!/usr/bin/env python3
"""Question-bank health check v2: preserve official grading semantics.

The proven ``health_check.py`` remains the structural/count checker. This wrapper
adds fail-closed validation for MOEX grading modes without duplicating the rest
of the health-check implementation.

Modes:
- standard: normal single/multi-answer scoring; unanswered is incorrect.
- all_credit: official 一律給分; unanswered also scores.
- any_answer: official 除未作答者不給分外，其餘均給分.

Legacy payload compatibility is intentionally narrow: a missing grading_mode is
accepted only when the answer is not ``一律給分`` and is treated as standard.
A special-credit row without an explicit mode fails closed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import health_check as base

VALID_GRADING_MODES = {"standard", "all_credit", "any_answer"}
SPECIAL_GRADING_MODES = {"all_credit", "any_answer"}

_original_validate_exam = base.validate_exam


def grading_mode_for_question(q: dict, source: str = "payload") -> str:
    qid = str(q.get("id") or "<unknown>")
    answer = q.get("answer")
    raw = q.get("grading_mode")

    if raw is None or not str(raw).strip():
        if answer == "一律給分":
            base.die(f"{source}: {qid} 為特殊給分題但缺 grading_mode")
        return "standard"

    mode = str(raw).strip()
    if mode not in VALID_GRADING_MODES:
        base.die(f"{source}: {qid} grading_mode 異常：{mode}")

    if mode == "standard" and answer == "一律給分":
        base.die(f"{source}: {qid} answer=一律給分 卻標成 standard")
    if mode in SPECIAL_GRADING_MODES and answer != "一律給分":
        base.die(f"{source}: {qid} grading_mode={mode} 但 answer 不是一律給分")

    return mode


def validate_exam(path):
    data = _original_validate_exam(path)
    for q in data.get("questions") or []:
        grading_mode_for_question(q, str(path))
    return data


# base.incoming_payloads() resolves validate_exam dynamically from its module.
base.validate_exam = validate_exam


def local_check(write_report: bool = True):
    report, payloads = base.local_check(write_report=False)

    counts = Counter()
    for path, data in payloads:
        for q in data.get("questions") or []:
            counts[grading_mode_for_question(q, str(path))] += 1

    report["grading_mode_local_counts"] = dict(sorted(counts.items()))
    report.setdefault("checks", []).extend([
        "grading_mode 僅允許 standard/all_credit/any_answer",
        "特殊給分題必須明確標示 all_credit 或 any_answer，不允許缺值猜測",
        "standard 不得搭配 answer=一律給分；特殊模式必須搭配 answer=一律給分",
    ])

    if write_report:
        base.AUTO.mkdir(exist_ok=True)
        (base.AUTO / "health.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(
        "LOCAL GRADING HEALTH OK: "
        + ", ".join(f"{k}={counts.get(k, 0)}" for k in sorted(VALID_GRADING_MODES))
    )
    return report, payloads


def remote_check():
    report, payloads = local_check(write_report=False)
    url, key = base.extract_supabase_config()

    total_questions = base.rest_count(url, key, "questions")
    total_essays = base.rest_count(url, key, "essays")
    if total_questions != report["expected_total_questions"]:
        base.die(
            f'Supabase questions 總數應為 {report["expected_total_questions"]}，實際 {total_questions}'
        )
    if total_essays != report["auto_essay_count"]:
        base.die(
            f'Supabase essays 總數應為 {report["auto_essay_count"]}，實際 {total_essays}'
        )

    for _path, data in payloads:
        code = data["exam_code"]
        if code in base.BASELINE_EXAMS:
            continue
        qcount = base.rest_count(url, key, "questions", {"source_exam_code": code})
        ecount = base.rest_count(url, key, "essays", {"source_exam_code": code})
        if qcount != 200:
            base.die(f"Supabase {code} 選擇題應為 200，實際 {qcount}")
        if ecount != 10:
            base.die(f"Supabase {code} 申論題應為 10，實際 {ecount}")

    mode_counts = {
        mode: base.rest_count(url, key, "questions", {"grading_mode": mode})
        for mode in sorted(VALID_GRADING_MODES)
    }
    if sum(mode_counts.values()) != total_questions:
        base.die(
            "Supabase grading_mode 有 NULL 或非法值："
            f"valid={sum(mode_counts.values())}, total={total_questions}"
        )

    special_total = base.rest_count(url, key, "questions", {"answer": "一律給分"})
    standard_special = base.rest_count(
        url, key, "questions", {"grading_mode": "standard", "answer": "一律給分"}
    )
    all_credit_semantic = base.rest_count(
        url, key, "questions", {"grading_mode": "all_credit", "answer": "一律給分"}
    )
    any_answer_semantic = base.rest_count(
        url, key, "questions", {"grading_mode": "any_answer", "answer": "一律給分"}
    )

    if standard_special != 0:
        base.die(f"Supabase 有 {standard_special} 題一律給分被錯標 standard")
    if all_credit_semantic != mode_counts["all_credit"]:
        base.die("Supabase all_credit 存在 answer 語意不一致")
    if any_answer_semantic != mode_counts["any_answer"]:
        base.die("Supabase any_answer 存在 answer 語意不一致")
    if special_total != mode_counts["all_credit"] + mode_counts["any_answer"]:
        base.die(
            "Supabase 特殊給分總數與 grading_mode 不一致："
            f"answer=一律給分 {special_total}, modes={mode_counts}"
        )

    print(
        "REMOTE HEALTH OK: "
        f"Supabase questions={total_questions}, essays={total_essays}, "
        f"grading_modes={mode_counts}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="社工師題庫健康檢查 v2（含官方給分模式）")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--local", action="store_true")
    group.add_argument("--remote", action="store_true")
    args = ap.parse_args()

    if args.local:
        local_check(write_report=True)
    elif args.remote:
        remote_check()
    else:
        local_check(write_report=True)
        remote_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
