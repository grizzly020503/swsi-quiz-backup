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


-- Privacy-minimized AI operational telemetry.
-- Stores only aggregate hourly counters/latency; never prompts, answers, images,
-- raw IP, User-Agent, names, email addresses, or client identifiers.
CREATE TABLE IF NOT EXISTS ai_telemetry_hourly (
  bucket_hour TEXT NOT NULL PRIMARY KEY,
  requests INTEGER NOT NULL DEFAULT 0 CHECK (requests >= 0),
  successes INTEGER NOT NULL DEFAULT 0 CHECK (successes >= 0),
  rate_limited INTEGER NOT NULL DEFAULT 0 CHECK (rate_limited >= 0),
  service_errors INTEGER NOT NULL DEFAULT 0 CHECK (service_errors >= 0),
  client_rejected INTEGER NOT NULL DEFAULT 0 CHECK (client_rejected >= 0),
  total_latency_ms INTEGER NOT NULL DEFAULT 0 CHECK (total_latency_ms >= 0),
  max_latency_ms INTEGER NOT NULL DEFAULT 0 CHECK (max_latency_ms >= 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
