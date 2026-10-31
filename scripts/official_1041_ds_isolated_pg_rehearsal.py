#!/usr/bin/env python3
"""Build a ZERO-SECRETS, isolated PostgreSQL 17 rehearsal from public SWSI CDN shards.

Never connects to production. Output is for ephemeral GitHub Actions postgres service.
The two-step update sequence is a CANDIDATE, not a deployed production fix.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/official_104_1_direct_service_three_ocr_candidate_20261031.json"
SHADOW = ROOT / "audit/official_104_1_direct_service_three_shadow_readonly_20261031.sql"
MANIFEST = ROOT / "cdn/question-shards/manifest.json"
TRIGGER_SNAPSHOT = ROOT / "audit/official_104_1_live_seven_trigger_definitions_20261031.json"
FIELDS = [
    "id", "subject", "year", "round", "qno", "major", "topic", "keywords",
    "question", "opt_a", "opt_b", "opt_c", "opt_d", "answer", "exp_why",
    "exp_others", "exp_trap", "exp_raw", "mnemonic", "extension", "law",
    "mistake", "source_exam_code", "source_url", "analysis_status",
    "analysis_attempts", "analysis_error", "analysis_started_at",
    "analysis_completed_at", "legal_status", "legal_checked_at", "legal_note",
    "legal_source_url", "legal_canonical_names", "accepted_answers",
    "grading_mode", "analysis_last_attempt_at",
]
TYPES = {
    "analysis_attempts": "integer",
    "analysis_started_at": "timestamptz",
    "analysis_completed_at": "timestamptz",
    "legal_checked_at": "timestamptz",
    "analysis_last_attempt_at": "timestamptz",
    "legal_canonical_names": "text[]",
    "accepted_answers": "text[]",
}
TEXT_FIELDS = ("question", "opt_a", "opt_b", "opt_c", "opt_d")
CLEAN_FIELDS = (
    "major", "topic", "keywords", "exp_why", "exp_others", "exp_trap",
    "exp_raw", "mnemonic", "extension", "law", "mistake",
    "analysis_error", "analysis_started_at", "analysis_completed_at",
    "analysis_last_attempt_at",
)


def quoted(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def pg_array(values: list[str]) -> str:
    return "{" + ",".join('"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values) + "}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    path = args.out.resolve()
    if path == ROOT or ROOT in path.parents:
        raise SystemExit("REFUSED: isolated rehearsal SQL must be outside repository")

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert audit["independent_human_approval"] is False
    assert audit["release_approved"] is False
    assert audit["original_pdf_sha256_reverified_in_this_run"] is True
    sql = SHADOW.read_text(encoding="utf-8")
    match = re.search(r"jsonb_array_elements\('((?:''|[^'])*)'::jsonb\)", sql)
    assert match, "missing exactly-pinned full live preimages"
    candidates = json.loads(match.group(1).replace("''", "'"))
    assert len(candidates) == 3
    pre = {x["id"]: x["before"] for x in candidates}
    post = {x["id"]: x["after_text"] for x in candidates}
    assert set(pre) == set(audit["affected_ids"])
    assert all(len(pre[k]) == len(FIELDS) == 37 for k in pre)
    for item in audit["proposed_changes"]:
        assert post[item["id"]] == item["proposed_fields"]
        assert pre[item["id"]]["answer"] == item["official_answer_unchanged"]

    rows = []
    for shard in manifest["shards"]:
        fname = shard["file"]
        assert Path(fname).name == fname and fname.endswith(".json")
        data = (ROOT / "cdn/question-shards" / fname).read_bytes()
        assert hashlib.sha256(data).hexdigest() == shard["sha256"]
        content = json.loads(data)
        assert len(content["questions"]) == shard["question_count"]
        for row in content["questions"]:
            rows.append(pre.get(row["id"], row))
    assert len(rows) == 4800 and len({r["id"] for r in rows}) == 4800
    assert manifest["total_questions"] == 4800
    assert all(row["id"] in {r["id"] for r in rows} for row in pre.values())

    out = io.StringIO()
    out.write("\\set ON_ERROR_STOP on\n")
    out.write("CREATE SCHEMA IF NOT EXISTS public;\n")
    ddl = [f"{name} {TYPES.get(name, 'text')}" for name in FIELDS]
    ddl[0] += " PRIMARY KEY"
    out.write("CREATE TABLE public.questions (" + ", ".join(ddl) + ");\n")
    out.write("CREATE TABLE public.ai_analysis_job_config (id boolean PRIMARY KEY, enabled boolean NOT NULL);\n")
    out.write("INSERT INTO public.ai_analysis_job_config VALUES (true,false);\n")
    out.write("CREATE TABLE public.mock_ai_schedule_events (event text);\n")
    out.write("ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;\n")
    out.write("CREATE POLICY \"public read questions\" ON public.questions FOR SELECT USING (true);\n")
    out.write("COPY public.questions (" + ",".join(FIELDS) + ") FROM STDIN WITH (FORMAT csv, NULL '\\N');\n")
    writer = csv.writer(out, lineterminator="\n")
    for row in rows:
        cells = []
        for key in FIELDS:
            val = row.get(key)
            if val is None:
                cells.append("\\N")
            elif key in ("accepted_answers", "legal_canonical_names"):
                cells.append(pg_array(val) if isinstance(val, list) else str(val))
            else:
                cells.append(str(val))
        writer.writerow(cells)
    out.write("\\.\n")

    # Source-faithful seven live questions triggers; only the external AI
    # scheduler helpers are STUBBED to avoid touching cron, pg_net and secrets.
    # No live DB connection is used by this generated SQL.
    snapshot = json.loads(TRIGGER_SNAPSHOT.read_text(encoding="utf-8"))
    triggers = snapshot.get("triggers")
    assert snapshot["production_question_trigger_count"] == len(triggers) == 7
    assert len({t["tgname"] for t in triggers}) == 7
    assert all(t["tgenabled"] == "O" for t in triggers)
    expected_functions = {
        "sanitize_unverified_law_provenance",
        "sync_question_legal_canonical_names",
        "auto_enable_ai_for_pending_question",
        "auto_stop_ai_when_queue_drains",
        "set_analysis_completed_at",
        "reject_ai_answer_meta_commentary",
        "reset_ai_analysis_on_official_change",
    }
    assert {t["proname"] for t in triggers} == expected_functions
    assert len(snapshot.get("extra_functions", [])) == 1
    for trigger in triggers:
        assert trigger["trigger_def"].startswith("CREATE TRIGGER ")
        assert "ON public.questions FOR EACH ROW EXECUTE FUNCTION " in trigger["trigger_def"]
        assert trigger["trigger_def"].endswith(
            "EXECUTE FUNCTION " + trigger["proname"] + "()"
        ) or trigger["trigger_def"].endswith(
            "EXECUTE FUNCTION public." + trigger["proname"] + "()"
        )
        assert trigger["function_def"].startswith(
            "CREATE OR REPLACE FUNCTION public." + trigger["proname"] + "()"
        )
        assert "CREATE EXTENSION" not in trigger["function_def"].upper()
    out.write("""
