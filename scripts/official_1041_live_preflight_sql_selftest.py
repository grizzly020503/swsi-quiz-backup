#!/usr/bin/env python3
"""Static, fail-closed guard for the three-row production READ-ONLY preflight SQL.

Does not open a DB connection, inspect private data, or grant source approval.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "audit/official_1041_live_release_preflight_readonly_20261101.sql"

PROTECTED = (
    "FALSE AS independent_human_original_pdf_approval",
    "FALSE AS production_faithful_private_restore_proven",
    "FALSE AS permission_to_modify_official_core",
    "'HOLD_NO_PRODUCTION_DML_OR_DEPLOY'::text AS release_gate",
    "tc.compared=7 AND tc.drift=0",
    "dc.compared=3 AND dc.drift=0",
    "q.enabled IS FALSE AND q.active_ai_named_jobs=0",
)
FORBIDDEN_SQL = re.compile(
    r"\\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|"
    r"GRANT|REVOKE|CALL|DO|EXECUTE|COPY|PERFORM|COMMIT|ROLLBACK|"
    r"SECURITY\\s+DEFINER)\\b", re.IGNORECASE,
)


def validate(sql: str) -> None:
    code = "\n".join(line for line in sql.splitlines()
                      if not line.lstrip().startswith("--"))
    require = lambda condition, msg: (_ for _ in ()).throw(AssertionError(msg)) if not condition else None
    require(code.lstrip().startswith("WITH\n"), "must have only read-only SELECT CTE")
    require(code.rstrip().endswith(";"), "one terminated read-only statement required")
    # Ignore SQL string literals when validating keywords/statement separators;
    # the string 'UPDATE' in a has_table_privilege check is not an SQL UPDATE.
    stripped = re.sub(r"'(?:''|[^'])*'", "''", code)
    require(stripped.count(";") == 1, "multiple SQL statements not permitted")
    require(not FORBIDDEN_SQL.search(stripped), "unexpected write/privileged SQL statement")
    require("SELECT\n  (tc.compared=7" in code, "missing final SELECT-only report")
    for fragment in PROTECTED:
        require(fragment in code, "release safety/HOLD gate removed: " + fragment)
    require("md5(pg_get_triggerdef(t.oid))" in code, "trigger source hash not checked")
    require("md5(pg_get_functiondef(p.oid))" in code, "function source hash not checked")
    require("FULL OUTER JOIN current_trigger" in code, "new/missing triggers must fail")
    require("FULL OUTER JOIN current_dependency" in code, "new/missing functions must fail")
    require("has_table_privilege('anon','public.questions','UPDATE')" in code,
            "anonymous mutation privilege not checked")
    require("has_table_privilege('authenticated','public.questions','UPDATE')" in code,
            "authenticated mutation privilege not checked")
    require("FROM cron.job" in code and "active_ai_named_jobs" in code,
            "AI scheduler cron safety not checked")


def main() -> int:
    sql = SQL_PATH.read_text(encoding="utf-8")
    validate(sql)
    negatives = [
        sql.replace("FALSE AS permission_to_modify_official_core",
                    "TRUE AS permission_to_modify_official_core"),
        sql.replace("tc.compared=7 AND tc.drift=0", "tc.compared=6 AND tc.drift=0"),
        sql.replace("md5(pg_get_triggerdef(t.oid))", "''"),
        sql + "\nDELETE FROM public.questions;",
    ]
    for n, bad in enumerate(negatives, 1):
        try:
            validate(bad)
        except AssertionError:
            continue
        raise AssertionError(f"unsafe preflight mutation accepted: {n}")
    print("104-1 LIVE RELEASE PREFLIGHT STATIC QA PASS: SELECT-only, "
          "7 original triggers, 3 dependent functions, 4 negative mutations; "
          "human approval + private restore remain NO-GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
