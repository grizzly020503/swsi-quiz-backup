#!/usr/bin/env python3
"""Fail-closed recovery smoke for the SWSI Cloudflare D1 quota schema.

This test never contacts Cloudflare. It proves that the repo-owned recovery
bootstrap can satisfy the CURRENT Worker's quota SQL contract in a clean SQLite
DB and that destructive statements are not added to the bootstrap.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "cloudflare" / "wandering-wave-4418" / "d1" / "recovery_schema.sql"
WORKER = ROOT / "cloudflare" / "wandering-wave-4418" / "worker.js"

CLIENT_TABLE = "ai_daily_client_usage"
GLOBAL_TABLE = "ai_daily_global_usage"

REQUIRED_COLUMNS = {
    CLIENT_TABLE: {"usage_date", "client_key", "text_count", "photo_count", "updated_at"},
    GLOBAL_TABLE: {"usage_date", "text_count", "photo_count", "updated_at"},
}

DESTRUCTIVE_BOOTSTRAP = re.compile(r"\b(DROP|DELETE|TRUNCATE|ALTER)\b", re.IGNORECASE)

CLIENT_RESERVE_SQL = """
INSERT INTO ai_daily_client_usage
  (usage_date, client_key, text_count, photo_count, updated_at)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(usage_date, client_key) DO UPDATE SET
  text_count = text_count + excluded.text_count,
  photo_count = photo_count + excluded.photo_count,
  updated_at = CURRENT_TIMESTAMP
WHERE
  (excluded.text_count = 0 OR text_count < ?)
  AND (excluded.photo_count = 0 OR photo_count < ?)
"""

GLOBAL_RESERVE_SQL = """
INSERT INTO ai_daily_global_usage
  (usage_date, text_count, photo_count, updated_at)
