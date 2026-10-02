#!/usr/bin/env python3
"""Stage 7 materializes verified historical-law metadata into a separate overlay.

This is the first stage allowed to emit ``historical_version_checked=true``, and
only inside the dedicated derived registry. It never mutates question shards,
official answers, accepted answers, grading modes, stems, or options.

Materialization is monotonic: an existing verified record remains present during
source outages. If fresh evidence for an existing key changes the historical
article, fingerprint, or selected-version identity, the script fails closed
rather than silently overwriting provenance.

A source-format fingerprint migration is allowed only when an explicit,
evidence-bound allowlist entry exactly matches the law/question/article,
old/new SHA-256 pair, and the selected-version identity is unchanged. This is
used only to repair known parser/source-format drift; all unlisted drift remains
fail-closed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE5 = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"
DEFAULT_STAGE6 = ROOT / "auto/qa/historical_law_stage6_semantic.v1.json"
DEFAULT_EXISTING = ROOT / "data/historical_law_verified_priority10.v1.json"
DEFAULT_MIGRATIONS = ROOT / "data/historical_law_fingerprint_migrations.v1.json"
DEFAULT_OUTPUT = DEFAULT_EXISTING

VERIFICATION_LEVEL = "machine_verified_historical_v1"
VERIFICATION_BASIS = (
    "Stage3 zero-false-machine shadow calibration + Stage4 official MOJ exam-date "
    "article fingerprint + Stage6 historical-version semantic top1 high confidence"
)
VERSION_FIELDS = (
    "kind",
    "version_date",
    "effective_date",
    "effective_date_scope",
    "lnndate",
    "lser",
    "url",
)
MIGRATION_FIELDS = (
    "from_sha256",
    "to_sha256",
    "reason",
    "legacy_parser_suffix",
    "legacy_evidence_run_id",
    "current_evidence_run_id",
)


def key(row: dict) -> tuple[str, str]:
    return (str(row.get("law_name") or ""), str(row.get("question_id") or ""))


def _valid_sha(value: object) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def compact_version(value: object) -> dict:
    """Keep only stable provenance fields; omit MOJ page/footer/history noise."""
    source = value if isinstance(value, dict) else {}
    return {field: source.get(field) for field in VERSION_FIELDS}


def _version_identity(value: object) -> tuple[str, ...]:
    version = compact_version(value)
    return tuple(str(version.get(field) or "") for field in VERSION_FIELDS)


def migration_map(payload: dict | None) -> dict[tuple[str, str], dict]:
    payload = payload or {}
    if payload and payload.get("schema_version") != 1:
        raise ValueError("fingerprint migration schema_version must be 1")
    out: dict[tuple[str, str], dict] = {}
    for row in payload.get("migrations") or []:
        if not isinstance(row, dict):
            raise ValueError("fingerprint migration row must be an object")
        k = key(row)
        article = str(row.get("article") or "")
        old_sha = str(row.get("from_sha256") or "")
        new_sha = str(row.get("to_sha256") or "")
        reason = str(row.get("reason") or "").strip()
        suffix = str(row.get("legacy_parser_suffix") or "").strip()
        old_run = row.get("legacy_evidence_run_id")
        new_run = row.get("current_evidence_run_id")
        if not all(k) or k in out:
            raise ValueError(f"invalid/duplicate fingerprint migration key: {k}")
        if not article or not _valid_sha(old_sha) or not _valid_sha(new_sha) or old_sha == new_sha:
            raise ValueError(f"invalid fingerprint migration hashes/article: {k}")
        if not reason or not suffix:
            raise ValueError(f"fingerprint migration missing reason/suffix: {k}")
        if not isinstance(old_run, int) or old_run <= 0 or not isinstance(new_run, int) or new_run <= 0:
            raise ValueError(f"fingerprint migration evidence run IDs invalid: {k}")
        out[k] = dict(row)
    return out


def _authorized_fingerprint_migration(
    previous: dict,
    fresh: dict,
    migration: dict | None,
) -> bool:
    if not migration:
        return False
    if key(previous) != key(fresh) or key(fresh) != key(migration):
        return False
    if str(previous.get("article") or "") != str(fresh.get("article") or ""):
        return False
    if str(migration.get("article") or "") != str(fresh.get("article") or ""):
        return False
    if str(previous.get("historical_article_sha256") or "") != str(migration.get("from_sha256") or ""):
        return False
    if str(fresh.get("historical_article_sha256") or "") != str(migration.get("to_sha256") or ""):
        return False
    return _version_identity(previous.get("selected_version")) == _version_identity(fresh.get("selected_version"))


def _migration_metadata(migration: dict) -> dict:
    return {field: migration.get(field) for field in MIGRATION_FIELDS}


def candidate_records(stage5: dict, stage6: dict) -> list[dict]:
    s5 = {
        key(row): row for row in (stage5.get("records") or [])
        if row.get("promotion_status") == "promotion_candidate"
    }
    records: list[dict] = []
    for row in stage6.get("records") or []:
        if row.get("status") != "historical_semantic_confirmed":
            continue
        k = key(row)
        p = s5.get(k)
        if not p:
            continue
        article = str(row.get("suggested_article") or "")
        fingerprint = str(row.get("historical_article_sha256") or "")
        version = compact_version(row.get("selected_version"))
        if not article or not _valid_sha(fingerprint) or not version.get("url"):
            continue
        records.append({
            "law_name": k[0],
            "question_id": k[1],
            "exam_code": row.get("exam_code"),
            "article": article,
            "historical_version_checked": True,
            "verification_level": VERIFICATION_LEVEL,
            "verification_basis": VERIFICATION_BASIS,
            "selected_version": version,
            "historical_article_sha256": fingerprint,
            "historical_semantic": {
                "top_article": row.get("historical_top_article"),
                "top_score": row.get("historical_top_score"),
                "second_article": row.get("historical_second_article"),
                "second_score": row.get("historical_second_score"),
                "margin": row.get("historical_margin"),
                "decision_reason": row.get("historical_decision_reason"),
            },
            "official_history_url": p.get("official_history_url"),
            "exam_date_source_url": p.get("exam_date_source_url"),
        })
    return sorted(records, key=lambda row: key(row))


def build_registry(
    stage5: dict,
    stage6: dict,
    existing: dict | None = None,
    fingerprint_migrations: dict | None = None,
) -> tuple[dict, list[dict]]:
    existing = existing or {}
    old = {key(row): dict(row) for row in (existing.get("records") or [])}
    fresh = {key(row): row for row in candidate_records(stage5, stage6)}
    migrations = migration_map(fingerprint_migrations)
    conflicts: list[dict] = []

    for k, new in fresh.items():
        previous = old.get(k)
        if previous:
            changed: list[str] = []
            if str(previous.get("article") or "") != str(new.get("article") or ""):
                changed.append("article")
            if str(previous.get("historical_article_sha256") or "") != str(new.get("historical_article_sha256") or ""):
                changed.append("historical_article_sha256")
            if _version_identity(previous.get("selected_version")) != _version_identity(new.get("selected_version")):
                changed.append("selected_version")
            if changed:
                migration = migrations.get(k)
                if changed == ["historical_article_sha256"] and _authorized_fingerprint_migration(previous, new, migration):
                    new = dict(new)
                    new["fingerprint_migration"] = _migration_metadata(migration)
                    old[k] = new
                    continue
                conflicts.append({
                    "law_name": k[0],
                    "question_id": k[1],
                    "changed_fields": changed,
                    "previous_article": previous.get("article"),
                    "fresh_article": new.get("article"),
                    "previous_sha256": previous.get("historical_article_sha256"),
                    "fresh_sha256": new.get("historical_article_sha256"),
                    "previous_selected_version": compact_version(previous.get("selected_version")),
                    "fresh_selected_version": compact_version(new.get("selected_version")),
                })
                continue
            if previous.get("fingerprint_migration"):
                new = dict(new)
                new["fingerprint_migration"] = previous["fingerprint_migration"]
        old[k] = new

    rows = [old[k] for k in sorted(old)]
    registry = {
        "schema_version": 1,
        "scope": "priority10 historical-law verified metadata overlay",
        "method": (
            "Machine-verified historical-law metadata only; protected official "
            "question/answer/grading core is not modified. Registry is monotonic; "
            "evidence drift fails closed."
        ),
        "verified_record_count": len(rows),
        "historical_version_checked_count": sum(
            row.get("historical_version_checked") is True for row in rows
        ),
        "records": rows,
    }
    return registry, conflicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage5", default=str(DEFAULT_STAGE5))
    parser.add_argument("--stage6", default=str(DEFAULT_STAGE6))
    parser.add_argument("--existing", default=str(DEFAULT_EXISTING))
    parser.add_argument("--fingerprint-migrations", default=str(DEFAULT_MIGRATIONS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage5 = json.loads(Path(args.stage5).read_text(encoding="utf-8"))
    stage6 = json.loads(Path(args.stage6).read_text(encoding="utf-8"))
    existing_path = Path(args.existing)
    existing = (
        json.loads(existing_path.read_text(encoding="utf-8"))
        if existing_path.exists() else {}
    )
    migrations_path = Path(args.fingerprint_migrations)
    migrations = (
        json.loads(migrations_path.read_text(encoding="utf-8"))
        if migrations_path.exists() else {}
    )
    registry, conflicts = build_registry(stage5, stage6, existing, migrations)
    if conflicts:
        print(json.dumps({"materialization_conflicts": conflicts}, ensure_ascii=False, indent=2))
        return 2

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verified_record_count": registry["verified_record_count"],
        "historical_version_checked_count": registry["historical_version_checked_count"],
        "fresh_confirmed_count": len(candidate_records(stage5, stage6)),
        "fingerprint_migration_count": sum(bool(row.get("fingerprint_migration")) for row in registry["records"]),
        "materialization_conflict_count": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
