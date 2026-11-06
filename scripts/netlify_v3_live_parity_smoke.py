#!/usr/bin/env python3
"""Fail-closed read-only exact V3 stylesheet parity for Netlify releases."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

STYLE = re.compile(r'<style id="swsi-calm-learning-ui-v3">(.*?)</style>', re.DOTALL)


def extract(html: str) -> str:
    found = STYLE.findall(html)
    if len(found) != 1:
        raise ValueError(f"expected exactly one V3 style, got {len(found)}")
    return found[0]


def verify(expected: str, actual: str) -> None:
    if extract(expected) != extract(actual):
        raise ValueError("hosted V3 stylesheet differs from approved build")


def self_test() -> None:
    good = '<style id="swsi-calm-learning-ui-v3">--paper:#F7F9F7;</style>'
    verify(good, good)
    for bad in (good.replace("#F7F9F7", "#FFFFFF"), "<html>old</html>", good + good):
        try:
            verify(good, bad)
        except ValueError:
            continue
        raise AssertionError("stale, missing or duplicate V3 CSS was accepted")
    print("NETLIFY V3 STYLE PARITY SELFTEST OK")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected", type=Path)
    p.add_argument("--actual", type=Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.expected or not args.actual:
        p.error("--expected and --actual are both required")
    try:
        verify(args.expected.read_text(encoding="utf-8"),
               args.actual.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise SystemExit("NETLIFY LIVE V3 STYLE PARITY NO-GO: " + str(exc)) from None
    print("NETLIFY LIVE V3 STYLE PARITY OK: exact reviewed CSS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
