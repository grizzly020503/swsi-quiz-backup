#!/usr/bin/env python3
"""Proof-bound, URL-only historical MOEX repair proposals. No production writes.

Every proposed URL uses a PDF-header-verified source record. Wrong exam codes,
untrusted URLs, incomplete papers and changed grading remain human-held.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from historical_source_url_guard import (
    ROOT, load_registry, url_identity, validate_historical_source_urls,
)

HISTORICAL_YEARS = {str(y) for y in range(104, 116)}
ROUNDS = {"第一次": "1", "第二次": "2"}


def load_local_shards(root: Path = ROOT) -> list[dict]:
    """Read SHA-verified CDN artifacts without reading the production DB."""
    base = root / "cdn/question-shards"
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("shards")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest must contain shards")
    rows = []
    for entry in entries:
        name = entry.get("file") if isinstance(entry, dict) else None
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json"):
            raise ValueError("invalid manifest shard filename")
        raw = (base / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
            raise ValueError(f"manifest shard SHA mismatch: {name}")
        payload = json.loads(raw)
        questions = payload.get("questions") if isinstance(payload, dict) else None
        if not isinstance(questions, list) or len(questions) != entry.get("question_count"):
            raise ValueError(f"shard count mismatch: {name}")
        rows.extend(questions)
    return rows


def propose(rows: list[dict], *, registry_path: Path | None = None) -> dict[str, Any]:
    """Make exact URL-only candidates; refuse ambiguous/partial evidence."""
    if not isinstance(rows, list):
        raise ValueError("questions must be a JSON array")
    registry = load_registry(registry_path) if registry_path is not None else load_registry()
    seen: set[str] = set()
    observed: Counter[tuple[str, str]] = Counter()
    proposed: list[dict] = []
    historical: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("question row must be an object")
        ident = row.get("id")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("missing or duplicate question ID")
        seen.add(ident)
        year = str(row.get("year") or "")
        if year not in HISTORICAL_YEARS:
            continue  # Future exams use the separately approved exam-scheme registry.
        rd = ROUNDS.get(row.get("round"))
        key = (f"{year}-{rd}", str(row.get("subject") or ""))
        if rd is None or key not in registry:
            raise ValueError(f"unverified historical session/subject for {ident}")
        expected = registry[key]
        observed[key] += 1
        code = expected["exam_code"]
        if row.get("source_exam_code") != code:
            raise ValueError(f"official exam_code disagreement: {ident}")
        old = row.get("source_url")
        try:
            actual = url_identity(old)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"unsafe or malformed source URL: {ident}") from exc
        if actual[0] != code:
            raise ValueError(f"source URL points to wrong exam_code: {ident}")
        wanted = (code, str(expected["c"]), str(expected["s"]))
        if actual != wanted:
            proposed.append({
                "id": ident, "session": key[0], "subject": key[1],
                "before": old, "after": expected["url"],
                "official_pdf_sha256": expected["pdf_sha256"],
                "field": "source_url", "release_approved": False,
            })
        historical.append(row)
    if set(observed) != set(registry) or any(n != 40 for n in observed.values()) or len(historical) != 4800:
        raise ValueError("historical coverage incomplete: require 120 papers x 40 MCQs")
    proposed.sort(key=lambda item: item["id"])
    changes = {item["id"]: item["after"] for item in proposed}
    candidate = [
        ({**row, "source_url": changes[row["id"]]} if row["id"] in changes else row)
        for row in historical
    ]
    # Reuse the established guard: candidate must match all 120 verified papers.
    validate_historical_source_urls(
        candidate, registry_path=registry_path or ROOT / "data/moex_source_subjects.v1.json"
    )
    return {
        "schema_version": 1,
        "status": "REVIEW_REQUIRED_NOT_APPLIED" if proposed else "NO_CHANGE",
        "source": "pdf_header_index_matched_official_registry",
        "historical_rows_checked": len(historical),
        "verified_papers": len(registry),
        "proposed_url_changes": len(proposed),
        "changed_fields": ["source_url"] if proposed else [],
        "official_core_other_fields_changed": 0,
        "production_written": False,
        "release_approved": False,
        "patches": proposed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="JSON list of exported question records")
    source.add_argument("--live", action="store_true", help="explicit anon READ ONLY production API")
    parser.add_argument("--out", type=Path, help="write review-only JSON outside the repo")
    parser.add_argument("--fail-on-proposals", action="store_true", help="monthly QA blocks if official URL drift is found")
    args = parser.parse_args()
    if args.live:
        from build_question_shards import fetch_questions
        rows = fetch_questions()
    elif args.input:
        rows = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        rows = load_local_shards()
    report = propose(rows)
    if args.out:
        out = args.out.resolve()
        if out == ROOT or ROOT in out.parents:
            raise SystemExit("REFUSED: proposal output must be outside the Git repository")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "patches"}, ensure_ascii=False))
    return 2 if args.fail_on_proposals and report["proposed_url_changes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
