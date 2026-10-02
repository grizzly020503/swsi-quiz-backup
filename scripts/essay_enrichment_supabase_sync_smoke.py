#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "data" / "essay_enrichment.json"
EDGE = ROOT / "supabase" / "functions" / "sync-essay-enrichment" / "index.ts"
WORKFLOW = ROOT / ".github" / "workflows" / "moex-social-worker-sync.yml"
RECOVERY = ROOT / "supabase" / "recovery" / "edge_functions.json"

FIELDS = {
    "topic", "major", "keywords", "theories", "laws", "difficulty", "frequency",
    "qtype", "related", "cluster", "cluster_name", "analysis_status",
}
OFFICIAL_FIELDS = {"subject", "year", "round", "qno", "q", "points", "source_exam_code", "source_url"}


def ts_array(source: str, name: str) -> set[str]:
    match = re.search(rf"const\s+{re.escape(name)}\s*=\s*\[(.*?)\]\s+as const;", source, re.S)
    assert match, f"missing TypeScript array {name}"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def main() -> int:
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    edge = EDGE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    recovery = json.loads(RECOVERY.read_text(encoding="utf-8"))

    assert overlay.get("schema_version") == 1, overlay.get("schema_version")
    records = overlay.get("records") or []
    assert records, "essay enrichment overlay must not be empty"
    ids = [str(row.get("id") or "") for row in records]
    assert len(ids) == len(set(ids)), "duplicate overlay essay ids"
    for row in records:
        assert set(row) == {"id", *FIELDS}, (row.get("id"), sorted(set(row) - {"id", *FIELDS}))

    assert ts_array(edge, "ANALYSIS_FIELDS") == FIELDS
    assert OFFICIAL_FIELDS.isdisjoint(ts_array(edge, "ANALYSIS_FIELDS"))
    for token in (
        'const REPO = "grizzly020503/swsi-quiz-backup"',
        "verifyGitHubRepoToken",
        '.from("essays")',
        '.select("id")',
        '.update(record.update)',
        '.eq("id", record.id)',
        "overlay targets missing from essays",
        'ANALYSIS_STATES = new Set(["ready", "reviewed", "verified"])',
        "record ${index}.id has invalid essay identity",
    ):
        assert token in edge, f"missing fail-closed Edge contract: {token}"
    for forbidden in ('.insert(', '.upsert(', '.delete('):
        assert forbidden not in edge, f"analysis sync must never use {forbidden}"

    endpoint = "https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/sync-essay-enrichment"
    for token in (
        "Sync essay teaching enrichment to Supabase",
        "GH_REPO_TOKEN: ${{ github.token }}",
        endpoint,
        "--data-binary @data/essay_enrichment.json",
    ):
        assert token in workflow, f"MOEX workflow missing essay enrichment sync contract: {token}"

    inventory = {str(row.get("slug")): row for row in recovery.get("functions") or []}
    entry = inventory.get("sync-essay-enrichment")
    assert entry, "recovery inventory missing sync-essay-enrichment"
    assert entry.get("verify_jwt") is False, entry

    print(
        "ESSAY ENRICHMENT SUPABASE SYNC CONTRACT OK: "
        f"records={len(records)}, analysis_fields={len(FIELDS)}, official_fields_writeable=0, "
        "repo-token-auth=yes, preflight-existing-ids=yes, recovery-inventory=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
