#!/usr/bin/env python3
"""Self-test for scripts/ai_feedback_eval.py.

This test is fully deterministic and does not call any external AI service.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = ROOT / "scripts" / "ai_feedback_eval.py"
DATASET_PATH = ROOT / "ai_eval" / "golden_set.json"


def load_module():
    spec = importlib.util.spec_from_file_location("swsi_ai_feedback_eval", EVAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import evaluator from {EVAL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def good_output(case, contract):
    critical = []
    critical.extend(case["expectations"]["must_mention_all"])
    for group in case["expectations"]["must_mention_any"]:
        critical.append(group[0])

    extra = []
    if case["expectations"]["require_uncertainty"]:
        extra.append("這個內容需要再核對，不能把未確認資訊當成事實。")
    if case["expectations"]["require_question_priority"]:
        extra.append("若參考架構與正式考題衝突，應以正式考題為準。")

    text = (
        "一、題目要你答什麼：先依題目要求整理回答範圍，確認每一部分都有回應。"
        + (" 可注意「" + "、".join(critical) + "」。" if critical else "")
        + "\n二、你已經做到什麼：你的作答已經有可用的起點，可以保留目前清楚的觀點，再把理由和題目連得更緊。"
        + "\n三、下一步可以補什麼：建議補上更具體的判斷依據、情境或作法，讓每個重點都有說明，而不是只列名詞。"
        + (" " + " ".join(extra) if extra else "")
        + " 最後再逐項對照題目檢查是否漏答。你已經有方向，下一版把內容寫得更具體就會更完整。"
    )

    if len("".join(text.split())) < contract["preferred_min_chars"]:
        text += " 作答時可以使用『主張—理由—具體作法』的方式展開，並避免加入題目沒有提供、自己也無法確認的資訊。"
    return text


def build_good_payload(dataset):
    dims = dataset["human_rubric"]["dimensions"]
    return {
        "schema_version": 1,
        "golden_set": dataset["name"],
        "model": dataset["model_contract"]["public_model"],
        "prompt_version": dataset["prompt_contract"]["guide_version"],
        "generated_at": "selftest",
        "cases": [
            {
                "id": case["id"],
                "output": good_output(case, dataset["global_output_contract"]),
                "human_scores": {dim: 2 for dim in dims},
                "review_notes": "synthetic self-test record",
            }
            for case in dataset["cases"]
        ],
    }


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    evaluator = load_module()
    dataset = evaluator.load_json(DATASET_PATH)

    errors, warnings = evaluator.validate_dataset(dataset)
    require(not errors, "baseline dataset must validate: " + " | ".join(errors))
    require(len(dataset["cases"]) >= 20, "baseline must contain at least 20 cases")

    good = build_good_payload(dataset)
    report = evaluator.evaluate_outputs(dataset, good, require_human_scores=True)
    require(report["passed"], "synthetic good outputs must pass: " + repr(report))

    authoritative = copy.deepcopy(good)
    authoritative["cases"][0]["output"] += " 這就是標準答案，而且一定得分。"
    report = evaluator.evaluate_outputs(dataset, authoritative, require_human_scores=True)
    require(not report["passed"], "authoritative-score regression must fail")
    case_result = report["cases"][authoritative["cases"][0]["id"]]
    require(case_result["errors"], "authoritative-score regression must produce case errors")

    missing_heading = copy.deepcopy(good)
    missing_heading["cases"][1]["output"] = missing_heading["cases"][1]["output"].replace(
        "三、下一步可以補什麼", "三、後續建議", 1
    )
    report = evaluator.evaluate_outputs(dataset, missing_heading, require_human_scores=True)
    require(not report["passed"], "missing feedback section must fail")

    # A map-keyed payload must not silently relabel the model output for
    # another Golden Set case by supplying a conflicting embedded record id.
    object_cases = copy.deepcopy(good)
    object_cases["cases"] = {record["id"]: dict(record) for record in object_cases["cases"]}
    report = evaluator.evaluate_outputs(dataset, object_cases, require_human_scores=True)
    require(report["passed"], "matching map-keyed case ids must remain accepted")

    mismatched_case = copy.deepcopy(object_cases)
    first_id, second_id = [case["id"] for case in dataset["cases"][:2]]
    mismatched_case["cases"][first_id]["id"] = second_id
    report = evaluator.evaluate_outputs(dataset, mismatched_case, require_human_scores=True)
    require(not report["passed"], "embedded id mismatch must fail candidate evidence")
    require(
        any("mismatched embedded id" in error for error in report["payload_errors"]),
        "embedded id mismatch must be reported as a payload error",
    )

    omitted_embedded_id = copy.deepcopy(object_cases)
    omitted_embedded_id["cases"][first_id].pop("id")
    report = evaluator.evaluate_outputs(dataset, omitted_embedded_id, require_human_scores=True)
    require(report["passed"], "map-keyed case without redundant embedded id must remain accepted")

    # FAIR LANGUAGE QA: the model may correctly say "第二子題" instead of
    # the Golden Set's "第二小題" / "第二問". This is an exact, narrow phrasing
    # equivalent; it is NOT a blanket semantic pass for a student answer.
    coverage_case = next(case for case in dataset["cases"] if case["id"] == "coverage_missing_second_part")
    coverage_output = good_output(coverage_case, dataset["global_output_contract"])
    require("第二問" in coverage_output, "coverage fixture must include the original ordinal")
    alternate_ordinal = coverage_output.replace("第二問", "第二子題")
    ordinal_errors, _ = evaluator.evaluate_case(
        coverage_case, alternate_ordinal, dataset["global_output_contract"]
    )
    require(not ordinal_errors, "valid 第二子題 wording must not be rejected: " + repr(ordinal_errors))

    wrong_ordinal = coverage_output.replace("第二問", "第一子題")
    ordinal_errors, _ = evaluator.evaluate_case(
        coverage_case, wrong_ordinal, dataset["global_output_contract"]
    )
    require(
        any("case-critical concept missing" in error for error in ordinal_errors),
        "first subquestion must not satisfy missing-second-subquestion requirement",
    )

    # The public runtime withholds unverified guides from the AI. Requiring
    # the AI to mention a hidden guide is a false negative, not student error.
    unverified = next(case for case in dataset["cases"] if case["id"] == "unverified_reference_not_standard")
    unseen_output = good_output(unverified, dataset["global_output_contract"])
    unseen_output = unseen_output.replace("參考", "教材").replace("架構", "框架").replace("未核對", "尚未檢查")
    require(
        not any(word in unseen_output for word in ("參考", "架構", "未核對")),
        "unseen reference fixture must not accidentally satisfy lexical reference expectation",
    )
    unseen_errors, _ = evaluator.evaluate_case(unverified, unseen_output, dataset["global_output_contract"])
    require(not unseen_errors, "hidden unverified guide mention must not be required: " + repr(unseen_errors))

    # Fail-closed boundary: the same wording does NOT satisfy a verified
    # conflicting-reference case whose expectations explicitly require it.
    visible_case = copy.deepcopy(unverified)
    visible_case["reference_status"] = "verified_but_intentionally_conflicting_fixture"
    visible_errors, _ = evaluator.evaluate_case(visible_case, unseen_output, dataset["global_output_contract"])
    require(
        any("case-critical concept missing" in error for error in visible_errors),
        "reference evidence must still be required when a verified guide was supplied",
    )

    # Question-first discipline and all other gates remain mandatory even
    # when a reference was withheld.
    no_priority = unseen_output.replace("以正式考題為準", "由作者自行決定")
    no_priority = no_priority.replace("以題目為準", "由作者自行決定")
    no_priority = no_priority.replace("題目要求", "撰寫重點")
    no_priority = no_priority.replace("題意優先", "自行選擇")
    no_priority = no_priority.replace("正式考題優先", "自行選擇")
    priority_errors, _ = evaluator.evaluate_case(unverified, no_priority, dataset["global_output_contract"])
    require(
        any("question-priority language required" in error for error in priority_errors),
        "question-first rule must still be enforced for unverified guide cases",
    )

    missing_case = copy.deepcopy(good)
    missing_case["cases"] = missing_case["cases"][:-1]
    report = evaluator.evaluate_outputs(dataset, missing_case, require_human_scores=True)
    require(not report["passed"], "missing Golden Set output must fail closed")
    require(report["payload_errors"], "missing Golden Set output must produce payload error")

    # A real captured JSON can contain NaN/Infinity (Python json.loads accepts
    # these non-standard constants). Never allow malformed or non-whole human
    # rubric values to make a candidate appear reviewed and passing.
    for invalid_score in (float("nan"), float("inf"), -float("inf"), True, False, 1.5, "2"):
        untrusted = copy.deepcopy(good)
        case_id = untrusted["cases"][0]["id"]
        untrusted["cases"][0]["human_scores"]["task_alignment"] = invalid_score
        report = evaluator.evaluate_outputs(dataset, untrusted, require_human_scores=True)
        require(not report["passed"], f"invalid human score {invalid_score!r} must fail closed")
        require(
            bool(report["cases"][case_id]["errors"]),
            f"invalid human score {invalid_score!r} must produce an explicit case error",
        )

    # An integral JSON float is still numerically a valid whole rubric point.
    integer_float = copy.deepcopy(good)
    integer_float["cases"][0]["human_scores"]["task_alignment"] = 2.0
    report = evaluator.evaluate_outputs(dataset, integer_float, require_human_scores=True)
    require(report["passed"], "finite whole-number JSON float must remain accepted")

    # Invalid metadata cannot silently redefine the human quality gate.
    # NaN in particular bypassed the original threshold comparison because
    # `nan < threshold` and `nan > threshold` are both false.
    for key, invalid_values in {
        "score_min": (True, -1, float("nan")),
        "score_max": (False, 3, float("inf")),
        "normal_case_pass_total": (False, 0, 6, 7.5, float("nan")),
        "high_risk_case_pass_total": (True, 0, 7, 8.5, float("inf")),
        "mean_pass_total": (False, 0, 7.5, float("nan"), float("-inf")),
    }.items():
        for invalid in invalid_values:
            altered = copy.deepcopy(dataset)
            altered["human_rubric"][key] = invalid
            drift, _warnings = evaluator.validate_dataset(altered)
            require(
                any("human_rubric" in error for error in drift),
                f"rubric {key}={invalid!r} must fail closed",
            )
    missing_dims = copy.deepcopy(dataset)
    missing_dims["human_rubric"]["dimensions"] = ["task_alignment"]
    drift, _warnings = evaluator.validate_dataset(missing_dims)
    require(
        any("five V1 dimensions" in error for error in drift),
        "shrunk rubric must fail the canonical dimension contract",
    )

    # Exercise the attainable-score guard independently, with the canonical
    # dimensions intact so an earlier schema error cannot mask this check.
    for key in ("normal_case_pass_total", "high_risk_case_pass_total", "mean_pass_total"):
        impossible = copy.deepcopy(dataset)
        impossible["human_rubric"][key] = 11
        drift, _warnings = evaluator.validate_dataset(impossible)
        require(
            any("attainable maximum" in error for error in drift),
            f"rubric {key} above the five-dimension maximum must fail",
        )

    # Four dimensions still allow numeric 7/8/8 thresholds, but omit a
    # required sign-off criterion; the whole V1 rubric must be pinned.
    for bad_dims in (
        dataset["human_rubric"]["dimensions"][:-1],
        dataset["human_rubric"]["dimensions"][1:],
        dataset["human_rubric"]["dimensions"][:-1] + ["other_dimension"],
        list(reversed(dataset["human_rubric"]["dimensions"])),
    ):
        altered = copy.deepcopy(dataset)
        altered["human_rubric"]["dimensions"] = bad_dims
        drift, _warnings = evaluator.validate_dataset(altered)
        require(
            any("five V1 dimensions" in error for error in drift),
            "modified human rubric dimension set must fail even if thresholds are numerically feasible",
        )

    # Required contract lists must NEVER be empty. The old _is_string_list
    # accidentally allowed [] because Python's all([]) is True, which could
    # disable mandatory prompt clauses, feedback sections or forbidden phrases.
    required_lists = (
        ("prompt_contract", "required_clauses"),
        ("global_output_contract", "required_headings"),
        ("global_output_contract", "forbidden_phrases"),
        ("global_output_contract", "simplified_markers"),
        ("global_output_contract", "uncertainty_markers"),
        ("global_output_contract", "question_priority_markers"),
    )
    for block, key in required_lists:
        malformed = copy.deepcopy(dataset)
        malformed[block][key] = []
        drift, _warnings = evaluator.validate_dataset(malformed)
        require(
            any(f"{block}.{key}" in error for error in drift),
            f"required quality contract {block}.{key}=[] must fail closed",
        )

    # A Golden Set case may have zero must_mention_any groups. But when a
    # group is present, it must include at least one nonempty marker.
    empty_group = copy.deepcopy(dataset)
    empty_group["cases"][0]["expectations"]["must_mention_any"] = [[]]
    drift, _warnings = evaluator.validate_dataset(empty_group)
    require(
        any("must_mention_any" in error for error in drift),
        "empty must_mention_any marker group must fail closed",
    )

    empty_outer_groups = copy.deepcopy(dataset)
    empty_outer_groups["cases"][0]["expectations"]["must_mention_any"] = []
    drift, _warnings = evaluator.validate_dataset(empty_outer_groups)
    require(
        not drift,
        "an empty optional case-specific marker group LIST must remain valid",
    )

    prompt_drift = copy.deepcopy(dataset)
    prompt_drift["prompt_contract"]["guide_version"] = "deliberately-wrong-version"
    drift_errors, _ = evaluator.validate_dataset(prompt_drift)
    require(any("guide version drift" in error for error in drift_errors), "prompt version drift must fail")

    model_drift = copy.deepcopy(dataset)
    model_drift["model_contract"]["public_model"] = "deliberately/wrong-model"
    drift_errors, _ = evaluator.validate_dataset(model_drift)
    require(any("public model drift" in error for error in drift_errors), "public model drift must fail")

    print(f"Golden Set cases: {len(dataset['cases'])}")
    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")
    print("AI FEEDBACK EVAL SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
