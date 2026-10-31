#!/usr/bin/env python3
"""Build a ZERO-SECRETS, isolated PostgreSQL 17 rehearsal from public SWSI CDN shards.

Never connects to production. Output is for ephemeral GitHub Actions postgres service.
The patched trigger below is a REVIEW CANDIDATE, not a deployed production fix.
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

    # Isolated stand-in for the actual production scheduling side effect.
    # It *never* schedules cron or makes an HTTP request.
    out.write("""
CREATE FUNCTION public.enable_swsi_ai_analysis() RETURNS void LANGUAGE plpgsql AS $fn$
BEGIN
 UPDATE public.ai_analysis_job_config SET enabled=true WHERE id=true;
 INSERT INTO public.mock_ai_schedule_events VALUES ('WOULD_ENABLE_AI_CRON_AND_EDGE');
END;$fn$;
CREATE FUNCTION public.auto_enable_ai_for_pending_question() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
 IF NEW.source_exam_code IS NOT NULL AND NEW.analysis_status='pending' THEN
   IF NOT (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true) THEN
      PERFORM public.enable_swsi_ai_analysis();
   END IF;
 END IF;
 RETURN NEW;
END;$fn$;
CREATE FUNCTION public.reset_ai_analysis_on_official_change() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
 IF NEW.source_exam_code IS NOT NULL AND (
      NEW.question IS DISTINCT FROM OLD.question
   OR NEW.opt_a IS DISTINCT FROM OLD.opt_a OR NEW.opt_b IS DISTINCT FROM OLD.opt_b
   OR NEW.opt_c IS DISTINCT FROM OLD.opt_c OR NEW.opt_d IS DISTINCT FROM OLD.opt_d
   OR NEW.answer IS DISTINCT FROM OLD.answer
   OR NEW.accepted_answers IS DISTINCT FROM OLD.accepted_answers
   OR NEW.grading_mode IS DISTINCT FROM OLD.grading_mode
 ) THEN
   NEW.major := NULL; NEW.topic := NULL; NEW.keywords := NULL;
   NEW.exp_why := NULL; NEW.exp_others := NULL; NEW.exp_trap := NULL;
   NEW.exp_raw := NULL; NEW.mnemonic := NULL; NEW.extension := NULL;
   NEW.law := NULL; NEW.mistake := NULL;
   NEW.analysis_attempts := 0; NEW.analysis_error := NULL;
   NEW.analysis_started_at := NULL; NEW.analysis_completed_at := NULL;
   NEW.analysis_last_attempt_at := NULL;
   IF current_setting('swsi.official_core_review_only',true)='on'
      AND session_user='postgres' THEN
      NEW.analysis_status := 'review';
   ELSE
      NEW.analysis_status := 'pending';
   END IF;
 END IF;
 RETURN NEW;
END;$fn$;
CREATE TRIGGER trg_reset_ai_on_official_change BEFORE UPDATE OF question,opt_a,opt_b,opt_c,opt_d,answer,accepted_answers,grading_mode
ON public.questions FOR EACH ROW EXECUTE FUNCTION public.reset_ai_analysis_on_official_change();
CREATE TRIGGER trg_auto_enable_ai_pending AFTER INSERT OR UPDATE OF analysis_status
ON public.questions FOR EACH ROW EXECUTE FUNCTION public.auto_enable_ai_for_pending_question();
CREATE TEMP TABLE swsi_baseline AS SELECT id, to_jsonb(q) original FROM public.questions q;
DO $test$
BEGIN
 IF (SELECT count(*) FROM public.questions) <> 4800 THEN RAISE EXCEPTION 'expected 4800'; END IF;
 IF (SELECT count(*) FROM swsi_baseline) <> 4800 THEN RAISE EXCEPTION 'baseline incomplete'; END IF;
END;$test$;
""")
    # Demonstrate that the ORIGINAL default path really creates pending and
    # would schedule AI; then roll back. No production calls are possible.
    first = candidates[0]
    out.write(f"""
BEGIN;
UPDATE public.questions SET question = question || ' [ISOLATED SYNTHETIC CHANGE]' WHERE id={quoted(first["id"])};
DO $test$
BEGIN
 IF (SELECT analysis_status FROM public.questions WHERE id={quoted(first["id"])}) <> 'pending'
 OR (SELECT count(*) FROM public.mock_ai_schedule_events) <> 1
 OR NOT (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true)
 THEN RAISE EXCEPTION 'default production-like trigger unexpectedly safe'; END IF;
END;$test$;
ROLLBACK;
""")
    # Approved-mode candidate: 3 source-text rows, all 5 official text fields.
    props = []
    for change in candidates:
        obj = {"id": change["id"], **change["after_text"]}
        props.append(obj)
    values = json.dumps(props, ensure_ascii=False)
    out.write(f"""
BEGIN;
SET LOCAL swsi.official_core_review_only='on';
UPDATE public.questions q
SET question = x.question, opt_a=x.opt_a, opt_b=x.opt_b, opt_c=x.opt_c, opt_d=x.opt_d
FROM jsonb_to_recordset({quoted(values)}::jsonb) AS x(id text, question text, opt_a text,opt_b text,opt_c text,opt_d text)
WHERE q.id=x.id;
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
 RAISE NOTICE 'SWSI ISOLATED PG17 TRANSACTIONAL PASS: unsafe default reproduced; 3 safe review postimages; 4797 unchanged; 4800 grade tuples preserved; rollback exact; zero AI events';
END;$test$;
""")
    content = out.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print("Generated ISOLATED PostgreSQL 17 dry-run from 4800 public questions, " +
          str(len(content.encode("utf-8"))) + " UTF-8 bytes; NO production DB credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
