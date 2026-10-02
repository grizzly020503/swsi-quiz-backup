#!/usr/bin/env python3
"""Isolated Supabase recovery dry-run against a disposable PostgreSQL database."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "supabase" / "recovery" / "recovery_manifest.json"
SHARD_DIR = ROOT / "cdn" / "question-shards"


def psql(*, sql: str | None = None, file: Path | None = None, capture: bool = False) -> str:
    if (sql is None) == (file is None):
        raise RuntimeError("psql requires exactly one of sql or file")
    cmd = ["psql", "-X", "-v", "ON_ERROR_STOP=1"]
    if capture:
        cmd += ["-A", "-t", "-F", "|"]
    if sql is not None:
        cmd += ["-c", sql]
    else:
        cmd += ["-f", str(file)]
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=True,
    )
    return (result.stdout or "").strip()


def setup_portable_supabase_harness() -> None:
    psql(
        sql=r"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
    EXECUTE 'CREATE ROLE anon NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
    EXECUTE 'CREATE ROLE authenticated NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN
    EXECUTE 'CREATE ROLE service_role NOLOGIN';
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
  id uuid PRIMARY KEY
);
CREATE EXTENSION IF NOT EXISTS pgcrypto;
"""
    )


def render_recovery_sql(manifest: dict) -> tuple[Path, dict[str, int]]:
    base = ROOT / manifest["base_schema"]
    if not base.is_file():
        raise RuntimeError(f"recovery base schema missing: {base.relative_to(ROOT)}")

    skipped = {name: 0 for name in manifest["portable_ci"]["skip_extensions"]}
    chunks = [
        "SET check_function_bodies = off;\n",
        f"-- BEGIN {base.relative_to(ROOT)}\n",
        base.read_text(encoding="utf-8"),
        f"\n-- END {base.relative_to(ROOT)}\n",
    ]

    for rel in manifest["migration_order"]:
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f"recovery migration missing: {rel}")
        text = path.read_text(encoding="utf-8")
        for ext in skipped:
            pattern = re.compile(
                rf"(?im)^[ \t]*create[ \t]+extension[ \t]+if[ \t]+not[ \t]+exists[ \t]+{re.escape(ext)}[ \t]*;[ \t]*$"
            )
            text, count = pattern.subn(
                f"-- portable DR CI: skipped Supabase-managed extension {ext};",
                text,
            )
            skipped[ext] += count
        chunks += [f"\n-- BEGIN {rel}\n", text, f"\n-- END {rel}\n"]

    for ext, count in skipped.items():
        if count < 1:
            raise RuntimeError(f"expected recovery migration to declare {ext}; found {count}")

    tmp = Path(tempfile.gettempdir()) / "swsi_supabase_recovery.sql"
    tmp.write_text("".join(chunks), encoding="utf-8")
    return tmp, skipped


def query_list(sql: str) -> list[str]:
    out = psql(sql=sql, capture=True)
    return [line for line in out.splitlines() if line.strip()]


def assert_schema(manifest: dict) -> None:
    expected_tables = sorted(manifest["expected"]["public_tables"])
    actual_tables = query_list(
        "select tablename from pg_tables where schemaname='public' order by tablename"
    )
    if actual_tables != expected_tables:
        raise AssertionError(
            f"public table set mismatch: expected={expected_tables} actual={actual_tables}"
        )

    qcols = query_list(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name='questions' order by ordinal_position"
    )
    ecols = query_list(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name='essays' order by ordinal_position"
    )
    if len(qcols) != int(manifest["expected"]["question_columns"]):
        raise AssertionError(f"questions column count mismatch: {len(qcols)}")
    if len(ecols) != int(manifest["expected"]["essay_columns"]):
        raise AssertionError(f"essays column count mismatch: {len(ecols)}")

    for required in (
        "accepted_answers",
        "grading_mode",
        "legal_canonical_names",
        "analysis_attempts",
        "analysis_completed_at",
        "analysis_last_attempt_at",
    ):
        if required not in qcols:
            raise AssertionError(f"questions recovery column missing: {required}")

    rls = set(
        query_list(
            "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relkind='r' and c.relrowsecurity order by c.relname"
        )
    )
    missing_rls = set(expected_tables) - rls
    if missing_rls:
        raise AssertionError(f"RLS missing after recovery: {sorted(missing_rls)}")

    privilege = psql(
        sql=(
            "select "
            "has_table_privilege('anon','public.questions','SELECT'),"
            "has_table_privilege('anon','public.questions','INSERT'),"
            "has_table_privilege('anon','public.essays','SELECT'),"
            "has_table_privilege('anon','public.essays','UPDATE'),"
            "has_table_privilege('anon','public.swsi_feedback_reports','SELECT'),"
            "has_table_privilege('anon','public.swsi_feedback_reports','INSERT'),"
            "has_function_privilege('anon','public.reset_ai_analysis_on_official_change()','EXECUTE')"
        ),
        capture=True,
    )
    if privilege != "t|f|t|f|f|f|f":
        raise AssertionError(f"public privilege recovery mismatch: {privilege}")


def pg_array(values) -> str | None:
    if values is None:
        return None
    if not isinstance(values, list):
        raise AssertionError(
            f"accepted_answers must be list/null, got {type(values).__name__}"
        )
    return "{" + ",".join(str(v) for v in values) + "}"


