#!/usr/bin/env python3
"""Fail-closed IA contract for the SWSI student homepage (#307).

This is intentionally a source-level, zero-network check. It protects the
existing subtraction-first homepage from growing back into a feature wall and
prevents a cosmetic "resume" entry from being added before a durable quiz
session contract exists.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "monthly_patch_parts" / "20.product-philosophy.part"


def fail(message: str) -> None:
    raise SystemExit(f"STUDENT HOME IA CONTRACT FAILED: {message}")


def require_count(text: str, marker: str, expected: int, label: str) -> None:
    actual = text.count(marker)
    if actual != expected:
        fail(f"{label}: expected {expected}, found {actual}")


def main() -> int:
    text = HOME.read_text(encoding="utf-8")

    # One primary study card only. Advanced scope stays inside that card rather
    # than becoming another top-level feature area.
    require_count(text, '<section class="swsi-focus-primary">', 1, "primary study card")
    require_count(text, '<div class="swsi-home-quick">', 1, "quick-action row")
    require_count(text, 'class="swsi-home-resource"', 1, "low-interference resource entry")

    # Existing first-screen action owners. Adding another top-level action must
    # be an explicit IA decision, not an incidental feature addition.
    for marker, label in (
        ('onclick="swsiStartNow()"', "primary practice action"),
        ('onclick="toggleHomeQuiz()"', "advanced-range disclosure"),
        ('onclick="swsiOpenHomeReview()"', "review action"),
        ('onclick="MK.open()"', "mock-exam action"),
        ('onclick="go(\\\'topics\\\')"', "resource action"),
    ):
        require_count(text, marker, 1, label)

    # The primary CTA count and the actual start contract must agree. The exact
    # number may intentionally move from 20 to 10 later; drift is what is banned.
    start = re.search(r"swsiStartNow=function\(\)\{.*?homeQuizCount=(\d+);", text, re.S)
    button = re.search(r">直接開始\s+(\d+)\s+題</button>", text)
    heading = re.search(r"<h2>(\d+)\s*題[^<]*</h2>", text)
    if not start or not button or not heading:
        fail("primary practice count markers are incomplete")
    counts = {int(start.group(1)), int(button.group(1)), int(heading.group(1))}
    if len(counts) != 1:
        fail(f"primary practice count drift: {sorted(counts)}")
    count = counts.pop()
    if count not in {10, 20, 40}:
        fail(f"primary practice count must use an existing supported size, got {count}")

    # Current product has answer history/review persistence, not a durable
    # unfinished-quiz session. Do not create a misleading button before the
    # session state, version/fingerprint and expiry/fail-closed behavior exist.
    forbidden_resume_copy = ("繼續上次", "繼續作答", "繼續未完成")
    if any(copy in text for copy in forbidden_resume_copy):
        fail("resume copy appeared before a durable unfinished-quiz session contract exists")

    # Engineering terms should not leak into the focused homepage copy.
    rendered_home = text[text.find("app.innerHTML=offlineNote+") : text.find("if(typeof relabelTabs")]
    for term in ("shard", "canonical", "runtime", "manifest", "fingerprint"):
        if term.lower() in rendered_home.lower():
            fail(f"engineering term leaked into student homepage: {term}")

    print(
        "STUDENT HOME IA CONTRACT OK "
        f"primary_count={count} primary_cards=1 quick_row=1 resource_entries=1 resume=disabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
