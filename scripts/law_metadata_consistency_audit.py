#!/usr/bin/env python3
"""Deterministic read-only audit for SWSI law enrichment provenance.

This audit never mutates Official Core, question shards, Supabase, or legal trust
states. It answers three narrower questions from tracked repository artifacts:

1. Is a generated ``law`` value canonical and explicitly grounded in immutable
   official question/option text?
2. Is ``legal_status=not_applicable`` stale even though the official text itself
   explicitly names a tracked canonical legal source?
3. Which legacy generated law values need evidence review instead of blanket
   promotion/deletion?

Canonical names and aliases are parsed from the reviewed PostgreSQL canonicalizer
migration so this script does not maintain a second independent law registry.
NFKC normalization is applied to matching input only, mirroring the database
canonicalizer; source question bytes are never rewritten.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHARDS = ROOT / "cdn" / "question-shards"
DEFAULT_CANONICALIZER = ROOT / "supabase" / "migrations" / "20261003184700_normalize_legal_canonical_input_nfkc.sql"
DEFAULT_REVIEWED = ROOT / "data" / "law_metadata_reviewed_evidence.v1.json"

EVIDENCE_BACKED_STATUSES = {"verified_current", "changed"}
REVIEW_FINDINGS = {
    "likely_semantic_mismatch",
    "policy_or_program",
    "ethics_or_norm",
    "concept_or_system",
    "unregistered_or_misnamed_legal",
    "unknown",
}


def _sql_unquote(value: str) -> str:
    return value.replace("''", "'")


def parse_canonicalizer(sql_text: str) -> tuple[list[str], dict[str, str]]:
    """Extract canonical names and literal alias->canonical pairs from SQL."""
    m = re.search(r"names\s+text\[\]\s*:=\s*array\[(.*?)\];", sql_text, re.S | re.I)
    if not m:
        raise ValueError("canonicalizer SQL names array not found")
    names = [_sql_unquote(x) for x in re.findall(r"'((?:''|[^'])*)'", m.group(1))]
    if not names or len(names) != len(set(names)):
        raise ValueError("canonicalizer SQL names array is empty or duplicated")

    aliases: dict[str, str] = {}
    for block in re.finditer(r"\bif\b(.*?)\bthen\b(.*?)\bend\s+if\s*;", sql_text, re.S | re.I):
        condition, body = block.group(1), block.group(2)
        target_match = re.search(
            r"array_append\(\s*out_names\s*,\s*'((?:''|[^'])*)'\s*\)", body, re.S | re.I
        )
        if not target_match:
            continue
        target = _sql_unquote(target_match.group(1))
        if target not in names:
            continue
        for raw_alias in re.findall(
            r"position\(\s*'((?:''|[^'])*)'\s+in\s+s\s*\)", condition, re.S | re.I
        ):
            alias = _sql_unquote(raw_alias)
            # A same-name exclusion in the SQL condition is not an alias.
            if alias == target:
                continue
            previous = aliases.get(alias)
            if previous and previous != target:
                raise ValueError(f"alias maps to multiple canonical names: {alias}")
            aliases[alias] = target
    return names, aliases


def canonicalize(text: Any, names: list[str], aliases: dict[str, str]) -> list[str]:
    source = unicodedata.normalize("NFKC", str(text or ""))
    out: list[str] = []
    for alias, target in aliases.items():
        if alias in source and target not in out:
            out.append(target)
    for name in names:
        if name in source and name not in out:
            out.append(name)
    return out


def official_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(k) or "")
        for k in ("question", "q", "opt_a", "opt_b", "opt_c", "opt_d", "A", "B", "C", "D")
    )


def classify_noncanonical(law: str) -> str:
    """Conservative taxonomy only; never treats a class as correctness proof."""
    s = unicodedata.normalize("NFKC", law).strip()
    if re.search(r"倫理|守則", s):
        return "ethics_or_norm"
    if re.search(r"計畫|方案|政策|綱領|白皮書|補助", s):
        return "policy_or_program"
    if re.search(r"法$|條例$|辦法$|規則$|準則$|自治條例$", s):
        return "unregistered_or_misnamed_legal"
    if re.search(r"制度|體制|新漢堡制|社會保險|年金|相關法規", s):
        return "concept_or_system"
    return "unknown"


def load_reviewed_evidence(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("reviewed evidence schema_version must be 1")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in data.get("records") or []:
        qid = str(row.get("question_id") or "").strip()
        law = str(row.get("law") or "").strip()
        finding = str(row.get("finding") or "").strip()
        if not qid or not law or finding not in REVIEW_FINDINGS:
            raise ValueError(f"invalid reviewed evidence row: {row}")
        key = (qid, law)
        if key in out:
            raise ValueError(f"duplicate reviewed evidence: {key}")
        out[key] = row
    return out


def iter_questions(shards_dir: Path):
    paths = sorted(p for p in shards_dir.glob("*.json") if p.name != "manifest.json")
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("questions") or []:
            yield path.name, row


def audit(
    shards_dir: Path,
    canonicalizer_sql: Path,
    reviewed_evidence_path: Path | None = DEFAULT_REVIEWED,
) -> dict[str, Any]:
    sql = canonicalizer_sql.read_text(encoding="utf-8")
    names, aliases = parse_canonicalizer(sql)
    reviewed = load_reviewed_evidence(reviewed_evidence_path)

    question_count = 0
    shard_names: set[str] = set()
    law_present_count = 0
    official_reference_count = 0
    provenance = Counter()
    status_issues = Counter()
    taxonomy = Counter()
    reviewed_findings = Counter()
    evidence_backed_inferred_count = 0
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    matched_reviewed: set[tuple[str, str]] = set()

    for shard_name, row in iter_questions(shards_dir):
        question_count += 1
        shard_names.add(shard_name)
        qid = str(row.get("id") or "").strip()
        if not qid or qid in seen_ids:
            raise ValueError(f"missing/duplicate question id: {qid!r}")
        seen_ids.add(qid)

        law = str(row.get("law") or "").strip()
        status = str(row.get("legal_status") or "").strip().lower()
        official_names = canonicalize(official_text(row), names, aliases)
        law_names = canonicalize(law, names, aliases) if law else []
        if official_names:
            official_reference_count += 1
        if law:
            law_present_count += 1

        if law:
            if law_names and set(law_names).issubset(set(official_names)):
                pclass = "official_supported_canonical"
            elif law_names:
                pclass = "enrichment_only_canonical"
            else:
                pclass = "noncanonical_law"
            provenance[pclass] += 1
        else:
            pclass = "no_law"

        checked_at = str(row.get("legal_checked_at") or "").strip()
        source_url = str(row.get("legal_source_url") or "").strip()
        evidence_backed = (
            status in EVIDENCE_BACKED_STATUSES
            and bool(checked_at)
            and source_url.startswith("https://")
        )
        if evidence_backed and pclass == "enrichment_only_canonical":
            evidence_backed_inferred_count += 1

        flags: list[str] = []
        if status == "not_applicable" and official_names:
            flags.append("status_not_applicable_but_official_supported")
            status_issues[flags[-1]] += 1
        if status == "not_applicable" and pclass == "enrichment_only_canonical":
            flags.append("status_not_applicable_enrichment_only")
            status_issues[flags[-1]] += 1
        if status == "not_applicable" and pclass == "noncanonical_law":
            flags.append("status_not_applicable_noncanonical")
            status_issues[flags[-1]] += 1

        noncanonical_type = classify_noncanonical(law) if pclass == "noncanonical_law" else None
        if noncanonical_type:
            taxonomy[noncanonical_type] += 1

        reviewed_row = reviewed.get((qid, law)) if law else None
        reviewed_finding = None
        if reviewed_row:
            reviewed_finding = str(reviewed_row["finding"])
            reviewed_findings[reviewed_finding] += 1
            matched_reviewed.add((qid, law))

        needs_item = (
            pclass in {"enrichment_only_canonical", "noncanonical_law"}
            or bool(flags)
            or reviewed_row is not None
        )
        if not needs_item:
            continue

        if evidence_backed:
            action = "preserve_evidence_backed_review_state"
        elif "status_not_applicable_but_official_supported" in flags:
            action = "candidate_restore_to_unreviewed_only"
        elif pclass in {"enrichment_only_canonical", "noncanonical_law"}:
            action = "evidence_review_required"
        else:
            action = "none"

        items.append(
            {
                "question_id": qid,
                "shard": shard_name,
                "subject": row.get("subject"),
                "year": row.get("year"),
                "round": row.get("round"),
                "law": law or None,
                "legal_status": status or None,
                "legal_checked_at": checked_at or None,
                "legal_source_url": source_url or None,
                "official_canonical_names": official_names,
                "law_canonical_names": law_names,
                "provenance": pclass,
                "noncanonical_type": noncanonical_type,
                "evidence_backed_review_state": evidence_backed,
                "status_flags": flags,
                "reviewed_finding": reviewed_finding,
                "reviewed_evidence": reviewed_row.get("evidence") if reviewed_row else None,
                "suggested_action": action,
            }
        )

    missing_reviewed = sorted(set(reviewed) - matched_reviewed)
    if missing_reviewed:
        raise ValueError(f"reviewed evidence no longer matches tracked shard rows: {missing_reviewed}")

    items.sort(key=lambda x: (str(x["provenance"]), str(x["question_id"])))
    candidate_count = provenance["enrichment_only_canonical"] + provenance["noncanonical_law"]
    report = {
        "schema_version": 1,
        "method": (
            "NFKC canonical matching parsed from reviewed PostgreSQL canonicalizer; "
            "official support uses immutable question/options only; generated law is enrichment only"
        ),
        "source": {
            "shard_count": len(shard_names),
            "question_count": question_count,
            "canonical_name_count": len(names),
            "alias_count": len(aliases),
            "canonicalizer": str(canonicalizer_sql.relative_to(ROOT)) if canonicalizer_sql.is_relative_to(ROOT) else str(canonicalizer_sql),
        },
        "law_present_count": law_present_count,
        "official_reference_count": official_reference_count,
        "provenance_counts": dict(sorted(provenance.items())),
        "legacy_candidate_count": candidate_count,
        "status_issue_counts": dict(sorted(status_issues.items())),
        "evidence_backed_inferred_count": evidence_backed_inferred_count,
        "noncanonical_taxonomy_counts": dict(sorted(taxonomy.items())),
        "reviewed_finding_counts": dict(sorted(reviewed_findings.items())),
        "protected_core_mutation_count": 0,
        "items": items,
    }
    return report


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {k: report[k] for k in (
        "source",
        "law_present_count",
        "official_reference_count",
        "provenance_counts",
        "legacy_candidate_count",
        "status_issue_counts",
        "evidence_backed_inferred_count",
        "noncanonical_taxonomy_counts",
        "reviewed_finding_counts",
        "protected_core_mutation_count",
    )}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards-dir", type=Path, default=DEFAULT_SHARDS)
    parser.add_argument("--canonicalizer-sql", type=Path, default=DEFAULT_CANONICALIZER)
    parser.add_argument("--reviewed-evidence", type=Path, default=DEFAULT_REVIEWED)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = audit(args.shards_dir, args.canonicalizer_sql, args.reviewed_evidence)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
