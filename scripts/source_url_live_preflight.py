#!/usr/bin/env python3
"""Read-only production preflight for an exact, pinned 3,920-link correction.

Never updates Supabase, deploys a site, or approves release. The only live read
uses the existing public read-only question API, with no service-role secret.
Checks ALL 31 columns exported by the normal shard builder, not just grading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from build_question_shards import SELECT_FIELDS, fetch_questions
from source_url_exact_target_replay import verify

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROWS = 4800
EXPECTED_URL_EDITS = 3920
DATA_FIELDS = tuple(key for key in SELECT_FIELDS if key != "source_url")


def index(rows: list[dict], label: str, expected_rows: int) -> dict[str, dict]:
    if len(rows) != expected_rows:
        raise ValueError(f"{label}: expected {expected_rows} rows, got {len(rows)}")
    by_id = {}
    for row in rows:
        ident = row.get("id") if isinstance(row, dict) else None
        if not isinstance(ident, str) or not ident or ident in by_id:
            raise ValueError(f"{label}: absent/duplicate row ID")
        if any(field not in row for field in SELECT_FIELDS):
            raise ValueError(f"{label}: missing a required shard field: {ident}")
        by_id[ident] = row
    return by_id


def check_live(live: list[dict], original: list[dict], corrected: list[dict],
               *, total: int = EXPECTED_ROWS, edits: int = EXPECTED_URL_EDITS) -> dict:
    old, new, prod = (index(rows, label, total) for rows, label in (
        (original, "pinned old question rows"),
        (corrected, "proposed question rows"),
        (live, "current public questions")))
    if old.keys() != new.keys() or new.keys() != prod.keys():
        raise ValueError("source-only promotion cannot add/remove any question IDs")
    before, after, unaffected = 0, 0, 0
    changed_fields = []
    unexpected_url = []
    for ident in sorted(old):
        old_row, new_row, live_row = old[ident], new[ident], prod[ident]
        for field in DATA_FIELDS:
            if (old_row[field] != new_row[field] or
                    live_row[field] != new_row[field]):
                changed_fields.append((ident, field))
        a, b, observed = old_row["source_url"], new_row["source_url"], live_row["source_url"]
        if a == b:
            if observed != a:
                unexpected_url.append(ident)
            unaffected += 1
        elif observed == a:
            before += 1
        elif observed == b:
            after += 1
        else:
            unexpected_url.append(ident)
    if changed_fields or unexpected_url:
        raise RuntimeError(
            f"BLOCKED: non-URL field drift={len(changed_fields)}, "
            f"unexpected URLs={len(unexpected_url)}. "
            f"sample fields={changed_fields[:5]}, urls={unexpected_url[:5]}")
    if before + after != edits or unaffected != total - edits:
        raise RuntimeError(
            f"BLOCKED: correction scope differs: before={before} after={after} "
            f"unchanged={unaffected}, expected edits={edits} total={total}")
    if before and after:
        raise RuntimeError(
            f"BLOCKED: partial production cutover detected (before={before}, after={after}); "
            "do not silently repair or auto-approve")
    return {
        "status": "PREFLIGHT_PASS_NOT_PRODUCTION_APPROVAL",
        "live_state": "BEFORE_ONLY" if before else "AFTER_ONLY",
        "public_question_rows_read": total,
        "fields_verified_except_source_url": len(DATA_FIELDS),
        "non_url_field_mismatches": 0,
        "source_url_pending": before,
        "source_url_target": after,
        "source_url_unaffected": unaffected,
        "source_url_unknown": 0,
        "production_write": False,
        "merge_or_deploy_authorized": False,
        "official_pdf_text_and_ai_human_approved": False,
    }


def session_rows(root: Path) -> list[dict]:
    rows = []
    for year in range(104, 116):
        for rd in (1, 2):
            path = root / f"cdn/question-shards/{year}-{rd}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("question_count") != 200 or len(data.get("questions", [])) != 200:
                raise ValueError(f"incomplete staged shard: {path.name}")
            rows.extend(data["questions"])
    return rows


def selftest() -> None:
    def example(ident, url):
        return {key: (ident if key == "id" else None) for key in DATA_FIELDS} | {"source_url": url}
    old = [example("A", "old"), example("B", "same"), example("C", "old")]
    new = [example("A", "new"), example("B", "same"), example("C", "new")]
    ok = check_live(old, old, new, total=3, edits=2)
    assert ok["live_state"] == "BEFORE_ONLY" and ok["source_url_pending"] == 2
    ok = check_live(new, old, new, total=3, edits=2)
    assert ok["live_state"] == "AFTER_ONLY" and ok["source_url_target"] == 2
    def blocked(current, phrase):
        try:
            check_live(current, old, new, total=3, edits=2)
        except (RuntimeError, ValueError) as exc:
            assert phrase in str(exc), str(exc)
            return
        raise AssertionError(f"must reject: {phrase}")
    blocked([new[0], old[1], old[2]], "partial production cutover")
    altered = [dict(x) for x in old]
    altered[0]["source_url"] = "unregistered URL"
    blocked(altered, "unexpected URLs")
    altered = [dict(x) for x in old]
    altered[1]["question"] = "unaudited question change"
    # Synthetic entries deliberately include all real SELECT_FIELDS to catch
    # accidental weakening of the check when build_question_shards adds fields.
    for row in old + new + altered:
        for field in SELECT_FIELDS:
            row.setdefault(field, None)
    blocked(altered, "non-URL field drift")
    blocked(old[:-1], "expected 3 rows")
    print("SOURCE-ONLY LIVE PARITY SELFTEST OK: old/new, partial, unknown URL, official text drift, missing row rejected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--live", action="store_true", help="READ ONLY: query existing public.questions with anon API")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.live:
        parser.error("explicit --live or --selftest required; no implicit network calls")
    with TemporaryDirectory(prefix="swsi-source-only-preflight-") as temp:
        old_path = Path(temp) / "pinned-before"
        offline = verify(ROOT, old_path)
        if offline["changed_source_urls"] != EXPECTED_URL_EDITS:
            raise RuntimeError("offline SHA-pinned source correction proof failed")
        original, corrected = session_rows(old_path), session_rows(ROOT)
        current = [row for row in fetch_questions() if row.get("year") in {str(y) for y in range(104, 116)}]
        result = check_live(current, original, corrected)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
