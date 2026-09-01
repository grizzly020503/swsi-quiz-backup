-- SWSI Cloudflare D1 quota recovery bootstrap
--
-- IMPORTANT:
-- - This is a recovery-compatible schema derived from the CURRENT Worker SQL
--   contract. It is NOT asserted to be a byte-for-byte snapshot of the existing
--   production D1 schema, because the original production DDL was not committed.
-- - Do not apply this file blindly to the existing production database.
-- - Intended use: bootstrap a NEW/EMPTY recovery database after separately
--   verifying the current Worker contract and, when possible, comparing against
--   the live production schema.
-- - No migration/deploy workflow applies this file automatically.

CREATE TABLE IF NOT EXISTS ai_daily_client_usage (
  usage_date TEXT NOT NULL,
  client_key TEXT NOT NULL,
  text_count INTEGER NOT NULL DEFAULT 0 CHECK (text_count >= 0),
  photo_count INTEGER NOT NULL DEFAULT 0 CHECK (photo_count >= 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (usage_date, client_key)
);

CREATE TABLE IF NOT EXISTS ai_daily_global_usage (
  usage_date TEXT NOT NULL PRIMARY KEY,
  text_count INTEGER NOT NULL DEFAULT 0 CHECK (text_count >= 0),
  photo_count INTEGER NOT NULL DEFAULT 0 CHECK (photo_count >= 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
