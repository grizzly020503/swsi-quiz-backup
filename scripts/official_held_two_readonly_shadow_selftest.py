#!/usr/bin/env python3
"""Fail-closed static QA for the two-row, REAL production SELECT-only shadow.

The SQL was actually executed against active SWSI Supabase in the review turn.
This checker cannot and does not grant source approval, mutate rows or test
production trigger/pg_cron side effects; keep the release as NO-GO.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "audit/official_held_two_option_shadow_readonly_20261105.sql"
PROOF = ROOT / "audit/official_held_two_live_preflight_evidence_20261105.json"
IDS = {"R-107-2-40", "SP111-2-34"}
BEFORE = {
    "R-107-2-40": "ec50059ee6d7ef42fb093e19edde8c2058321e6730844f8a64463a01397d6705",
    "SP111-2-34": "b4ebad61984ab44a8e0949d90d6cf23a8bd2575f00568d93fdd598ca4c79ef7d",
}
UNTOUCHED = {
    "R-107-2-40": "b5838df66ee261cf845a0c93f3f08e7e8304c0059286cfd3e8725a93cf943faa",
    "SP111-2-34": "d045f3978fb52e7018149c3c7ff81b6efb92c7e86ab1ec0f42bc4a21e7e28f2f",
}
AFTER_PREVIEW = {
    "R-107-2-40": "62be4a94fd07080100a30a389e0245ab1d272e99454134bce2acde163a80fe87",
    "SP111-2-34": "b931225d843499b14144b98df9970961744bdc1f6f691ee3fae4b474bba0eae3",
}
PDF_SHA = {
    "R-107-2-40": "65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d",
    "SP111-2-34": "9a4afe4df13a7b88582efa0bb3950ccdb3780ec5c7e3380afabe8b0e8f2e3a0d",
}
OPTIONS = {
    "R-107-2-40": ["opt_d"],
    "SP111-2-34": ["opt_a", "opt_b", "opt_c", "opt_d"],
}
FORBIDDEN = re.compile(r"\b(?:UPDATE|INSERT|DELETE|MERGE|TRUNCATE|CREATE|ALTER|DROP|"
                       r"GRANT|REVOKE|CALL|DO|EXECUTE|COPY|PERFORM|"
                       r"BEGIN|COMMIT|ROLLBACK|SECURITY\s+DEFINER)\b", re.I)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError("NO-GO two-source SQL preflight changed: " + reason)


def validate_sql(sql: str) -> None:
    # SQL lexical safeguard for a single WITH ... SELECT statement.
    lines = [line for line in sql.splitlines()
             if line.strip() and not line.lstrip().startswith("--")]
    code = "\n".join(lines)
    without_literals = re.sub(r"'(?:''|[^'])*'", "''", code)
    require(code.startswith("WITH proposed("), "must start as SELECT-only CTE")
    require(without_literals.rstrip().endswith(";")
            and without_literals.count(";") == 1, "exactly one statement")
    require(not FORBIDDEN.search(without_literals), "write/privileged SQL")
    for fragment in (
        "(SELECT COUNT(*) FROM public.questions) AS full_corpus_count",
        "(SELECT COUNT(*) FROM jsonb_each(before_row))=37 AS shape_ok",
        "sha256(convert_to(before_row::text,'UTF8'))",
        "sha256(convert_to(proposed_row::text,'UTF8'))",
        "AND grading_ok AND analysis_pending_quarantine",
        "all_non_option_fields_preserved",
        "FALSE AS human_original_pdf_approval",
        "FALSE AS permission_to_modify_official_core",
        "FALSE AS release_approved",
        "NO-GO: SQL SELECT ONLY",
    ):
        require(fragment in code, "missing original data/NO-GO guard: " + fragment)
    for sha in list(BEFORE.values()) + list(UNTOUCHED.values()):
        require(code.count(sha) == 1, "SHA drift or duplicate: " + sha)
    for id in IDS:
        require(code.count(id) == 1, "missing/duplicated case: " + id)
    for option in ("兩個變項間有高度相關，則非常可能有因果關係",
                   "1 至 3 個月", "2 至 4 個月", "3 至 6 個月", "4 至 6 個月"):
        require(option in sql, "MOEX original option text drift")
    require("JOIN proposed USING(id)" in code, "unexpected rows in scope")
    require("(before_row || patch) <> before_row" in code, "empty patch allowed")
    require("(proposed_row - 'opt_a' - 'opt_b' - 'opt_c' - 'opt_d') =" in code,
            "non-option fields not protected")


def validate_proof(proof: dict) -> None:
    require(proof.get("schema_version") == 1
            and proof.get("status") == "LIVE_SELECT_PREIMAGE_PROVEN_RELEASE_NO_GO",
            "scope status")
    summary = proof.get("results", {})
    require(summary.get("official_mcq_count") == 4800
            and summary.get("targets") == 2 and summary.get("strict_matches") == 2
            and summary.get("rows_have_37_columns") is True
            and summary.get("all_non_option_fields_preserved") is True
            and summary.get("production_writes") == 0, "actual live SELECT results")
    safe = proof.get("safety", {})
    for field in ("human_original_pdf_approval", "private_production_faithful_restore_proven",
                  "release_approved", "production_write", "backup_operation",
                  "official_core_modified"):
        require(safe.get(field) is False, "approval/security hold removed: " + field)
    rows = proof.get("rows", [])
    require(len(rows) == 2 and {r.get("id") for r in rows} == IDS,
            "exact two reviewed IDs")
    for row in rows:
        ident = row["id"]
        require(row.get("before_37_column_sha256") == BEFORE[ident], "preimage hash")
        require(row.get("unaffected_fields_sha256") == UNTOUCHED[ident],
                "non-option hash")
        require(row.get("proposed_source_field_shadow_sha256") == AFTER_PREVIEW[ident],
                "proposal hash")
        require(row.get("original_pdf_registry_sha256") == PDF_SHA[ident],
                "pinned official source PDF identity")
        require(row.get("changed_fields_proposed") == OPTIONS[ident],
                "fields changed without review")
        require(row.get("expected_answer") == ("D" if ident == "R-107-2-40" else "C"),
                "grading changed")
        require(row.get("original_pdf_url", "").startswith(
                "https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?"),
                "non-MOEX source")


def main():
    sql = SQL.read_text(encoding="utf-8")
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    validate_sql(sql)
    validate_proof(proof)
    sql_bad = [
        sql + "\nDELETE FROM public.questions;",
        sql.replace("FALSE AS release_approved", "TRUE AS release_approved"),
        sql.replace("COUNT(*) FROM jsonb_each(before_row)", "30 FROM jsonb_each(before_row)"),
        sql.replace(BEFORE["R-107-2-40"], "0" * 64),
        sql.replace("JOIN proposed USING(id)", "CROSS JOIN proposed"),
        sql.replace("AND grading_ok AND analysis_pending_quarantine",
                    "AND analysis_pending_quarantine"),
    ]
    for n, modified in enumerate(sql_bad, 1):
        try:
            validate_sql(modified)
        except AssertionError:
            continue
        raise AssertionError("fail-open SQL mutation " + str(n))
    proof_bad = [
        (lambda p: p["safety"].update(human_original_pdf_approval=True)),
        (lambda p: p["results"].update(strict_matches=1)),
        (lambda p: p["rows"][1].update(expected_answer="A")),
        (lambda p: p["rows"][0].update(changed_fields_proposed=["answer", "opt_d"])),
    ]
    for n, change in enumerate(proof_bad, 1):
        modified = copy.deepcopy(proof)
        change(modified)
        try:
            validate_proof(modified)
        except AssertionError:
            continue
        raise AssertionError("fail-open proof mutation " + str(n))
    print("SWSI 2-ROW LIVE READONLY SHADOW OK: 4800 corpus / 2 x 37-column "
          "exact preimages / 5 text fields / 0 writes / 10 fail-closed mutations; "
          "HUMAN RELEASE NO-GO")


if __name__ == "__main__":
    main()
