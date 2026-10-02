#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = (ROOT / "monthly_patch_parts" / "zzzz_product_v1_lock.part").read_text(encoding="utf-8")
LOOP = (ROOT / "monthly_patch_parts" / "70.learning-loop.part").read_text(encoding="utf-8")
BASE = (ROOT / "monthly_patch_parts" / "00.part").read_text(encoding="utf-8")
PARTS = ROOT / "monthly_patch_parts"

# Progressive disclosure must stay inside the existing Product V1 owner instead
# of growing another late runtime patch layer.
assert not (PARTS / "zzzzz_progressive_explanation.part").exists(), "progressive explanation must not add a new z-layer runtime part"

# Existing canonical answer / disclosure owner remains the single presentation owner.
assert "swsi-answer-line" in LOCK
assert "看完整解析" in LOCK
assert "querySelectorAll(':scope > .extra')" in LOCK

# Base renderer still owns explanation data; this change only adjusts presentation.
for marker in ("item.exp.why", "item.exp.others", "item.exp.trap", "item.mnemonic", "item.law", "item.mistake"):
    assert marker in BASE, f"base explanation source disappeared: {marker}"

# Layer 1: deterministic concise reason from already-rendered text, never a new AI explanation.
assert "function conciseExplanation(text)" in LOCK
assert "一句核心原因" in LOCK
assert "coreText.textContent=summary" in LOCK
assert "swsi-core-reason" in LOCK

# Layer 2: all direct explanation sections plus mnemonic/law extras move under one disclosure.
assert "var hidden=secs.slice()" in LOCK
assert "hidden.forEach(function(x){body.appendChild(x);})" in LOCK
assert "details.className='swsi-explanation-more'" in LOCK

# Personal wrong-cause reflection remains visible outside the collapsed notes.
assert "這題你為什麼會錯？" in LOOP
assert "swsi-self-cause" in LOOP
assert "var detailsNow=directChild(exp,'.swsi-explanation-more')" in LOCK
assert "exp.insertBefore(cause,detailsNow)" in LOCK

# No unsafe feature creep in this existing presentation owner.
for forbidden in ("fetch(", "supabase", "localStorage.setItem", "sessionStorage.setItem", "innerHTML=summary"):
    assert forbidden not in LOCK, f"unexpected progressive-layer side effect: {forbidden}"

print("PROGRESSIVE EXPLANATION CONTRACT OK: existing product owner keeps concise layer 1 + complete layer 2 + visible self-reflection")
