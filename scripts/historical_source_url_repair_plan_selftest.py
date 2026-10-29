#!/usr/bin/env python3
"""End-to-end regression against the real 4,800 read-only local shard rows."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from historical_source_url_repair_plan import load_local_shards, propose


def altered_url(url: str, *, s: str) -> str:
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query))
    params["s"] = s
    return urlunsplit(parts._replace(query=urlencode(params)))


def must_reject(rows: list[dict], phrase: str) -> None:
    try:
        propose(rows)
    except (ValueError, RuntimeError) as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"did not reject: {phrase}")


def main() -> int:
    rows = load_local_shards()
    assert len(rows) == 4800
    no_change = propose(rows)
    assert no_change["status"] == "NO_CHANGE" and no_change["proposed_url_changes"] == 0

    index = next(i for i, r in enumerate(rows) if str(r["year"]) == "112"
                 and r["round"] == "第一次"
                 and r["subject"] == "社會政策與社會立法")
    original = rows[index]
    changed = [dict(r) for r in rows]
    changed[index]["source_url"] = altered_url(original["source_url"], s="0303")
    assert changed[index]["source_url"] != original["source_url"]
    proposal = propose(changed)
    assert proposal["status"] == "REVIEW_REQUIRED_NOT_APPLIED"
    assert proposal["proposed_url_changes"] == 1
    assert proposal["changed_fields"] == ["source_url"]
    assert proposal["patches"][0]["id"] == original["id"]
    assert proposal["patches"][0]["before"] != proposal["patches"][0]["after"]
    assert proposal["patches"][0]["official_pdf_sha256"]
    assert not proposal["production_written"] and not proposal["release_approved"]
    assert changed[index]["source_url"] != original["source_url"], "planner must not mutate rows"

    code_bad = [dict(r) for r in rows]
    code_bad[index]["source_exam_code"] = "000000"
    must_reject(code_bad, "exam_code disagreement")

    spoof = [dict(r) for r in rows]
    spoof[index]["source_url"] = (
        "https://wwwq.moex.gov.tw@evil.example/exam/wHandExamQandA_File.ashx"
    )
    must_reject(spoof, "unsafe or malformed")

    wrong_code = [dict(r) for r in rows]
    wrong_code[index]["source_url"] = original["source_url"].replace("code=112030", "code=000000")
    must_reject(wrong_code, "wrong exam_code")

    must_reject(rows[:-1], "historical coverage incomplete")
    duplicates = [dict(r) for r in rows]
    duplicates[1]["id"] = duplicates[0]["id"]
    must_reject(duplicates, "duplicate question ID")

    print("SOURCE URL PROPOSAL SELFTEST OK: 4800 no-op, source-only proposal, five safety rejections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
