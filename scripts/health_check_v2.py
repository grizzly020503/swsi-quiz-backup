#!/usr/bin/env python3
"""Question-bank health check v2: preserve grading and exam-scheme semantics.

The proven ``health_check.py`` still owns historical/release snapshot checks.
For *current incoming* exam payloads this wrapper replaces its fixed 200+10
validator with the effective-dated approved profile from
``data/exam_scheme_registry.v1.json``. Historical 104-115 regression constants
inside ``health_check.py`` remain pinned and are intentionally not generalized.

Grading modes:
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
from exam_scheme import ExamSchemeError, load_registry, require_approved_payload, resolve_profile

VALID_GRADING_MODES = {"standard", "all_credit", "any_answer"}
SPECIAL_GRADING_MODES = {"all_credit", "any_answer"}
REGISTRY = load_registry()


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


def profile_for_payload(data: dict, source: str) -> tuple[dict, dict]:
    try:
        result = require_approved_payload(data, REGISTRY, source)
    except ExamSchemeError as exc:
        base.die(str(exc))
    profile = resolve_profile(REGISTRY, data.get("roc_year"), data.get("round"))
    if profile is None:
        base.die(f"{source}: 找不到已核准 exam scheme profile")
    return result, profile


def validate_exam(path):
    """Validate one current incoming payload from the approved scheme registry.

    This deliberately does not call the legacy fixed-count base.validate_exam;
    otherwise an officially approved future profile could never pass the health
    gate without editing code. The exam-scheme gate remains fail-closed: an
    observed but unapproved structural difference is refused before these
    field-level checks run.
    """
    data = base.read_json(path)
    _scheme, profile = profile_for_payload(data, str(path))
    code = str(data.get("exam_code") or "")
    questions = data.get("questions") or []
    essays = data.get("essays") or []

    subjects = {str(row["name"]) for row in profile.get("subjects") or []}
    mcq_cfg = profile.get("mcq") or {}
    essay_cfg = profile.get("essay") or {}
    expected_mcq = int(mcq_cfg["expected_total"])
    expected_essay = int(essay_cfg["expected_total"])
    mcq_per_subject = int(mcq_cfg["per_subject"])
    essay_per_subject = int(essay_cfg["per_subject"])
    mcq_min = int(mcq_cfg["qno_min"])
    mcq_max = int(mcq_cfg["qno_max"])
    essay_min = int(essay_cfg["qno_min"])
    essay_max = int(essay_cfg["qno_max"])
    valid_answers = {str(x) for x in (mcq_cfg.get("option_letters") or [])}
    valid_answers.add("一律給分")

    if len(questions) != expected_mcq:
        base.die(f"{path}: 選擇題應為 {expected_mcq} 題，實際 {len(questions)}")
    if len(essays) != expected_essay:
        base.die(f"{path}: 申論題應為 {expected_essay} 題，實際 {len(essays)}")

    q_ids = [str(q.get("id") or "") for q in questions]
    e_ids = [str(e.get("id") or "") for e in essays]
    if any(not value for value in q_ids) or len(set(q_ids)) != expected_mcq:
        base.die(f"{path}: 選擇題 ID 空白或重複")
    if any(not value for value in e_ids) or len(set(e_ids)) != expected_essay:
        base.die(f"{path}: 申論題 ID 空白或重複")

    q_subjects = {q.get("subject") for q in questions}
    e_subjects = {e.get("subject") for e in essays}
    if q_subjects != subjects:
        base.die(f"{path}: 選擇題科目集合異常：{sorted(str(x) for x in q_subjects)}")
    if expected_essay and e_subjects != subjects:
        base.die(f"{path}: 申論題科目集合異常：{sorted(str(x) for x in e_subjects)}")
    if not expected_essay and e_subjects:
        base.die(f"{path}: 此核准 profile 不應有申論題")

    for q in questions:
        qid = q.get("id")
        if q.get("source_exam_code") != code:
            base.die(f"{path}: {qid} source_exam_code 不一致")
        if q.get("answer") not in valid_answers:
            base.die(f"{path}: {qid} 答案異常：{q.get('answer')}")
        for key in (
            "subject", "year", "round", "qno", "question",
            "opt_a", "opt_b", "opt_c", "opt_d", "source_url",
        ):
            if not str(q.get(key) or "").strip():
                base.die(f"{path}: {qid} 缺 {key}")
        number = base.qno_int(q)
        if number is None or not mcq_min <= number <= mcq_max:
            base.die(f"{path}: {qid} 題號異常：{q.get('qno')}")
        grading_mode_for_question(q, str(path))

    for essay in essays:
        eid = essay.get("id")
        if essay.get("source_exam_code") != code:
            base.die(f"{path}: {eid} source_exam_code 不一致")
        for key in ("subject", "year", "round", "qno", "q", "source_url"):
            if not str(essay.get(key) or "").strip():
                base.die(f"{path}: {eid} 缺 {key}")
        number = base.qno_int(essay)
        if number is None or not essay_min <= number <= essay_max:
            base.die(f"{path}: {eid} 申論題號異常：{essay.get('qno')}")

    expected_mcq_qnos = set(range(mcq_min, mcq_max + 1))
    expected_essay_qnos = set(range(essay_min, essay_max + 1)) if expected_essay else set()
    for subject in sorted(subjects):
        sq = [q for q in questions if q.get("subject") == subject]
        se = [e for e in essays if e.get("subject") == subject]
        if len(sq) != mcq_per_subject:
            base.die(f"{path}: {subject} 應有 {mcq_per_subject} 題選擇題，實際 {len(sq)}")
        if len(se) != essay_per_subject:
            base.die(f"{path}: {subject} 應有 {essay_per_subject} 題申論，實際 {len(se)}")
        if {base.qno_int(q) for q in sq} != expected_mcq_qnos:
            base.die(f"{path}: {subject} 選擇題題號不符合已核准 profile")
        if {base.qno_int(e) for e in se} != expected_essay_qnos:
            base.die(f"{path}: {subject} 申論題題號不符合已核准 profile")

    stats = data.get("stats") or {}
    for subject in subjects:
        values = stats.get(subject) or {}
        if values.get("mc") != mcq_per_subject or values.get("essay") != essay_per_subject:
            base.die(
                f"{path}: stats 的 {subject} 不是 "
                f"{mcq_per_subject}+{essay_per_subject}"
            )

    return data


# base.incoming_payloads() resolves validate_exam dynamically from its module.
# Replacing only this current-incoming hook preserves historical checks and
# report construction in the proven base module.
base.validate_exam = validate_exam


def local_check(write_report: bool = True):
    report, payloads = base.local_check(write_report=False)

    counts = Counter()
    scheme_counts = Counter()
    for path, data in payloads:
        scheme, _profile = profile_for_payload(data, str(path))
        scheme_counts[str(scheme["profile_id"])] += 1
        for q in data.get("questions") or []:
            counts[grading_mode_for_question(q, str(path))] += 1

    report["grading_mode_local_counts"] = dict(sorted(counts.items()))
    report["exam_scheme_local_counts"] = dict(sorted(scheme_counts.items()))
    report.setdefault("checks", []).extend([
        "current incoming 結構由 data/exam_scheme_registry.v1.json 的 effective-dated approved profile 決定",
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
        "LOCAL GRADING/SCHEME HEALTH OK: "
        + ", ".join(f"{k}={counts.get(k, 0)}" for k in sorted(VALID_GRADING_MODES))
        + f"; schemes={dict(sorted(scheme_counts.items()))}"
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

    for path, data in payloads:
        code = data["exam_code"]
        if code in base.BASELINE_EXAMS:
            continue
        _scheme, profile = profile_for_payload(data, str(path))
        expected_mcq = int(profile["mcq"]["expected_total"])
        expected_essay = int(profile["essay"]["expected_total"])
        qcount = base.rest_count(url, key, "questions", {"source_exam_code": code})
        ecount = base.rest_count(url, key, "essays", {"source_exam_code": code})
        if qcount != expected_mcq:
            base.die(f"Supabase {code} 選擇題應為 {expected_mcq}，實際 {qcount}")
        if ecount != expected_essay:
            base.die(f"Supabase {code} 申論題應為 {expected_essay}，實際 {ecount}")

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
    ap = argparse.ArgumentParser(description="社工師題庫健康檢查 v2（含官方給分模式／版本化考制）")
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
