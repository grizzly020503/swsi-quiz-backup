#!/usr/bin/env python3
"""Generate rollback-only 104-1 DS official source correction transaction.

DRAFT / NO-GO: human approval is FALSE; never execute on the production DB.
The resulting SQL is ONLY for disposable restored Postgres 17 verification:
it verifies all 37 live columns of three before-images, all 4800 rows, the
seven production question triggers, two-step review-only update, then ROLLBACK.
Nothing here uses credentials, a network, a production connection, or an API.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/official_104_1_direct_service_three_ocr_candidate_20261031.json"
SHADOW = ROOT / "audit/official_104_1_direct_service_three_shadow_readonly_20261031.sql"
IDS = {"DS-104-1-22": "A", "DS-104-1-27": "B", "DS-104-1-29": "D"}
FIVE = {"question", "opt_a", "opt_b", "opt_c", "opt_d"}
TRIGGERS = {
    "questions_00_sanitize_unverified_law_provenance",
    "questions_sync_legal_canonical_names",
    "trg_auto_enable_ai_pending",
    "trg_auto_stop_ai_queue",
    "trg_questions_analysis_completed_at",
    "trg_reject_ai_answer_meta_commentary",
    "trg_reset_ai_on_official_change",
}
ALLOWED_CHANGES = {
    "question", "opt_a", "opt_b", "opt_c", "opt_d",
    "major", "topic", "keywords", "exp_why", "exp_others", "exp_trap",
    "exp_raw", "mnemonic", "extension", "law", "mistake", "analysis_status",
    "analysis_attempts", "analysis_error", "analysis_started_at",
    "analysis_completed_at", "analysis_last_attempt_at", "legal_canonical_names",
}


def sql_literal(data: object) -> str:
    return "'" + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("'", "''") + "'"


def fail_unless(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError("RELEASE HOLD: " + message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    path = args.out.resolve()
    fail_unless(path != ROOT and ROOT not in path.parents, "never write tracked repository files")
    fail_unless(not path.exists(), "output must not exist (overwrite refused)")

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    fail_unless(audit["status"] == "DRAFT_ORIGINAL_MOEX_PDF_VERIFIED_HUMAN_APPROVAL_REQUIRED"
                and audit["independent_human_approval"] is False
                and audit["release_approved"] is False
                and audit["production_database_written"] is False
                and audit["netlify_backup_changed"] is False,
                "not an unapproved, untouched production candidate")
    fail_unless(audit["original_pdf_sha256_reverified_in_this_run"] is True,
                "original PDF verification not recorded")
    shadow = SHADOW.read_text(encoding="utf-8")
    match = re.search(r"jsonb_array_elements\('((?:''|[^'])*)'::jsonb\)", shadow)
    fail_unless(match is not None, "missing exact full 37-column live snapshots")
    candidates = json.loads(match.group(1).replace("''", "'"))
    fail_unless(len(candidates) == 3 and {item["id"] for item in candidates} == set(IDS),
                "candidate IDs drifted")
    correction = {item["id"]: item for item in audit["proposed_changes"]}
    fail_unless(set(correction) == set(IDS), "source proposal drifted")
    payload = []
    for item in candidates:
        ident = item["id"]
        before = item["before"]
        after = item["after_text"]
        proof = correction[ident]
        fail_unless(len(before) == 37 and set(after) == FIVE,
                    "must carry exact 37 columns and five text fields")
        fail_unless(all(before[k] == proof["preimage_fields"][k] and
                        after[k] == proof["proposed_fields"][k] for k in FIVE),
                    "preimage/source candidate mismatch: " + ident)
        fail_unless(before["answer"] == IDS[ident] ==
                    proof["official_answer_unchanged"] and
                    before["accepted_answers"] == proof["accepted_answers_unchanged"] and
                    before["grading_mode"] == proof["grading_mode_unchanged"] == "standard",
                    "official grading drift: " + ident)
        fail_unless(before["source_exam_code"] == "104030" and
                    before["subject"] == "社會工作直接服務",
                    "wrong official exam identity")
        payload.append({"id": ident, "before": before, "after_text": after})
    fail_unless(len({x["id"] for x in payload}) == 3, "duplicate release target")

    item_values = sql_literal(payload)
    trigger_values = ", ".join("'" + item + "'" for item in sorted(TRIGGERS))
    allowed_values = ", ".join("'" + item + "'" for item in sorted(ALLOWED_CHANGES))
    result = r"""-- NOT FOR PRODUCTION. DRAFT / NO-GO. Human source approval remains FALSE.
