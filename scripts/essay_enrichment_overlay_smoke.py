#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "incoming" / "115100.json"
AUTO = ROOT / "auto" / "essays_auto.json"
OVERLAY = ROOT / "data" / "essay_enrichment.json"
BUILD = ROOT / "scripts" / "build_auto_payload.py"

LOCKED_FIELDS = ("id", "subject", "year", "round", "qno", "q", "points")
EXPECTED_CLUSTERS = {
    "E-115-2-HBSE-1": "DEV1",
    "E-115-2-HBSE-2": "SOC1",
    "E-115-2-SW-1": "MED1",
    "E-115-2-SW-2": "COM3",
    "E-115-2-DS-1": "EMP1",
    "E-115-2-DS-2": "GRP1",
    "E-115-2-R-1": "RES5",
    "E-115-2-R-2": "RES8",
    "E-115-2-SP-1": "POL2",
    "E-115-2-SP-2": "PRO2",
}
REQUIRED_TEXT_FIELDS = (
    "topic", "major", "difficulty", "frequency", "qtype", "cluster",
    "cluster_name", "analysis_status",
)
REQUIRED_LIST_FIELDS = ("keywords", "theories", "laws", "related")


def by_id(rows):
    return {str(row.get("id") or ""): row for row in rows if isinstance(row, dict)}


def main() -> int:
    subprocess.run([sys.executable, str(BUILD)], cwd=ROOT, check=True)

    incoming_payload = json.loads(INCOMING.read_text(encoding="utf-8"))
    incoming = by_id(incoming_payload.get("essays") or [])
    generated = by_id(json.loads(AUTO.read_text(encoding="utf-8")))
    overlay_payload = json.loads(OVERLAY.read_text(encoding="utf-8"))
    overlay_rows = overlay_payload.get("records") or []
    overlay = by_id(overlay_rows)

    assert overlay_payload.get("schema_version") == 1
    assert len(overlay_rows) == 10, f"expected exactly 10 115-2 overlays, got {len(overlay_rows)}"
    assert set(overlay) == set(EXPECTED_CLUSTERS), (set(overlay), set(EXPECTED_CLUSTERS))

    for ident, cluster in EXPECTED_CLUSTERS.items():
        assert ident in incoming, f"overlay target missing from official incoming: {ident}"
        assert ident in generated, f"overlay target missing from generated auto essays: {ident}"
        source = incoming[ident]
        row = generated[ident]

        # Official MOEX fields must remain exactly equal. Enrichment must never be
        # able to rewrite wording, points, identity, session, subject or qno.
        for field in LOCKED_FIELDS:
            assert row.get(field) == source.get(field), (
                ident, field, source.get(field), row.get(field)
            )

        for field in REQUIRED_TEXT_FIELDS:
            assert isinstance(row.get(field), str) and row[field].strip(), (ident, field, row.get(field))
        for field in REQUIRED_LIST_FIELDS:
            assert isinstance(row.get(field), list), (ident, field, row.get(field))

        assert row["analysis_status"] == "ready", (ident, row["analysis_status"])
        assert row["cluster"] == cluster, (ident, row["cluster"], cluster)
        assert row["difficulty"] in {"基礎", "中等", "困難"}, (ident, row["difficulty"])
        assert row["frequency"] in {"低頻", "中頻", "高頻"}, (ident, row["frequency"])
        assert row["keywords"], f"{ident}: keywords must not be empty"

    # Pin the two highest-risk semantic contracts. SP-2 is metadata-only here;
    # detailed guide/legal interpretation remains a separate verified task.
    assert generated["E-115-2-SP-2"]["laws"] == ["性侵害犯罪防治法"]
    assert generated["E-115-2-SP-2"]["qtype"] == "法規題"
    assert generated["E-115-2-R-1"]["topic"] == "概念化與操作化"
    assert generated["E-115-2-R-1"]["cluster"] == "RES5"

    print(
        "ESSAY ENRICHMENT OVERLAY SMOKE OK: 10/10 ready metadata; "
        "official essay core unchanged; cluster/schema contracts=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