-- Synthetic isolated *external* helpers only: no cron/net or credentials.
CREATE OR REPLACE FUNCTION public.enable_swsi_ai_analysis()
RETURNS void LANGUAGE plpgsql AS $external_stub$
BEGIN
 UPDATE public.ai_analysis_job_config SET enabled=true WHERE id=true;
 INSERT INTO public.mock_ai_schedule_events VALUES ('WOULD_ENABLE_AI_CRON_AND_EDGE');
END;$external_stub$;
CREATE OR REPLACE FUNCTION public.maybe_stop_swsi_ai_analysis()
RETURNS jsonb LANGUAGE plpgsql AS $external_stub$
BEGIN
 INSERT INTO public.mock_ai_schedule_events VALUES ('WOULD_MAYBE_STOP_AI_CRON');
 RETURN jsonb_build_object('stopped',true);
END;$external_stub$;
""")
    for fn in snapshot["extra_functions"]:
        out.write(fn.rstrip().rstrip(";") + ";\n")
    for trigger in triggers:
        out.write(trigger["function_def"].rstrip().rstrip(";") + ";\n")
    for trigger in triggers:
        out.write(trigger["trigger_def"].rstrip().rstrip(";") + ";\n")
    out.write("""
CREATE TEMP TABLE swsi_baseline AS SELECT id, to_jsonb(q) original FROM public.questions q;
DO $test$
BEGIN
 IF (SELECT count(*) FROM public.questions) <> 4800 THEN RAISE EXCEPTION 'expected 4800'; END IF;
 IF (SELECT count(*) FROM swsi_baseline) <> 4800 THEN RAISE EXCEPTION 'baseline incomplete'; END IF;
 IF (SELECT count(*) FROM pg_trigger WHERE tgrelid='public.questions'::regclass
        AND NOT tgisinternal AND tgenabled='O') <> 7
 THEN RAISE EXCEPTION 'expected exactly 7 enabled copied production triggers'; END IF;