def restore_official_questions(manifest: dict) -> None:
    manifest_json = json.loads(
        (SHARD_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    expected = manifest["expected"]
    if int(manifest_json.get("total_questions", -1)) != int(
        expected["official_questions"]
    ):
        raise AssertionError("question manifest total mismatch")
    if int(manifest_json.get("shard_count", -1)) != int(expected["shard_count"]):
        raise AssertionError("question manifest shard count mismatch")

    rows: list[dict] = []
    for meta in manifest_json["shards"]:
        path = SHARD_DIR / meta["file"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise AssertionError(f"question shard sha mismatch: {meta['file']}")
        payload = json.loads(raw)
        items = payload.get("questions") or []
        if len(items) != int(meta["question_count"]):
            raise AssertionError(f"question shard count mismatch: {meta['file']}")
        rows.extend(items)

    if len(rows) != int(expected["official_questions"]):
        raise AssertionError(f"loaded question count mismatch: {len(rows)}")

    grading = Counter(
        str(row.get("grading_mode") or "standard") for row in rows
    )
    if dict(grading) != expected["grading_mode_counts"]:
        raise AssertionError(
            f"question grading distribution mismatch: {dict(grading)}"
        )
    accepted = sum(
        1 for row in rows if row.get("accepted_answers") is not None
    )
    if accepted != int(expected["accepted_answers_questions"]):
        raise AssertionError(f"accepted_answers count mismatch: {accepted}")

    fields = [
        "id",
        "subject",
        "year",
        "round",
        "qno",
        "major",
        "topic",
        "keywords",
        "question",
        "opt_a",
        "opt_b",
        "opt_c",
        "opt_d",
        "answer",
        "accepted_answers",
        "grading_mode",
        "exp_why",
        "exp_others",
        "exp_trap",
        "exp_raw",
        "mnemonic",
        "extension",
        "law",
        "mistake",
        "source_exam_code",
        "source_url",
        "analysis_status",
        "legal_status",
        "legal_checked_at",
        "legal_note",
        "legal_source_url",
    ]
    csv_path = Path(tempfile.gettempdir()) / "swsi_questions_restore.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        for row in rows:
            values = []
            for field in fields:
                value = row.get(field)
                if field == "accepted_answers":
                    value = pg_array(value)
                values.append(value)
            writer.writerow(values)

    psql(sql="alter table public.questions disable trigger user")
    copy_sql = Path(tempfile.gettempdir()) / "swsi_questions_copy.sql"
    columns = ",".join(fields)
    copy_sql.write_text(
        f"\\copy public.questions ({columns}) from '{csv_path}' "
        "with (format csv, header true, encoding 'UTF8');\n",
        encoding="utf-8",
    )
    psql(file=copy_sql)
    psql(sql="alter table public.questions enable trigger user")

    stats = psql(
        sql=(
            "select count(*),"
            "count(*) filter (where accepted_answers is not null),"
            "count(*) filter (where grading_mode='standard'),"
            "count(*) filter (where grading_mode='all_credit'),"
            "count(*) filter (where grading_mode='any_answer') "
            "from public.questions"
        ),
        capture=True,
    )
    expected_stats = (
        f"{expected['official_questions']}|"
        f"{expected['accepted_answers_questions']}|"
        f"{expected['grading_mode_counts']['standard']}|"
        f"{expected['grading_mode_counts']['all_credit']}|"
        f"{expected['grading_mode_counts']['any_answer']}"
    )
    if stats != expected_stats:
        raise AssertionError(
            f"restored question stats mismatch: expected={expected_stats} actual={stats}"
        )


def assert_official_change_trigger() -> None:
    psql(
        sql=r"""
insert into public.questions(
  id, subject, year, round, qno, question, opt_a, opt_b, opt_c, opt_d,
  answer, grading_mode, source_exam_code, analysis_status, exp_why
) values (
  'DR-TRIGGER-TEST', 'DR', '999', '第一次', '1', 'synthetic',
  'A', 'B', 'C', 'D', 'A', 'standard', 'DR999', 'ready', 'must-clear'
);

update public.questions
set answer='B'
where id='DR-TRIGGER-TEST';
"""
    )
    state = psql(
        sql=(
            "select analysis_status,coalesce(exp_why,'<NULL>') "
            "from public.questions where id='DR-TRIGGER-TEST'"
        ),
        capture=True,
    )
    if state != "pending|<NULL>":
        raise AssertionError(f"official-change reset trigger mismatch: {state}")
    psql(sql="delete from public.questions where id='DR-TRIGGER-TEST'")


def main() -> int:
    started = time.monotonic()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if int(manifest.get("schema_version", -1)) != 1:
        raise AssertionError("unsupported recovery manifest schema")

    setup_portable_supabase_harness()
    recovery_sql, skipped = render_recovery_sql(manifest)
    psql(file=recovery_sql)
    assert_schema(manifest)
    restore_official_questions(manifest)
    assert_official_change_trigger()

    elapsed = time.monotonic() - started
    print(
        "SUPABASE ISOLATED RECOVERY DRY-RUN OK "
        f"tables={len(manifest['expected']['public_tables'])} "
        f"questions={manifest['expected']['official_questions']} "
        f"shards={manifest['expected']['shard_count']} "
        f"skip_extensions={','.join(k for k, v in skipped.items() if v)} "
        f"elapsed_seconds={elapsed:.1f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