-- Generated from frozen 37-column production snapshots; only execute on a
-- disposable, isolated PostgreSQL 17 restored TEST database.
-- There is no COMMIT path. On any test failure, psql ON_ERROR_STOP aborts;
-- the database session ends without committing the transaction.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='60s';
CREATE TEMP TABLE swsi_1041_expected ON COMMIT DROP AS
  SELECT x->>'id' AS id, x->'before' AS old_record, x->'after_text' AS source_text
  FROM jsonb_array_elements(%PAYLOAD%::jsonb) AS x;
CREATE TEMP TABLE swsi_1041_before ON COMMIT DROP AS
  SELECT id, to_jsonb(q) AS old_record FROM public.questions q;

DO $swsi_preflight$
DECLARE
  current_triggers text[];
BEGIN
 IF (SELECT count(*) FROM swsi_1041_expected) <> 3
 OR (SELECT count(*) FROM swsi_1041_before) <> 4800
 OR (SELECT count(*) FROM public.questions) <> 4800
 OR (SELECT count(*) FROM public.questions WHERE analysis_status='pending') <> 0
 THEN RAISE EXCEPTION 'unexpected corpus size or pending analysis state'; END IF;
 IF (SELECT coalesce(enabled,true) FROM public.ai_analysis_job_config WHERE id=true) IS DISTINCT FROM false
 THEN RAISE EXCEPTION 'AI scheduler is not explicitly disabled'; END IF;
 SELECT array_agg(t.tgname ORDER BY t.tgname) INTO current_triggers
 FROM pg_trigger t WHERE t.tgrelid='public.questions'::regclass
 AND NOT t.tgisinternal AND t.tgenabled='O';
 IF current_triggers IS DISTINCT FROM ARRAY[%TRIGGERS%]::text[]
 THEN RAISE EXCEPTION 'production-like seven question triggers required'; END IF;
 IF EXISTS(
   SELECT 1 FROM swsi_1041_expected e
   LEFT JOIN public.questions q ON q.id=e.id
   WHERE q.id IS NULL OR to_jsonb(q) IS DISTINCT FROM e.old_record
 ) THEN RAISE EXCEPTION 'three 37-column source preimages drifted'; END IF;
 IF EXISTS(
   SELECT 1 FROM swsi_1041_expected e
   WHERE (SELECT count(*) FROM jsonb_object_keys(e.old_record)) <> 37
 ) THEN RAISE EXCEPTION 'not a 37-column production preimage'; END IF;
END;$swsi_preflight$;

-- FIRST statement: official text only. The real BEFORE trigger resets
-- enrichment and marks pending, but AFTER UPDATE OF analysis_status does
-- not fire because that column is NOT explicitly mentioned in this SET.
UPDATE public.questions q
SET question=e.source_text->>'question',
    opt_a=e.source_text->>'opt_a', opt_b=e.source_text->>'opt_b',
    opt_c=e.source_text->>'opt_c', opt_d=e.source_text->>'opt_d'
FROM swsi_1041_expected e
WHERE q.id=e.id;

DO $swsi_after_text$
BEGIN
 IF (SELECT count(*) FROM public.questions q JOIN swsi_1041_expected e USING(id)
     WHERE q.analysis_status='pending') <> 3
 OR (SELECT coalesce(enabled,true) FROM public.ai_analysis_job_config WHERE id=true)
    IS DISTINCT FROM false
 THEN RAISE EXCEPTION 'first official-only update did not safely reset'; END IF;
END;$swsi_after_text$;

-- SECOND statement: review-only status; no Official Core fields in SET.
UPDATE public.questions q SET analysis_status='review'
FROM swsi_1041_expected e WHERE q.id=e.id;

