#!/usr/bin/env python3
"""Build a privacy-safe public legal-watch snapshot from the reviewed MOJ report.

The source report may contain operational lookup diagnostics. The public artifact
only exposes aggregate state and official law metadata needed by Monitoring V2.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_record(row: dict) -> dict:
    return {
        "name": str(row.get("canonical_name") or "").strip(),
        "official_url": str(row.get("official_url") or "").strip() or None,
        "official_modified_date": row.get("official_modified_date"),
        "previous_modified_date": row.get("previous_modified_date"),
        "changed": bool(row.get("changed")),
        "abandon_note": row.get("abandon_note"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/legal_watch_report.json")
    ap.add_argument("--output", default="auto/legal_watch.json")
    args = ap.parse_args()

    report = load(args.input)
    records = [safe_record(x) for x in (report.get("records") or []) if isinstance(x, dict)]
    found = [x for x in records if x.get("official_url")]
    changed = [x for x in found if x.get("changed")]
    recent = sorted(
        found,
        key=lambda x: str(x.get("official_modified_date") or ""),
        reverse=True,
    )[:8]

    public = {
        "schema_version": 1,
        "checked_at": report.get("checked_at"),
        "baseline": bool(report.get("baseline")),
        "source_label": "全國法規資料庫",
        "watch_count": int(report.get("watch_count") or len(records)),
        "matched_count": int(report.get("matched_count") or len(found)),
        "missing_count": int(report.get("missing_count") or 0),
        "changed_count": int(report.get("changed_count") or len(changed)),
        "changes": changed,
        "recently_modified": recent,
    }

    if public["watch_count"] < 20 or public["matched_count"] < 20:
        raise SystemExit("legal watch snapshot refuses an implausibly small official baseline")
    if public["changed_count"] != len(changed):
        raise SystemExit("legal watch changed_count does not match changed records")
    for row in found:
        url = row.get("official_url") or ""
        if not url.startswith("https://law.moj.gov.tw/"):
            raise SystemExit(f"unexpected public legal source: {url}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    old = None
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            old = None
    if old == public:
        print(f"Public legal-watch snapshot unchanged: {public['matched_count']}/{public['watch_count']} matched")
        return 0

    out.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Public legal-watch snapshot updated: "
        f"{public['matched_count']}/{public['watch_count']} matched, changed={public['changed_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
