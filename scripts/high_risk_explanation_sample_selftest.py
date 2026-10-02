#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_high_risk_explanation_sample.py"
spec = importlib.util.spec_from_file_location("high_risk_sampler", MODULE_PATH)
assert spec and spec.loader
sampler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampler)


def row(**overrides):
    base = {
        "id": "SP-115-1-040",
        "subject": "社會政策與社會立法",
        "year": "115",
        "round": "第一次",
        "qno": "40",
        "question": "依相關法規規定，下列何者不正確？",
        "opt_a": "甲",
        "opt_b": "乙",
        "opt_c": "丙",
        "opt_d": "丁",
        "answer": "D",
        "accepted_answers": None,
        "grading_mode": "standard",
        "analysis_status": "ready",
        "legal_status": "verified_current",
        "law": "兒童及少年未來教育與發展帳戶條例",
        "exp_why": "D 不符合題意。",
        "exp_others": "其餘選項符合規定。",
        "exp_trap": "注意反向題。",
        "mnemonic": "",
        "extension": "",
        "mistake": "忽略否定詞",
    }
    base.update(overrides)
    return base


assert sampler.registry_id("SP-115-1-040") == "SP115-1-40"
assert sampler.registry_id("SW-104-2-003") == "SW104-2-3"
assert sampler.registry_id("custom-id") == "custom-id"

assert sampler.accepted_answers(row(accepted_answers=["A", " C "])) == ["A", "C"]
assert sampler.accepted_answers(row(accepted_answers='["B","D"]')) == ["B", "D"]
assert sampler.accepted_answers(row(accepted_answers="A / C")) == ["A", "C"]
assert sampler.accepted_answers(row(accepted_answers=None)) == []

assert sampler.is_negative(row(question="下列何者錯誤？"))
assert sampler.is_negative(row(question="下列何者不適當？"))
assert not sampler.is_negative(row(question="下列何者正確？"))
assert not sampler.is_negative(row(question="不幸事件之處遇原則何者適當？")), "substring '不' alone must not create a negative-question hit"

assert sampler.is_numeric(row(question="補助上限為 10 萬元。"))
assert sampler.is_numeric(row(exp_why="服務對象年滿 65 歲。"))
assert sampler.is_numeric(row(law="比例不得低於 5%。"))
assert not sampler.is_numeric(row(question="本題提到第十條但沒有阿拉伯數字單位。", exp_why="概念題"))

assert sampler.is_multi_answer(row(accepted_answers=["A", "B"]))
assert not sampler.is_multi_answer(row(accepted_answers=["A"]))
assert sampler.is_special_grading(row(grading_mode="all_credit"))
assert not sampler.is_special_grading(row(grading_mode="standard"))

base = row()
core_hash = sampler.official_core_hash(base)
exp_hash = sampler.explanation_hash(base)

changed_exp = copy.deepcopy(base)
changed_exp["exp_why"] = "另一份平台解析。"
assert sampler.official_core_hash(changed_exp) == core_hash, "platform explanation must not alter Official Core hash"
assert sampler.explanation_hash(changed_exp) != exp_hash, "explanation hash must detect explanation changes"

changed_answer = copy.deepcopy(base)
changed_answer["answer"] = "A"
assert sampler.official_core_hash(changed_answer) != core_hash, "Official Core hash must detect answer changes"
assert sampler.explanation_hash(changed_answer) == exp_hash, "answer-only change must not be hidden in explanation hash"

changed_accept = copy.deepcopy(base)
changed_accept["accepted_answers"] = ["A", "D"]
assert sampler.official_core_hash(changed_accept) != core_hash, "Official Core hash must include accepted answers"

rank1 = sampler.hash_rank("negative_ready", base)
rank2 = sampler.hash_rank("negative_ready", copy.deepcopy(base))
rank3 = sampler.hash_rank("numeric_ready", base)
assert rank1 == rank2, "selection rank must be deterministic"
assert rank1 != rank3, "lane must be part of deterministic selection identity"

assert sampler.is_ready(base)
assert sampler.is_legal(base)
assert not sampler.is_legal(row(legal_status="not_applicable", law=""))

print("HIGH-RISK EXPLANATION SAMPLE SELFTEST OK")
