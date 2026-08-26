#!/usr/bin/env python3
"""Build a compact admin/dashboard payload from unified_question_qa.py output.

The dashboard payload intentionally omits the full question list.  It contains
only aggregate counts plus actionable anomalies, so admin clients do not need to
load hundreds or thousands of question/audit records just to render a health
screen.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reason_rows(item: dict) -> list[dict]:
    out = []
    for issue in item.get("issues") or []:
        if issue.get("status") not in {"needs_review", "blocked"}:
            continue
        out.append(
            {
                "layer": issue.get("layer"),
                "rule": issue.get("rule"),
                "status": issue.get("status"),
                "message": issue.get("message"),
            }
        )
    return out


def build_dashboard(report: dict) -> dict:
    items = report.get("items") or []
    overall = report.get("overall") or {}

    actions = []
    generation_by_kind = Counter()
    generation_by_subject = Counter()
    ready_by_kind = Counter()

    for item in items:
        kind = str(item.get("kind") or "unknown")
        subject = str(item.get("subject") or "unknown")
        generation_state = str(item.get("generation_state") or "")

        if generation_state == "pending_generation":
            generation_by_kind[kind] += 1
            generation_by_subject[subject] += 1
        elif generation_state == "ready":
            ready_by_kind[kind] += 1

        official = str(item.get("official_status") or "passed")
        enrichment = str(item.get("enrichment_status") or "passed")
        if official not in {"needs_review", "blocked"} and enrichment not in {"needs_review", "blocked"}:
            continue

        official_risk = str(item.get("official_risk") or "low")
        enrichment_risk = str(item.get("enrichment_risk") or "low")
        max_risk = max(
            (official_risk, enrichment_risk),
            key=lambda r: RISK_RANK.get(r, -1),
        )
        actions.append(
            {
                "id": item.get("id"),
                "kind": kind,
                "subject": subject,
                "qno": item.get("qno"),
                "official_status": official,
                "enrichment_status": enrichment,
                "risk": max_risk,
                "reasons": reason_rows(item),
            }
        )

    actions.sort(
        key=lambda x: (
            -RISK_RANK.get(str(x.get("risk") or "low"), -1),
            0 if x.get("official_status") == "blocked" else 1,
            str(x.get("subject") or ""),
            str(x.get("qno") or ""),
        )
    )

    official = overall.get("official_core") or {}
    enrichment = overall.get("enrichment") or {}
    total = int(overall.get("items") or len(items))
    passed = int(official.get("passed") or 0)
    official_health_pct = round((passed / total * 100.0), 2) if total else 0.0

    blocked_count = sum(
        1
        for x in actions
        if x.get("official_status") == "blocked" or x.get("enrichment_status") == "blocked"
    )
    review_count = len(actions) - blocked_count

    if blocked_count:
        health = "blocked"
    elif review_count:
        health = "needs_review"
    else:
        health = "healthy"

    return {
        "schema_version": 1,
        "year": report.get("year"),
        "round": report.get("round"),
        "health": health,
        "official_health_pct": official_health_pct,
        "official_core": {
            "total": total,
            "passed": int(official.get("passed") or 0),
            "needs_review": int(official.get("needs_review") or 0),
            "blocked": int(official.get("blocked") or 0),
            "release_ready": bool(official.get("release_ready")),
        },
        "enrichment": {
            "passed": int(enrichment.get("passed") or 0),
            "needs_review": int(enrichment.get("needs_review") or 0),
            "blocked": int(enrichment.get("blocked") or 0),
        },
        "human_queue": {
            "total": len(actions),
            "blocked": blocked_count,
            "needs_review": review_count,
            "items": actions,
        },
        "generation_backlog": {
            "total": sum(generation_by_kind.values()),
            "by_kind": dict(sorted(generation_by_kind.items())),
            "by_subject": dict(sorted(generation_by_subject.items())),
            "ready_by_kind": dict(sorted(ready_by_kind.items())),
        },
        "legal_watch": report.get("legal_watch"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build compact SWSI QA dashboard JSON")
    ap.add_argument("report", type=Path, help="unified_question_qa.py JSON report")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    dashboard = build_dashboard(read_json(args.report))
    rendered = json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
