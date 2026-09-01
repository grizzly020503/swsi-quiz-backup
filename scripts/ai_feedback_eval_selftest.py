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

    missing_case = copy.deepcopy(good)
    missing_case["cases"] = missing_case["cases"][:-1]
    report = evaluator.evaluate_outputs(dataset, missing_case, require_human_scores=True)
    require(not report["passed"], "missing Golden Set output must fail closed")
    require(report["payload_errors"], "missing Golden Set output must produce payload error")

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
