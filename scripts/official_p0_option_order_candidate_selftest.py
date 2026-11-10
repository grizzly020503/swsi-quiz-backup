#!/usr/bin/env python3
"""Read-only proof for two high-impact MOEX official option-order corrections.

Usage: python scripts/official_p0_option_order_candidate_selftest.py
This script MUST NEVER import, publish, auto-approve, or mutate Official Core.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = ROOT / "audit/official_p0_option_order_candidate_20261110.json"
EXPECTED_ROWS = {
    "SP104-2-37": {
        "shard": "cdn/question-shards/104-2.json",
        "old_options": ["①②③", "①③⑤", "②③④", "③④⑤"],
        "proposed_options": ["①②③", "①③④", "①③⑤", "②④⑤"],
        "answer": "C", "group": "CBCCBCCACD", "question_number": 37,
        "changed_fields": {"opt_b", "opt_c", "opt_d"},
        "misgraded_displayed_correct_answer": True,
    },
    "SP107-1-40": {
        "shard": "cdn/question-shards/107-1.json",
        "old_options": ["①②③④", "①③④⑤", "①②③⑤", "②③④⑤"],
        "proposed_options": ["①②③④", "①③④⑤", "②③④⑤", "②③④"],
        "answer": "B", "group": "DBCDBBDCBB", "question_number": 40,
        "changed_fields": {"opt_c", "opt_d"},
        "misgraded_displayed_correct_answer": False,
    },
}
OPTION_FIELDS = ["opt_a", "opt_b", "opt_c", "opt_d"]
RESET_TO_NULL = ("major", "topic", "keywords", "exp_why", "exp_others",
                 "exp_trap", "exp_raw", "mnemonic", "extension", "law",
                 "mistake", "analysis_error", "analysis_started_at",
                 "analysis_completed_at", "analysis_last_attempt_at")
TRIGGER_MUTABLE_FIELDS = set(RESET_TO_NULL) | {"analysis_status", "analysis_attempts"}


def simulate_official_reset(staged: dict) -> dict:
    """Model public.reset_ai_analysis_on_official_change() on shard fields only.

    This is *not* the full production trigger stack. In real Supabase the
    BEFORE UPDATE trigger sets pending; avoid explicitly updating the status.
    """
    result = dict(staged)
    for field in RESET_TO_NULL:
        if field in result:
            result[field] = None
    if "analysis_attempts" in result:
        result["analysis_attempts"] = 0
    result["analysis_status"] = "pending"
    return result


def validate_live_trigger_preflight_sql(proof: dict) -> None:
    path = "audit/official_p0_option_order_live_trigger_preflight_20261111.sql"
    assert proof["production_trigger_preflight_sql"] == path
    assert proof["official_change_trigger_state"] == "pending"
    assert proof["production_reset_trigger_source_name"] == "public.reset_ai_analysis_on_official_change"
    assert proof["production_reset_trigger_source_sha256"] == "729a9c8e5158ebe73c65504ce988126d9e6de95d65eff8ed5bec9d6cacac74f0"
    pg_sql = (ROOT / "audit/official_p0_option_order_pg17_synthetic_rollback_20261111.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION public.reset_ai_analysis_on_official_change()" in pg_sql
    assert "EXECUTE FUNCTION public.reset_ai_analysis_on_official_change()" in pg_sql
    assert "SECURITY DEFINER" in pg_sql and "SET search_path TO ''" in pg_sql
    assert "UPDATE swsi_p0_fixture SET" in pg_sql
    # Only options may appear in any SQL UPDATE target list, never analysis_status.
    for match in re.finditer(r"UPDATE swsi_p0_fixture SET(.*?)\\bWHERE\\b", pg_sql, flags=re.S):
        assert not re.search(r"\\banalysis_status\\s*=", match.group(1))

    assert proof["official_change_trigger_clear_enrichment"] is True
    assert proof["option_only_update_required"] is True
    sql = (ROOT / path).read_text(encoding="utf-8")
    statements = "\n".join(line for line in sql.splitlines()
                           if not line.lstrip().startswith("--"))
    assert statements.lstrip().upper().startswith("WITH SEEN")
    assert statements.rstrip().endswith("FROM checks;")
    assert statements.count(";") == 1
    assert "trg_reset_ai_on_official_change" in statements
    assert "trg_auto_enable_ai_pending" in statements
    assert "new.analysis_status := ''pending''" in statements
    assert "HOLD_TRIGGER_DRIFT" in statements
    assert not re.search(r"(?im)^\s*(?:UPDATE|INSERT|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|CALL|COMMIT|ROLLBACK)\b", statements)

PREIMAGE_DIGESTS = {
    "SP104-2-37": "10ed64cb7f1343b45dabb025bf54c281ffb36ec35ccf1128d37f784ddecb7dfb",
    "SP107-1-40": "588af4d0976c6758594e679110f210f4f14dadeebddb9c84a196889e6e7c101f",
}
SQL_PATH = "audit/official_p0_option_order_live_preflight_20261110.sql"


def validate_live_preflight_sql(proof: dict) -> None:
    # This is a static contract check, not a live database connection.
    # Production preflight requires a separate authenticated READ-ONLY SELECT.
    assert proof["production_preflight_sql"] == SQL_PATH
    assert proof["production_preflight_mode"] == "READ_ONLY_EXACT_ROW_CHECK_NOT_APPROVAL"
    assert proof["production_preflight_field_count"] == 37
    assert set(PREIMAGE_DIGESTS) == {row["id"] for row in proof["rows"]}
    sql = (ROOT / SQL_PATH).read_text(encoding="utf-8")
    sql_code = "\n".join(line for line in sql.splitlines()
                          if not line.lstrip().startswith("--"))
    assert sql_code.lstrip().upper().startswith("WITH EXPECTED")
    # Exactly one SELECT statement: no transaction, DML, or stored procedures.
    assert sql_code.count(";") == 1 and sql_code.rstrip().endswith("ORDER BY id;")
    assert not re.search(
        r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|"
        r"GRANT|REVOKE|COPY|EXECUTE|DO|CALL|PERFORM|SET|COMMIT)\b",
        sql_code, flags=re.IGNORECASE,
    )
    assert "public.questions" in sql_code
    assert "sha256(convert_to(to_jsonb(q)::text, 'UTF8'))" in sql_code
    assert "column_count = 37" in sql_code
    assert "total_questions" in sql_code
    assert "HOLD_NO_RELEASE" in sql_code
    for row in proof["rows"]:
        ident = row["id"]
        digest = PREIMAGE_DIGESTS[ident]
        assert row["production_full_37_column_sha256"] == digest
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert sql_code.count(digest) == 1
        assert sql_code.count("'" + ident + "'") == 1



def verify() -> int:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    assert proof["schema_version"] == 1 and proof["status"] == "DRAFT_NO_GO"
    assert proof["official_p0_queue"] == 428
    assert proof["changed_question_count"] == len(proof["rows"]) == 2
    assert proof["changed_option_count"] == 5
    for flag in (
        "official_answer_changed", "grading_changed", "independent_human_approval",
        "owner_release_pin", "repository_official_core_changed", "production_db_written",
        "cloudflare_deployed", "netlify_deployed"
    ):
        assert proof[flag] is False, flag
    assert {x["id"] for x in proof["rows"]} == set(EXPECTED_ROWS)
    validate_live_preflight_sql(proof)
    validate_live_trigger_preflight_sql(proof)

    for entry in proof["rows"]:
        id_ = entry["id"]
        expected = EXPECTED_ROWS[id_]
        assert entry["shard"] == expected["shard"]
        assert entry["old_options"] == expected["old_options"]
        assert entry["proposed_options"] == expected["proposed_options"]
        assert entry["answer"] == expected["answer"]
        assert set(entry["changed_fields"]) == expected["changed_fields"]
        assert entry["official_answer_group_31_40"] == expected["group"]
        assert entry["question_number"] == expected["question_number"]
        assert entry["misgraded_displayed_correct_answer"] is expected["misgraded_displayed_correct_answer"]
        assert len(set(entry["proposed_options"])) == 4
        assert re.fullmatch(r"[a-f0-9]{64}", entry["pdf_sha"])

        for key, suffix in (("pdf_url", "t=Q"), ("official_answer_url", "t=A")):
            u = urlsplit(entry[key])
            assert u.scheme == "https" and u.hostname == "wwwq.moex.gov.tw"
            assert u.path.endswith("/wHandExamQandA_File.ashx") and suffix in u.query
        # A wrong exam code or subject URL must never certify an unrelated paper.
        exam_code = "104100" if id_ == "SP104-2-37" else "107030"
        assert parse_qs(urlsplit(entry["pdf_url"]).query).get("code") == [exam_code]
        assert parse_qs(urlsplit(entry["official_answer_url"]).query).get("code") == [exam_code]
        sheet_answer = entry["official_answer_group_31_40"][entry["question_number"] - 31]
        assert sheet_answer == expected["answer"], (id_, "official answer sheet changed")

        bank = json.loads((ROOT / entry["shard"]).read_text(encoding="utf-8"))
        assert bank["question_count"] == len(bank["questions"]) == 200
        rows = [q for q in bank["questions"] if q["id"] == id_]
        assert len(rows) == 1
        current = rows[0]
        assert [current[field] for field in OPTION_FIELDS] == entry["old_options"], (id_, "main changed")
        assert current["source_exam_code"] == exam_code
        assert parse_qs(urlsplit(current["source_url"]).query).get("code") == [exam_code]
        assert current["answer"] == expected["answer"]
        assert current.get("accepted_answers") is None
        assert current["grading_mode"] == "standard"
        assert current["analysis_status"] == entry["original_status"]
        assert entry["proposed_analysis_status"] == "pending"

        changed = {f for f, before, after in zip(OPTION_FIELDS, entry["old_options"], entry["proposed_options"]) if before != after}
        assert changed == expected["changed_fields"]
        assert entry["proposed_options"][ord(expected["answer"]) - ord("A")] == (
            "①③⑤" if id_ == "SP104-2-37" else "①③④⑤"
        )
        if id_ == "SP104-2-37":
            assert entry["old_options"][1] == entry["proposed_options"][2]
            assert entry["old_options"][2] != entry["proposed_options"][2]
        # Supabase's canonical BEFORE UPDATE OF official core trigger will
        # reset stale enrichment and set pending; our future SQL must not SET
        # analysis_status explicitly, because an AFTER UPDATE OF that column
        # can enable the AI analysis job.
        staged = dict(current)
        for field, value in zip(OPTION_FIELDS, entry["proposed_options"]):
            staged[field] = value
        staged = simulate_official_reset(staged)
        assert staged["analysis_status"] == "pending"
        assert staged["answer"] == current["answer"]
        assert staged.get("accepted_answers") == current.get("accepted_answers")
        assert staged["grading_mode"] == current["grading_mode"]
        assert all(staged[field] is None for field in RESET_TO_NULL if field in staged)
        changed_full = {k for k in staged if staged[k] != current[k]}
        expected_triggered = {k for k in TRIGGER_MUTABLE_FIELDS
                              if k in current and current[k] != staged[k]}
        assert changed_full == expected["changed_fields"] | expected_triggered
        assert changed_full.intersection(OPTION_FIELDS) == expected["changed_fields"]

    print("P0 OPTION ORDER DRAFT QA OK: 2 exact main rows, 5 option corrections, "
          "official answer unchanged, trigger-owned AI pending; 428 source reviews held; NO RELEASE")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
