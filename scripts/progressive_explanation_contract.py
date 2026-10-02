#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = (ROOT / "monthly_patch_parts" / "zzzz_product_v1_lock.part").read_text(encoding="utf-8")
PROGRESSIVE = (ROOT / "monthly_patch_parts" / "zzzzz_progressive_explanation.part").read_text(encoding="utf-8")
LOOP = (ROOT / "monthly_patch_parts" / "70.learning-loop.part").read_text(encoding="utf-8")
BASE = (ROOT / "monthly_patch_parts" / "00.part").read_text(encoding="utf-8")

# Existing canonical answer / disclosure owner must remain intact.
assert "swsi-answer-line" in LOCK
assert "看完整解析" in LOCK
assert "/其他選項|考場陷阱/" in LOCK
assert "querySelectorAll(':scope > .extra')" in LOCK

# Base renderer still owns explanation data; this patch only changes presentation.
for marker in ("item.exp.why", "item.exp.others", "item.exp.trap", "item.mnemonic", "item.law", "item.mistake"):
    assert marker in BASE, f"base explanation source disappeared: {marker}"

# Layer 1: deterministic concise reason, never a second AI/generated explanation.
assert "SWSI Progressive Explanation V1 2026-10-03" in PROGRESSIVE
assert "function concise(text)" in PROGRESSIVE
assert "一句核心原因" in PROGRESSIVE
assert "text.textContent=summary" in PROGRESSIVE
assert "exp.dataset.swsiCompact!=='1'" in PROGRESSIVE

# Layer 2: remaining full explanation sections move under the canonical disclosure.
assert "ensureDetails(exp)" in PROGRESSIVE
assert "secs=directChildren(exp,'.exp-sec')" in PROGRESSIVE
assert "body.insertBefore(secs[i],body.firstChild)" in PROGRESSIVE
assert "看完整解析" in PROGRESSIVE

# Personal wrong-cause reflection remains outside the collapsed layer.
assert "這題你為什麼會錯？" in LOOP
assert "swsi-self-cause" in LOOP
assert "keepReflectionOutside(exp)" in PROGRESSIVE
assert "exp.insertBefore(cause,details)" in PROGRESSIVE

# No unsafe feature creep in the presentation layer.
for forbidden in ("fetch(", "supabase", "localStorage.setItem", "sessionStorage.setItem", "innerHTML=summary"):
    assert forbidden not in PROGRESSIVE, f"unexpected progressive-layer side effect: {forbidden}"

print("PROGRESSIVE EXPLANATION CONTRACT OK: concise layer 1 + complete layer 2 + visible self-reflection")
