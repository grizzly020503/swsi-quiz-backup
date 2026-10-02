#!/usr/bin/env python3
"""Static fail-closed checks for #269 review-queue RPC candidate SQL."""
from __future__ import annotations

import argparse
from pathlib import Path


def require(text: str, needle: str) -> None:
    if needle.lower() not in text.lower():
        raise AssertionError(f"missing required review SQL contract: {needle}")


def reject(text: str, needle: str) -> None:
    if needle.lower() in text.lower():
        raise AssertionError(f"forbidden review SQL contract present: {needle}")


def validate(path: Path) -> dict[str, int | bool]:
    text = path.read_text(encoding="utf-8")
    for needle in [
        "create or replace function public.swsi_ops_upsert_review_item",
        "create or replace function public.swsi_ops_touch_review_item",
        "create or replace function public.swsi_ops_resolve_review_item",
        "for update",
        "if v_row.state = 'open'",
        "attempt = attempt + 1",
        "review item already terminal with different resolution",
        "revoke all on function public.swsi_ops_upsert_review_item",
        "grant execute on function public.swsi_ops_upsert_review_item",
        "to service_role",
    ]:
        require(text, needle)
    reject(text, "security definer")
    reject(text, "to anon;")
    reject(text, "to authenticated;")
    return {
        "ok": True,
        "bytes": len(text.encode("utf-8")),
        "functions": text.lower().count("create or replace function"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    args = p.parse_args()
    print(validate(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