END;$test$;
""")
    # Demonstrate that the ORIGINAL default path really creates pending and
    # would schedule AI; then roll back. No production calls are possible.
    first = candidates[0]
    out.write(f"""
BEGIN;
UPDATE public.questions SET question = question || ' [ISOLATED SYNTHETIC CHANGE]', analysis_status='review' WHERE id={quoted(first["id"])};
DO $test$
BEGIN
 IF (SELECT analysis_status FROM public.questions WHERE id={quoted(first["id"])}) <> 'pending'
 OR (SELECT count(*) FROM public.mock_ai_schedule_events) <> 1
 OR NOT (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true)
 THEN RAISE EXCEPTION 'default production-like trigger unexpectedly safe'; END IF;
END;$test$;
ROLLBACK;
""")
    # Candidate is a two-step update: Official Core changes first (implicit pending),
    # then explicit review-only status update in the SAME transaction. The
    # existing auto-enable trigger only fires for explicit UPDATE OF analysis_status.
    # It MUST NOT schedule analysis when finalizing a review status.
    props = []
    for change in candidates:
        obj = {"id": change["id"], **change["after_text"]}
        props.append(obj)
    values = json.dumps(props, ensure_ascii=False)
    out.write(f"""
BEGIN;
UPDATE public.questions q
SET question = x.question, opt_a=x.opt_a, opt_b=x.opt_b, opt_c=x.opt_c, opt_d=x.opt_d
FROM jsonb_to_recordset({quoted(values)}::jsonb) AS x(id text, question text, opt_a text,opt_b text,opt_c text,opt_d text)
WHERE q.id=x.id;
DO $test$
BEGIN
 IF (SELECT count(*) FROM public.questions WHERE id IN ('DS-104-1-22','DS-104-1-27','DS-104-1-29') AND analysis_status='pending')<>3
 OR (SELECT count(*) FROM public.mock_ai_schedule_events)<>0
 OR (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true)
 THEN RAISE EXCEPTION 'first official-only UPDATE must reset pending but not launch AI'; END IF;
END;$test$;
UPDATE public.questions SET analysis_status='review'
WHERE id IN ('DS-104-1-22','DS-104-1-27','DS-104-1-29');
DO $test$
DECLARE
  before_json jsonb;
  after_json jsonb;
  changed_count integer;
  grade_changed integer;
BEGIN
 SELECT count(*) INTO changed_count FROM public.questions q JOIN swsi_baseline b USING(id)
 WHERE to_jsonb(q) IS DISTINCT FROM b.original;
 IF changed_count <> 3 THEN RAISE EXCEPTION 'expected exactly 3 modified rows: %',changed_count; END IF;
 IF (SELECT count(*) FROM public.questions WHERE analysis_status='pending') <> 0
 OR (SELECT count(*) FROM public.mock_ai_schedule_events) <> 0
 OR (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true)
 THEN RAISE EXCEPTION 'review mode would trigger AI'; END IF;
 IF (SELECT count(*) FROM public.questions WHERE analysis_status='review') <> 136
 THEN RAISE EXCEPTION 'review count must be 136'; END IF;
 SELECT count(*) INTO grade_changed
 FROM public.questions q JOIN swsi_baseline b USING(id)
 WHERE to_jsonb(q)->'answer' IS DISTINCT FROM b.original->'answer'
    OR to_jsonb(q)->'accepted_answers' IS DISTINCT FROM b.original->'accepted_answers'
    OR to_jsonb(q)->'grading_mode' IS DISTINCT FROM b.original->'grading_mode';
 IF grade_changed <> 0 THEN RAISE EXCEPTION 'grading drift: %',grade_changed; END IF;
END;$test$;
ROLLBACK;
DO $test$
BEGIN
 IF EXISTS(SELECT 1 FROM public.questions q JOIN swsi_baseline b USING(id)
           WHERE to_jsonb(q) IS DISTINCT FROM b.original)
 OR (SELECT count(*) FROM public.mock_ai_schedule_events)<>0
 OR (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true)
 THEN RAISE EXCEPTION 'ROLLBACK not exact for all 4800 rows or AI job state'; END IF;
 RAISE NOTICE 'SWSI ISOLATED PG17 TRANSACTIONAL PASS: unsafe combined update reproduced; two-step 3 safe review postimages; 4797 unchanged; 4800 grade tuples preserved; rollback exact; zero AI events';
END;$test$;
""")
    content = out.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print("Generated ISOLATED PG17 source-faithful 7-trigger dry-run from 4800 public questions, " +
          str(len(content.encode("utf-8"))) + " UTF-8 bytes; NO production DB credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