DO $swsi_postcheck$
BEGIN
 IF (SELECT count(*) FROM public.questions) <> 4800
 OR (SELECT count(*) FROM public.questions WHERE analysis_status='pending') <> 0
 OR (SELECT count(*) FROM public.questions WHERE analysis_status='review') <> 136
 OR (SELECT count(*) FROM public.questions WHERE analysis_status='ready') <> 4664
 OR (SELECT coalesce(enabled,true) FROM public.ai_analysis_job_config WHERE id=true)
    IS DISTINCT FROM false
 THEN RAISE EXCEPTION 'review/ready totals or AI scheduler not safe'; END IF;
 IF (SELECT count(*) FROM public.questions q JOIN swsi_1041_before b USING(id)
     WHERE to_jsonb(q) IS DISTINCT FROM b.old_record) <> 3
 THEN RAISE EXCEPTION 'exact three changed rows required'; END IF;
 IF EXISTS(
   SELECT 1 FROM public.questions q JOIN swsi_1041_before b USING(id)
   WHERE q.id NOT IN (SELECT id FROM swsi_1041_expected)
     AND to_jsonb(q) IS DISTINCT FROM b.old_record
 ) THEN RAISE EXCEPTION 'unrelated Official Core row was changed'; END IF;
 IF EXISTS(
   SELECT 1 FROM public.questions q JOIN swsi_1041_before b USING(id)
   WHERE (to_jsonb(q)->'answer') IS DISTINCT FROM (b.old_record->'answer')
   OR (to_jsonb(q)->'accepted_answers') IS DISTINCT FROM (b.old_record->'accepted_answers')
   OR (to_jsonb(q)->'grading_mode') IS DISTINCT FROM (b.old_record->'grading_mode')
 ) THEN RAISE EXCEPTION 'grading drift detected'; END IF;
 IF EXISTS(
   SELECT 1 FROM public.questions q JOIN swsi_1041_expected e USING(id)
   WHERE q.analysis_status <> 'review'
      OR q.question IS DISTINCT FROM e.source_text->>'question'
      OR q.opt_a IS DISTINCT FROM e.source_text->>'opt_a'
      OR q.opt_b IS DISTINCT FROM e.source_text->>'opt_b'
      OR q.opt_c IS DISTINCT FROM e.source_text->>'opt_c'
      OR q.opt_d IS DISTINCT FROM e.source_text->>'opt_d'
 ) THEN RAISE EXCEPTION 'source postimage mismatch'; END IF;
 IF EXISTS (
   SELECT 1 FROM public.questions q JOIN swsi_1041_before b USING(id),
       LATERAL jsonb_each(b.old_record) AS kv(key,value)
   WHERE q.id IN (SELECT id FROM swsi_1041_expected)
     AND kv.value IS DISTINCT FROM to_jsonb(q)->kv.key
     AND kv.key NOT IN (%ALLOWED%)
 ) THEN RAISE EXCEPTION 'an unauthorized production column changed'; END IF;
 IF EXISTS(
   SELECT 1 FROM public.questions q JOIN swsi_1041_expected e USING(id)
   WHERE q.major IS NOT NULL OR q.topic IS NOT NULL OR q.keywords IS NOT NULL
     OR q.exp_why IS NOT NULL OR q.exp_others IS NOT NULL OR q.exp_trap IS NOT NULL
     OR q.exp_raw IS NOT NULL OR q.mnemonic IS NOT NULL OR q.extension IS NOT NULL
     OR q.law IS NOT NULL OR q.mistake IS NOT NULL
     OR q.analysis_attempts <> 0 OR q.analysis_error IS NOT NULL
     OR q.analysis_started_at IS NOT NULL OR q.analysis_completed_at IS NOT NULL
     OR q.analysis_last_attempt_at IS NOT NULL
 ) THEN RAISE EXCEPTION 'stale analysis metadata retained'; END IF;
 RAISE NOTICE 'SWSI ROLLBACK-ONLY FULL 37COL POSTCHECK PASS: 3 source posts / 4797 unchanged / 4800 grades / zero pending and AI disabled';
END;$swsi_postcheck$;

ROLLBACK;
SELECT CASE WHEN count(*)=4800
 AND (SELECT coalesce(enabled,true) FROM public.ai_analysis_job_config WHERE id=true) IS FALSE
 AND (SELECT count(*) FROM public.questions q JOIN swsi_1041_expected e ON q.id=e.id) = 0
 THEN 'UNREACHABLE TEMP TABLE AFTER ROLLBACK'
 ELSE 'ROLLBACK_EXECUTED_TEMP_TABLE_REMOVED'
 END AS rollback_status
FROM public.questions;
"""
    # DROP happens as part of ROLLBACK; do not reference rolled-back temp tables.
    result = result[:result.index("SELECT CASE WHEN count(*)=4800\n")] + """SELECT CASE WHEN count(*)=4800 AND
 (SELECT coalesce(enabled,true) FROM public.ai_analysis_job_config WHERE id=true) IS FALSE
 THEN 'ROLLBACK_COMPLETED_4800_ROWS_AI_DISABLED'
 ELSE 'ROLLBACK_POSTCHECK_BLOCKED' END AS rollback_status
FROM public.questions;
"""
    result = (result.replace("%PAYLOAD%", item_values)
                    .replace("%TRIGGERS%", trigger_values)
                    .replace("%ALLOWED%", allowed_values))
    fail_unless(result.count("ROLLBACK;") == 1 and
                not re.search(r"\bCOMMIT\s*;", result, re.I), "no commit possible")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result, encoding="utf-8")
    print("DRAFT ONLY ROLLBACK SQL PREPARED: strict 3x37 preimages, "
          "7 real question triggers, source-only then review-only updates, "
          "4797 non-target rows, 4800 grading tuples, ROLLBACK; no DB accessed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
