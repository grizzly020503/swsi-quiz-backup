#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/historical_law_verified_priority10.v1.json"
LINKS = ROOT / "data/law_question_links_priority10.v1.json"

PROTECTED = {
    "official_answer",
    "accepted_answers",
    "grading_mode",
    "stem",
    "options",
}
VERSION_FIELDS = {
    "kind",
    "version_date",
    "effective_date",
    "effective_date_scope",
    "lnndate",
    "lser",
    "url",
}


def _https_host(value: object, expected_host: str) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname == expected_host


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    rows = registry.get("records") or []

    assert registry.get("schema_version") == 1
    assert registry.get("verified_record_count") == len(rows)
    assert registry.get("historical_version_checked_count") == len(rows)
    # Initial audited baseline. Future growth may raise this floor but must not
    # silently drop the already verified 11 records.
    assert len(rows) >= 11, len(rows)

    linked = {
        (str(card.get("law_name") or ""), str(q.get("question_id") or q.get("id") or ""))
        for card in (links.get("cards") or [])
        for q in (card.get("questions") or [])
    }
    seen: set[tuple[str, str]] = set()
    for row in rows:
        k = (str(row.get("law_name") or ""), str(row.get("question_id") or ""))
        assert all(k), row
        assert k not in seen, f"duplicate verified registry key: {k}"
        seen.add(k)
        assert k in linked, f"verified registry row missing from priority10 links: {k}"

        assert row.get("historical_version_checked") is True, k
        assert row.get("verification_level") == "machine_verified_historical_v1", k
        assert str(row.get("verification_basis") or "").strip(), k
        assert str(row.get("article") or "").strip(), k
        assert re.fullmatch(r"[0-9a-f]{64}", str(row.get("historical_article_sha256") or "")), k

        semantic = row.get("historical_semantic") or {}
        assert str(semantic.get("top_article") or "") == str(row.get("article") or ""), k
        assert float(semantic.get("top_score") or 0) >= 0.50, (k, semantic)
        assert float(semantic.get("margin") or 0) >= 0.15, (k, semantic)
        assert semantic.get("decision_reason") == "very_strong_semantic_separation", (k, semantic)

        version = row.get("selected_version") or {}
        assert set(version) == VERSION_FIELDS, (k, sorted(version))
        assert _https_host(version.get("url"), "law.moj.gov.tw"), (k, version)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(version.get("version_date") or "")), (k, version)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(version.get("effective_date") or "")), (k, version)

        assert _https_host(row.get("official_history_url"), "law.moj.gov.tw"), k
        assert _https_host(row.get("exam_date_source_url"), "wwwc.moex.gov.tw"), k
        assert not (set(row) & PROTECTED), (k, sorted(set(row) & PROTECTED))

    print(json.dumps({
        "verified_record_count": len(rows),
        "unique_key_count": len(seen),
        "historical_version_checked_count": registry.get("historical_version_checked_count"),
        "protected_core_field_count": sum(len(set(row) & PROTECTED) for row in rows),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
