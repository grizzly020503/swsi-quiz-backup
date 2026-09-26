#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=postgres}"

psql_cmd=(psql -X -v ON_ERROR_STOP=1)

echo "[dr] installing isolated Supabase-owned role/auth/cron stubs"
"${psql_cmd[@]}" -f supabase/recovery/ci_supabase_stubs.sql

echo "[dr] creating recovery-only questions base"
"${psql_cmd[@]}" -f supabase/recovery/000_questions_base.sql

echo "[dr] replaying recovered initial MOEX schema"
"${psql_cmd[@]}" -f supabase/recovery/20260824154417_add_moex_auto_sync_tables.sql

echo "[dr] preparing AI automation migration with network schedulers disabled"
python3 - <<'PY'
from pathlib import Path

src = Path("supabase/migrations/20260825_ai_analysis_automation.sql").read_text(encoding="utf-8")
for exact in (
    "create extension if not exists pg_cron;\n",
    "create extension if not exists pg_net;\n",
):
    if exact not in src:
        raise SystemExit(f"expected isolated-removal marker missing: {exact.strip()}")
    src = src.replace(exact, "")
Path("/tmp/swsi-ai-analysis-isolated.sql").write_text(src, encoding="utf-8")
PY
"${psql_cmd[@]}" -f /tmp/swsi-ai-analysis-isolated.sql

migrations=(
  supabase/migrations/20260825_add_legal_quality_status.sql
  supabase/migrations/20260825_add_canonical_legal_names.sql
  supabase/migrations/20260825_add_official_legal_watch_registry.sql
  supabase/migrations/20260825_add_current_affairs_radar.sql
  supabase/migrations/20260825042630_harden_public_readonly_access.sql
  supabase/migrations/20260825044722_correct_social_worker_continuing_education_law_name.sql
  supabase/migrations/20260825094110_production_qa_consolidation.sql
  supabase/migrations/20260825110853_preserve_official_grading_mode.sql
  supabase/migrations/20260826062000_create_swsi_feedback_reports.sql
  supabase/migrations/20260826062500_explicitly_deny_public_feedback_table.sql
  supabase/migrations/20260826084600_atomic_swsi_feedback_submit.sql
  supabase/migrations/20260827031000_align_recovery_reset_with_grading_mode.sql
  supabase/migrations/20260828011500_create_swsi_admin_users.sql
  supabase/migrations/20260902143000_add_anonymous_usage_analytics.sql
  supabase/migrations/20260915151500_add_ai_telemetry.sql
)

for migration in "${migrations[@]}"; do
  echo "[dr] applying ${migration}"
  "${psql_cmd[@]}" -f "${migration}"
done

echo "[dr] verifying restored Postgres contracts with synthetic-only fixtures"
"${psql_cmd[@]}" -f supabase/recovery/postgres_contract_smoke.sql

echo "[dr] verifying repo-owned recovery inventory"
python3 scripts/disaster_recovery_repo_inventory.py

echo "[dr] verifying D1 recovery contract in isolated SQLite"
python3 scripts/cloudflare_d1_recovery_smoke.py

echo "SWSI ISOLATED RESTORE DRILL CORE OK"
