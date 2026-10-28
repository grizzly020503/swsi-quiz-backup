#!/usr/bin/env python3
"""Output a *rollback-only* exact 3,920-row Supabase URL cutover QA plan.

The generator itself is offline, never connects to a database and refuses to
write inside the source repository. Generated SQL ends with ROLLBACK and is
intended to run ONLY in an isolated disposable PG17 fixture. A real migration,
if approved later, needs separate review, authorization and execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from source_url_exact_target_replay import verify
from source_url_promotion_stage import load_unique_json

ROOT = Path(__file__).resolve().parents[1]


def sql_quote(s: str) -> str:
    if not isinstance(s, str) or "\x00" in s:
        raise ValueError("unsafe SQL text value")
    return "'" + s.replace("'", "''") + "'"


def row_index(root: Path) -> dict[str, dict]:
    rows = {}
    for year in range(104, 116):
        for half in (1, 2):
            data = load_unique_json((root / f"cdn/question-shards/{year}-{half}.json").read_bytes())
            if len(data["questions"]) != 200:
                raise ValueError("incomplete 200-question source file")
            for q in data["questions"]:
                if q["id"] in rows:
                    raise ValueError("duplicate official question ID")
                rows[q["id"]] = q
    if len(rows) != 4800:
        raise ValueError("expected 4,800 official question IDs")
    return rows


def generate(repo: Path, scratch: Path) -> tuple[str, str]:
    report = verify(repo, scratch)
    if report["phase"] != "after" or report["changed_source_urls"] != 3920:
        raise ValueError("must use the fully staged, exact SHA-pinned URL-only candidate")
    old, new = row_index(scratch), row_index(repo)
    if set(old) != set(new):
        raise ValueError("before/after question IDs disagree")
    patches, seeds = [], []
    for ident in sorted(old):
        source, target = old[ident], new[ident]
        if ({key: value for key, value in source.items() if key != "source_url"}
                != {key: value for key, value in target.items() if key != "source_url"}):
            raise ValueError(f"Official Core or enrichment changed: {ident}")
        seeds.append((ident, source["source_exam_code"], source["source_url"]))
        if source["source_url"] != target["source_url"]:
            patches.append((ident, source["source_exam_code"], source["source_url"], target["source_url"]))
    if len(patches) != 3920:
        raise ValueError(f"expected 3920 source URL changes, got {len(patches)}")
    values = ",\n".join("(" + ",".join(map(sql_quote, row)) + ")" for row in patches)
    fixture = ",\n".join("(" + ",".join(map(sql_quote, row)) + ")" for row in seeds)
    sql = "\n".join([
        "-- QA-ONLY; NEVER APPLY TO PRODUCTION: SWSI PR #453",
        "-- 3920 exact before/after source URLs, no Official Core changes.",
        "BEGIN;",
        "SET LOCAL lock_timeout='5s';",
        "SET LOCAL statement_timeout='120s';",
        "LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;",
        "CREATE TEMP TABLE swsi_url_patch (id text PRIMARY KEY, exam_code text NOT NULL, before_url text NOT NULL, after_url text NOT NULL) ON COMMIT DROP;",
        "INSERT INTO pg_temp.swsi_url_patch (id,exam_code,before_url,after_url) VALUES",
        values + ";",
        "DO $pre$ DECLARE all_rows int; matched int; BEGIN",
        "SELECT count(*) INTO all_rows FROM public.questions;",
        "IF all_rows <> 4800 THEN RAISE EXCEPTION 'full corpus drift: %',all_rows; END IF;",
        "SELECT count(*) INTO matched FROM public.questions q JOIN pg_temp.swsi_url_patch p ON q.id=p.id AND q.source_exam_code=p.exam_code AND q.source_url=p.before_url;",
        "IF matched <> 3920 THEN RAISE EXCEPTION 'source URL preimage drift: %',matched; END IF;",
        "END $pre$;",
        "UPDATE public.questions q SET source_url=p.after_url FROM pg_temp.swsi_url_patch p WHERE q.id=p.id AND q.source_exam_code=p.exam_code AND q.source_url=p.before_url;",
        "DO $post$ DECLARE matched int; legacy int; BEGIN",
        "SELECT count(*) INTO matched FROM public.questions q JOIN pg_temp.swsi_url_patch p ON q.id=p.id AND q.source_exam_code=p.exam_code AND q.source_url=p.after_url;",
        "IF matched <> 3920 THEN RAISE EXCEPTION 'source URL postimage drift: %',matched; END IF;",
        "SELECT count(*) INTO legacy FROM public.questions q JOIN pg_temp.swsi_url_patch p ON q.id=p.id AND q.source_url=p.before_url;",
        "IF legacy <> 0 THEN RAISE EXCEPTION 'partial source URL patch: %',legacy; END IF;",
        "IF (SELECT count(*) FROM public.questions) <> 4800 THEN RAISE EXCEPTION 'row count changed'; END IF;",
        "END $post$;",
        "SELECT 'SOURCE_URL_QA_POSTIMAGE_3920_PASS';",
        "ROLLBACK;",
        "SELECT 'SOURCE_URL_QA_ROLLBACK_DONE';",
        "",
    ])
    seed = "\n".join([
        "-- Synthetic disposable PG17 fixture; NEVER connect to production",
        "CREATE TABLE public.questions (id text PRIMARY KEY, source_exam_code text, source_url text);",
        "INSERT INTO public.questions (id,source_exam_code,source_url) VALUES",
        fixture + ";",
        "SELECT 'SOURCE_URL_QA_FIXTURE_4800_PASS';",
        "",
    ])
    if "COMMIT;" in sql or not sql.endswith("SELECT 'SOURCE_URL_QA_ROLLBACK_DONE';\n"):
        raise ValueError("generated SQL must always roll back")
    return sql, seed


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--root", type=Path, default=ROOT)
    a.add_argument("--scratch", type=Path, required=True)
    a.add_argument("--sql-out", type=Path, required=True)
    a.add_argument("--synthetic-seed-out", type=Path, required=True)
    v = a.parse_args()
    repo, scratch, sql_out, seed_out = (
        v.root.resolve(), v.scratch.resolve(),
        v.sql_out.resolve(), v.synthetic_seed_out.resolve())
    if (sql_out == seed_out or any(x == repo or repo in x.parents for x in (scratch, sql_out, seed_out))
            or any(x.exists() for x in (scratch, sql_out, seed_out))):
        raise SystemExit("REFUSED: use new outside-repo fixture and outputs only")
    sql, seed = generate(repo, scratch)
    for path, data in ((sql_out, sql), (seed_out, seed)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    print(json.dumps({"result":"ROLLBACK_ONLY_QA", "patch_rows":3920,
                      "seed_rows":4800,
                      "sql_sha256":hashlib.sha256(sql.encode()).hexdigest(),
                      "production_unchanged":True,
                      "no_commit":True},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
