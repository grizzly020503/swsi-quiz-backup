#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOOP = (ROOT / "monthly_patch_parts" / "70.learning-loop.part").read_text(encoding="utf-8")
KNOW = (ROOT / "monthly_patch_parts" / "80.knowledge-path.part").read_text(encoding="utf-8")

# Preserve the existing wrong-answer reflection + spaced-review owners.
for marker in (
    "swsi_wrong_cause_v1",
    "這題你為什麼會錯？",
    "startDueReview()",
    "swsiPracticeReviewSet",
):
    assert marker in LOOP, f"learning-loop foundation disappeared: {marker}"

# Explainable trigger: repeated wrong topic, not a model recommendation.
assert "focusTopic=topTopics.find(function(x){return x[1]>=2;})||null" in LOOP
assert "不是黑箱 AI 推薦" in LOOP

# Due spaced review stays higher priority than the new topic recommendation.
due_pos = LOOP.index("if(rv.dueCount)action=")
focus_pos = LOOP.index("else if(focusTopic)action=")
assert due_pos < focus_pos, "due review must remain higher priority than repeated-topic recommendation"

# Reuse the existing Knowledge Path rather than creating a parallel curriculum store.
assert "window.swsiOpenTopicMaterial=function(topic)" in LOOP
assert "window.swsiKnowledgeSearch" in LOOP
assert "window.swsiKnowledgeSearch=function(q)" in KNOW
assert "先看相關教材" in LOOP

# The loop must end in a bounded same-topic retest, not an open-ended adaptive run.
assert "練 5 題確認" in LOOP
assert "swsiPracticeTopic(\\''+H(focusTopic[0])+'\\',5)" in LOOP
assert "swsiPracticeTopic(\\''+H(x[0])+'\\',5)" in LOOP

# This layer may use local learning history, but must not gain network/DB/model authority.
for forbidden in ("fetch(", "supabase", "service_role", "openai", "anthropic", "gemini"):
    assert forbidden not in LOOP.lower(), f"unexpected authority in local learning loop: {forbidden}"

print("LEARNING LOOP CLOSED CONTRACT OK: repeated-topic evidence -> existing knowledge path -> five-question retest; due review remains first")
