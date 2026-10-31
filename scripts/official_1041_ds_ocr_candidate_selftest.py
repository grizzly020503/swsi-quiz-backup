#!/usr/bin/env python3
"""Fail-closed, offline audit gate for 104-1 DS Q22/Q27/Q29 OCR *candidate*.

This program NEVER approves MOEX source text, updates Official Core, or touches
Supabase/Cloudflare/Netlify. It only verifies this review-only audit against
the pinned currently published shard and source-identity registry.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/official_104_1_direct_service_three_ocr_candidate_20261031.json"
SHARD = ROOT / "cdn/question-shards/104-1.json"
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
REGISTRY = ROOT / "data/moex_source_subjects.v1.json"
SHADOW_SQL = ROOT / "audit/official_104_1_direct_service_three_shadow_readonly_20261031.sql"
IDS = {"DS-104-1-22": "A", "DS-104-1-27": "B", "DS-104-1-29": "D"}
TEXT_FIELDS = {"question", "opt_a", "opt_b", "opt_c", "opt_d"}
FALSE_GATES = (
    "independent_human_approval",
    "release_approved",
    "production_database_written",
    "cloudflare_main_deployed",
    "netlify_backup_changed",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def url_identity(url: str) -> tuple[str, str, str]:
    parts = urlsplit(url)
    require(
        parts.scheme == "https"
        and parts.netloc == "wwwq.moex.gov.tw"
        and parts.path == "/exam/wHandExamQandA_File.ashx"
        and not parts.fragment and not parts.username and not parts.password,
        "untrusted official URL origin/path",
    )
    params = parse_qs(parts.query, strict_parsing=True)
    require(
        set(params) == {"t", "code", "c", "s", "q"}
        and all(len(v) == 1 for v in params.values())
        and params["t"] == ["Q"] and params["q"] == ["1"],
        "malformed official URL parameters",
    )
    return params["code"][0], params["c"][0], params["s"][0]


def validate(candidate: dict, rows: list[dict], manifest: dict, registry: dict,
             actual_shard_sha: str) -> None:
    require(candidate["status"] == "DRAFT_ORIGINAL_MOEX_PDF_VERIFIED_HUMAN_APPROVAL_REQUIRED",
            "candidate must remain human-held/no-go")
    require(all(candidate.get(flag) is False for flag in FALSE_GATES),
            "an unverified source/production/approval gate was asserted true")
    require(candidate["secondary_pdf_role"] ==
            "UNVERIFIED_SECONDARY_TRANSCRIPTION_NOT_OFFICIAL_APPROVAL",
            "mirror transcription cannot become MOEX approval")
    require(candidate["original_pdf_sha256_reverified_in_this_run"] is True,
            "official original PDF exact-byte gate not recorded")
    source_proof = candidate["original_source_verification"]
    require(source_proof["github_actions_run_result"] == "success"
            and source_proof["exact_byte_sha256"] ==
            candidate["original_pdf_sha256_expected_from_pinned_registry"]
            and source_proof["exact_bytes"] == 317707
            and source_proof["official_pdf_page_number"] == 3
            and source_proof["extracted_text_field_count"] == 15
            and source_proof["matched_proposed_text_fields"] == 15
            and source_proof["independent_human_approval"] is False
            and source_proof["exact_text_whitespace_normalization"] ==
                "remove-whitespace-only (no character substitutions)",
            "official original PDF proof incomplete/overclaimed")
    require(candidate["all_grading_tuples_must_remain_unchanged"] is True,
            "grading lock missing")
    require(candidate["all_unaffected_rows_must_remain_byte_identical"] is True,
            "unaffected-row lock missing")
    require(candidate["mcq_total_unchanged"] == 4800 and
            candidate["essay_total_unchanged"] == 240,
            "corpus sizes not locked")
    require(candidate["baseline_dataset_revision"] ==
            manifest["dataset_revision"], "dataset revision drift")
    require(candidate["baseline_shard_sha256"] == actual_shard_sha,
            "baseline physical shard hash drift")

    shards = manifest["shards"]
    require(len(shards) == 24 and manifest["total_questions"] == 4800
            and sum(s["question_count"] for s in shards) == 4800,
            "manifest total/24-shard invariant broken")
    matching = [s for s in shards if s["file"] == "104-1.json"]
    require(len(matching) == 1 and matching[0]["sha256"] == actual_shard_sha
            and matching[0]["question_count"] == 200,
            "104-1 source shard no longer matches manifest")

    papers = registry.get("records")
    require(isinstance(papers, list) and len(papers) == 120,
            "expected 120 approved source identities")
    source = [p for p in papers if p["session"] == "104-1"
              and p["subject"] == "社會工作直接服務"]
    require(len(source) == 1 and source[0]["status"] ==
            "pdf_header_index_matched", "official source registry drift")
    source = source[0]
    require(
        candidate["original_pdf_sha256_expected_from_pinned_registry"] ==
        source["pdf_sha256"] and
        candidate["original_pdf_approved_source"] == source["url"] and
        source_proof["official_url"] == source["url"] and
        source_proof["exact_byte_sha256"] == source["pdf_sha256"] and
        source_proof["exact_bytes"] == source["http"]["bytes"],
        "pinned official PDF metadata mismatch",
    )
    expected_url = (source["exam_code"], str(source["c"]), str(source["s"]))
    require(url_identity(source["url"]) == expected_url,
            "wrong original-PDF source identity")

    require(len(rows) == candidate["baseline_question_count"] == 200
            and len({row["id"] for row in rows}) == 200,
            "expected 200 unique 104-1 questions")
    indexed = {row["id"]: row for row in rows}
    changes = candidate["proposed_changes"]
    require(len(changes) == len(IDS) == candidate["affected_question_count"],
            "unexpected changed-row count")
    require({e["id"] for e in changes} == set(IDS) ==
            set(candidate["affected_ids"]) ==
            set(candidate["official_answer_strings"]),
            "candidate only permits three pinned IDs")
    require(len({e["id"] for e in changes}) == len(changes),
            "duplicate proposed ID")
    require(candidate["unaffected_question_count"] == 4797,
            "unexpected unaffected-row count")

    for change in changes:
        key = change["id"]
        live = indexed[key]
        before = change["preimage_fields"]
        after = change["proposed_fields"]
        require(set(before) == set(after) == TEXT_FIELDS,
                f"{key}: only the official question and four options are allowed")
        require(all(isinstance(value, str) and value.strip()
                    for value in after.values()),
                f"{key}: empty/non-text proposal")
        require(all(live[field] == before[field] for field in TEXT_FIELDS),
                f"{key}: baseline question/option preimage drift")
        require(set(change["changed_fields"]) ==
                {field for field in TEXT_FIELDS if before[field] != after[field]},
                f"{key}: incorrect changed field list")
        require(change["changed_fields"],
                f"{key}: proposal has no actual text changes")
        require(live["subject"] == "社會工作直接服務" and
                str(live["year"]) == "104" and live["round"] == "第一次",
                f"{key}: wrong exam/subject")
        require(live["answer"] == IDS[key] ==
                change["official_answer_unchanged"] ==
                candidate["official_answer_strings"][key],
                f"{key}: official answer drift")
        require(live["accepted_answers"] == change["accepted_answers_unchanged"]
                and live["grading_mode"] == change["grading_mode_unchanged"] ==
                "standard", f"{key}: special grading drift")
        require(live["source_exam_code"] == change["source_exam_code"] ==
                source["exam_code"] and
                live["source_url"] == change["original_source_url"] and
                url_identity(live["source_url"]) == expected_url,
                f"{key}: official source URL/exam mismatch")

    require(len([r for r in rows if r["id"] not in IDS]) == 197,
            "unaffected 104-1 row invariant violated")


def validate_readonly_sql(candidate: dict) -> None:
    """Check that the separately executed production-shadow artifact stays scoped.

    Pure static guard; successful CI is not production SQL execution proof.
    """
    sql = SHADOW_SQL.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
    assert without_comments.lstrip().startswith("WITH candidate AS (")
    assert without_comments.rstrip().endswith("FROM flags;")
    assert without_comments.count(";") == 1, "Only one SQL statement allowed"
    literal = re.search(
        r"jsonb_array_elements\('((?:''|[^'])*)'::jsonb\)",
        without_comments,
    )
    assert literal is not None, "SQL must carry exact three immutable full rows"
    embedded = json.loads(literal.group(1).replace("''", "'"))
    assert len(embedded) == 3
    assert {x["id"] for x in embedded} == set(IDS)
    for entry in embedded:
        assert len(entry["before"]) == 37, "all 37 live columns required"
        reference = next(x for x in candidate["proposed_changes"]
                         if x["id"] == entry["id"])
        assert entry["after_text"] == reference["proposed_fields"]
        assert entry["expected_answer"] == reference["official_answer_unchanged"]
        assert (entry["expected_accepted_answers"] ==
                reference["accepted_answers_unchanged"])
        assert (entry["expected_grading_mode"] ==
                reference["grading_mode_unchanged"])
        for name, value in reference["preimage_fields"].items():
            assert entry["before"][name] == value, "baseline preimage drift"

    stripped = without_comments.replace(literal.group(0), "jsonb_array_elements('[]'::jsonb)")
    # Refuse write statements regardless of SQL keyword case.
    assert not re.search(
        r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|CALL|DO)\b",
        stripped, re.IGNORECASE,
    ), "read-only shadow file contains a write/DDL token"
    assert "public.questions q" in stripped
    assert "PASS_READONLY_SHADOW_ONLY" in stripped
    assert "forbidden_field_changes_total" in stripped
    assert "grade_tuples_unchanged" in stripped
    assert "other_rows_byte_semantics_unchanged" in stripped


def adversarial_selftest(candidate: dict, rows: list[dict],
                         manifest: dict, registry: dict, sha: str) -> None:
    cases = []
    altered = copy.deepcopy(candidate)
    altered["proposed_changes"][0]["preimage_fields"]["question"] += "TAMPER"
    cases.append(("preimage drift", altered))
    altered = copy.deepcopy(candidate)
    altered["proposed_changes"][0]["official_answer_unchanged"] = "D"
    cases.append(("answer drift", altered))
    altered = copy.deepcopy(candidate)
    altered["release_approved"] = True
    cases.append(("false approval", altered))
    altered = copy.deepcopy(candidate)
    altered["original_pdf_sha256_reverified_in_this_run"] = False
    cases.append(("falsely omitted original PDF check", altered))
    altered = copy.deepcopy(candidate)
    altered["original_source_verification"]["matched_proposed_text_fields"] = 14
    cases.append(("source text incompletely verified", altered))
    altered = copy.deepcopy(candidate)
    altered["original_source_verification"]["exact_byte_sha256"] = "0" * 64
    cases.append(("fabricated verified original PDF", altered))
    altered = copy.deepcopy(candidate)
    altered["proposed_changes"][0]["proposed_fields"]["question"] = ""
    cases.append(("blank proposed stem", altered))
    altered = copy.deepcopy(candidate)
    altered["proposed_changes"][1]["changed_fields"] = []
    cases.append(("wrong diff declaration", altered))
    altered = copy.deepcopy(candidate)
    altered["proposed_changes"].append(copy.deepcopy(altered["proposed_changes"][0]))
    cases.append(("duplicate row", altered))
    altered = copy.deepcopy(candidate)
    altered["original_pdf_sha256_expected_from_pinned_registry"] = "0" * 64
    cases.append(("spoofed source PDF hash", altered))
    for name, bad in cases:
        try:
            validate(bad, rows, manifest, registry, sha)
        except (AssertionError, KeyError, ValueError, TypeError):
            continue
        raise AssertionError(f"gate did not reject: {name}")


def main() -> int:
    raw = SHARD.read_bytes()
    physical_sha = hashlib.sha256(raw).hexdigest()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = json.loads(raw)["questions"]
    validate(audit, rows, manifest, registry, physical_sha)
    validate_readonly_sql(audit)
    adversarial_selftest(audit, rows, manifest, registry, physical_sha)
    print("REVIEW-ONLY OCR CANDIDATE QA PASS: 3 records/15 preimages, "
          "4800 official grade tuples untouched by this audit, "
          "10 fail-closed adversarial checks. VERIFIED PDF / HUMAN APPROVAL STILL NO-GO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
