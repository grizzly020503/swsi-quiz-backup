#!/usr/bin/env python3
"""Fail-closed homepage IA contract for SWSI Calm Learning V4."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "monthly_patch_parts" / "20.product-philosophy.part"
BUILD = ROOT / "cdn" / "monthly_patch.js"


def fail(message: str) -> None:
    raise SystemExit("STUDENT HOME IA CONTRACT FAILED: " + message)


def require_count(source: str, token: str, count: int, label: str) -> None:
    found = source.count(token)
    if found != count:
        fail(f"{label}: expected {count}, found {found}")


def main() -> int:
    text = HOME.read_text(encoding="utf-8")
    built = BUILD.read_text(encoding="utf-8")
    if text not in built:
        fail("canonical homepage source diverged from deployed monthly_patch.js")

    require_count(text, '<section class="swsi-focus-hero swsi-focus-primary swsi-v4-hero">',
                  1, "single primary learning hero")
    require_count(text, '<div class="swsi-v4-study-paths">', 1, "two study paths section")
    require_count(text, '<section class="swsi-v4-tools">', 1, "three optional study tools section")
    require_count(text, 'class="swsi-v4-path"', 2, "historical and essay study cards")
    require_count(text, 'class="swsi-v4-start"', 1, "one prominent primary CTA")

    for marker, label in (
        ('onclick="swsiStartNow()"', "start short practice"),
        ('onclick="toggleHomeQuiz()"', "disclose official past exam filters"),
        ('onclick="swsiOpenHomeReview()"', "review existing missed questions"),
        ('onclick="MK.open()"', "mock exam entry"),
        ('onclick="go(\\\'topics\\\')" ', "more learning tools entry"),
        ('onclick="go(\\\'essay\\\')" ', "essay practice entry"),
        ('onclick="go(\\\'progress\\\')" ', "weakness analysis entry"),
    ):
        if marker not in text:
            fail("missing functional route: " + label)

    if "homeQuizCount=10" not in text:
        fail("short-practice route no longer owns its 10-question contract")
    if not all(s in text for s in (
        "今天，從一題開始。", "歷屆試題", "申論練習", "模擬考", "錯題本", "弱點分析"
    )):
        fail("approved homepage hierarchy or copy missing")

    forbidden = ("繼續上次", "繼續作答", "繼續未完成")
    if any(s in text for s in forbidden):
        fail("unverified resume-session promise introduced")

    region_start = text.find("app.innerHTML=offlineNote+")
    region_end = text.find("if(typeof relabelTabs", region_start)
    if region_start < 0 or region_end <= region_start:
        fail("actual homepage renderer not found")
    region = text[region_start:region_end].lower()
    for word in ("shard", "canonical", "runtime", "manifest", "fingerprint"):
        if word in region:
            fail("engineering term leaked into student homepage: " + word)

    print("STUDENT HOME IA CONTRACT OK primary=1 historical=1 essay=1 optional_tools=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