VALUES (?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(usage_date) DO UPDATE SET
  text_count = text_count + excluded.text_count,
  photo_count = photo_count + excluded.photo_count,
  updated_at = CURRENT_TIMESTAMP
WHERE
  (excluded.text_count = 0 OR text_count < ?)
  AND (excluded.photo_count = 0 OR photo_count < ?)
"""


def fail(message: str) -> None:
    raise SystemExit(f"D1 RECOVERY SMOKE FAILED: {message}")


def table_info(db: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows:
        fail(f"missing table: {table}")
    return rows


def verify_schema_shape(db: sqlite3.Connection) -> None:
    for table, required in REQUIRED_COLUMNS.items():
        rows = table_info(db, table)
        columns = {row["name"] for row in rows}
        missing = sorted(required - columns)
        if missing:
            fail(f"{table} missing required columns: {', '.join(missing)}")

        for counter in ("text_count", "photo_count"):
            row = next(item for item in rows if item["name"] == counter)
            if not row["notnull"]:
                fail(f"{table}.{counter} must be NOT NULL")

    client_pk = {
        row["name"]: int(row["pk"])
        for row in table_info(db, CLIENT_TABLE)
        if int(row["pk"]) > 0
    }
    if client_pk != {"usage_date": 1, "client_key": 2}:
        fail(f"client conflict key drift: {client_pk!r}")

    global_pk = {
        row["name"]: int(row["pk"])
        for row in table_info(db, GLOBAL_TABLE)
        if int(row["pk"]) > 0
    }
    if global_pk != {"usage_date": 1}:
        fail(f"global conflict key drift: {global_pk!r}")


def verify_worker_contract(worker: str, schema: str) -> None:
    required_worker_fragments = [
        "FROM ai_daily_global_usage",
        "INSERT INTO ai_daily_client_usage",
        "ON CONFLICT(usage_date, client_key)",
        "INSERT INTO ai_daily_global_usage",
        "ON CONFLICT(usage_date)",
        "UPDATE ai_daily_client_usage",
        "UPDATE ai_daily_global_usage",
    ]
    for fragment in required_worker_fragments:
        if fragment not in worker:
            fail(f"current Worker quota SQL contract drifted; missing: {fragment}")

    for table, columns in REQUIRED_COLUMNS.items():
        if table not in schema:
            fail(f"recovery schema no longer declares {table}")
        for column in columns:
            if column not in worker:
                fail(f"current Worker no longer exposes expected quota column token: {column}")


def reserve_client(
    db: sqlite3.Connection,
    date: str,
    client: str,
    kind: str,
    text_cap: int = 2,
    photo_cap: int = 1,
) -> bool:
    text_inc = 1 if kind == "text" else 0
    photo_inc = 1 if kind == "photo" else 0
    before = db.total_changes
    db.execute(
        CLIENT_RESERVE_SQL,
        (date, client, text_inc, photo_inc, text_cap, photo_cap),
    )
    return db.total_changes > before


def reserve_global(
    db: sqlite3.Connection,
    date: str,
    kind: str,
    text_cap: int = 3,
    photo_cap: int = 2,
) -> bool:
    text_inc = 1 if kind == "text" else 0
    photo_inc = 1 if kind == "photo" else 0
    before = db.total_changes
    db.execute(
        GLOBAL_RESERVE_SQL,
        (date, text_inc, photo_inc, text_cap, photo_cap),
    )
    return db.total_changes > before


def verify_quota_semantics(db: sqlite3.Connection) -> None:
    date = "2026-09-01"
    client = "0123456789abcdef0123456789abcdef"

    if not reserve_client(db, date, client, "text"):
        fail("first client text reservation did not write")
    if not reserve_client(db, date, client, "text"):
        fail("second client text reservation did not write")
    if reserve_client(db, date, client, "text"):
        fail("client text quota cap did not fail closed")

    row = db.execute(
        "SELECT text_count, photo_count FROM ai_daily_client_usage WHERE usage_date=? AND client_key=?",
        (date, client),
    ).fetchone()
    if tuple(row) != (2, 0):
        fail(f"unexpected client counters after text cap: {tuple(row)!r}")

    if not reserve_client(db, date, client, "photo"):
        fail("first client photo reservation did not write")
    if reserve_client(db, date, client, "photo"):
        fail("client photo quota cap did not fail closed")

    if not all(reserve_global(db, date, "text") for _ in range(3)):
        fail("global text reservations before cap should succeed")
    if reserve_global(db, date, "text"):
        fail("global text quota cap did not fail closed")
    if not all(reserve_global(db, date, "photo") for _ in range(2)):
        fail("global photo reservations before cap should succeed")
    if reserve_global(db, date, "photo"):
        fail("global photo quota cap did not fail closed")

    db.execute(
        """
        UPDATE ai_daily_client_usage
        SET text_count=MAX(text_count-?,0), photo_count=MAX(photo_count-?,0), updated_at=CURRENT_TIMESTAMP
        WHERE usage_date=? AND client_key=?
        """,
        (1, 0, date, client),
    )
    db.execute(
        """
        UPDATE ai_daily_global_usage
        SET text_count=MAX(text_count-?,0), photo_count=MAX(photo_count-?,0), updated_at=CURRENT_TIMESTAMP
        WHERE usage_date=?
        """,
        (1, 0, date),
    )

    client_row = db.execute(
        "SELECT text_count, photo_count FROM ai_daily_client_usage WHERE usage_date=? AND client_key=?",
        (date, client),
    ).fetchone()
    global_row = db.execute(
        "SELECT text_count, photo_count FROM ai_daily_global_usage WHERE usage_date=?",
        (date,),
    ).fetchone()
    if tuple(client_row) != (1, 1):
        fail(f"client refund semantics incorrect: {tuple(client_row)!r}")
    if tuple(global_row) != (2, 2):
        fail(f"global refund semantics incorrect: {tuple(global_row)!r}")

    # Refunds must never drive counters below zero.
    db.execute(
        "UPDATE ai_daily_client_usage SET text_count=MAX(text_count-99,0), photo_count=MAX(photo_count-99,0) WHERE usage_date=? AND client_key=?",
        (date, client),
    )
    row = db.execute(
        "SELECT text_count, photo_count FROM ai_daily_client_usage WHERE usage_date=? AND client_key=?",
        (date, client),
    ).fetchone()
    if tuple(row) != (0, 0):
        fail(f"counter floor-at-zero contract failed: {tuple(row)!r}")


def main() -> int:
    if not SCHEMA.is_file():
        fail(f"missing recovery schema: {SCHEMA.relative_to(ROOT)}")
    if not WORKER.is_file():
        fail(f"missing Worker source: {WORKER.relative_to(ROOT)}")

    schema = SCHEMA.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")

    # Strip line comments before looking for dangerous SQL so warning text in
    # comments cannot create false positives.
    executable_schema = "\n".join(
        line for line in schema.splitlines() if not line.lstrip().startswith("--")
    )
    match = DESTRUCTIVE_BOOTSTRAP.search(executable_schema)
    if match:
        fail(f"destructive statement not allowed in recovery bootstrap: {match.group(1).upper()}")

    verify_worker_contract(worker, schema)

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    try:
        db.executescript(schema)
        verify_schema_shape(db)
        verify_quota_semantics(db)
    except sqlite3.DatabaseError as exc:
        fail(f"SQLite contract error: {exc}")
    finally:
        db.close()

    print("D1 recovery tables: ai_daily_client_usage, ai_daily_global_usage")
    print("D1 recovery conflict keys: (usage_date, client_key), (usage_date)")
    print("CLOUDFLARE D1 RECOVERY SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
