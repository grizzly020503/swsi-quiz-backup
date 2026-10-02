#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "monthly_patch_parts" / "71.my-learning-center.part"
HOME = ROOT / "monthly_patch_parts" / "20.product-philosophy.part"
LOOP = ROOT / "monthly_patch_parts" / "70.learning-loop.part"

hub = HUB.read_text(encoding="utf-8")
home = HOME.read_text(encoding="utf-8")
loop = LOOP.read_text(encoding="utf-8")

required = {
    "short": ("我只有 10 分鐘", "swsiLearningAction('short')"),
    "weak": ("我要補最弱科", "swsiLearningAction('weak')"),
    "mock": ("我要做完整考卷", "swsiLearningAction('mock')"),
    "essay": ("我要練申論", "swsiLearningAction('essay')"),
    "review": ("我要複習錯題", "swsiLearningAction('review')"),
}

for key, (label, action) in required.items():
    marker = f'data-swsi-scenario=\\"{key}\\"'
    assert marker in hub, f"missing scenario marker: {key}"
    assert label in hub, f"missing student-facing scenario label: {label}"
    assert action in hub, f"scenario {key} is not mapped to the expected existing action"

markers = re.findall(r'data-swsi-scenario=\\"([^\\"]+)\\"', hub)
assert markers == ["short", "weak", "mock", "essay", "review"], (
    f"scenario set/order drifted: {markers}"
)

assert "你現在想做什麼？" in hub
assert "不用先理解平台功能名稱" in hub
assert "先花 10 分鐘練 10 題" in hub

# 10-minute scenario must reuse the canonical 10-question owner from the homepage.
assert "if(kind==='short'){if(typeof window.swsiStartNow==='function')window.swsiStartNow()" in hub
assert "window.swsiStartNow=function()" in home
assert "homeQuizCount=10" in home

# Weak-subject scenario must route to the existing progress/weakness computation,
# not create a second recommendation engine.
assert "if(kind==='weak'){if(typeof go==='function')go('progress')" in hub
assert "var weak=subjects.filter(function(x){return x.t>=5;})[0]||subjects[0]" in loop
assert "swsiPracticeSubject" in loop
assert "目前最值得補" in loop

# Full-paper scenario must reuse the existing mock-exam owner.
assert "if(kind==='mock'){if(window.MK&&typeof window.MK.open==='function')window.MK.open()" in hub
assert "MK.open()" in home

# Essay/review mappings stay on their existing owners.
assert "swsiOpenEssay" in hub
assert "go('essay')" in hub
assert "go('review')" in hub

# Do not invent a fake unfinished-session promise while no durable session contract exists.
assert "繼續上次" not in hub

print("STUDENT LEARNING SCENARIOS CONTRACT OK: 5 task-oriented mappings reuse existing runtime owners")
