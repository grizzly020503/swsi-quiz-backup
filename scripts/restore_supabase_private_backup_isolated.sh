#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 64
}

if [[ -n "${CI:-}" || "${GITHUB_ACTIONS:-}" == "true" ]]; then
  fail "this isolated private-data restore helper refuses to run in CI"
fi

[[ $# -eq 1 ]] || fail "usage: bash scripts/restore_supabase_private_backup_isolated.sh /path/to/swsi-supabase-private-....tar.age"
bundle="$1"
[[ -f "$bundle" && -s "$bundle" ]] || fail "encrypted bundle not found: $bundle"

: "${SWSI_RESTORE_TARGET_DB_URL:?Set SWSI_RESTORE_TARGET_DB_URL to the isolated target database connection string.}"
: "${SWSI_RESTORE_TARGET_KIND:?Set SWSI_RESTORE_TARGET_KIND to local or hosted-isolated.}"
: "${SWSI_RESTORE_ACK:?Set SWSI_RESTORE_ACK=I_UNDERSTAND_THIS_WRITES_THE_ISOLATED_TARGET.}"

[[ "$SWSI_RESTORE_ACK" == "I_UNDERSTAND_THIS_WRITES_THE_ISOLATED_TARGET" ]] ||   fail "restore acknowledgement mismatch"

for cmd in age psql python3 tar git; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required command not found: $cmd"
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$repo_root" ]] || fail "run this script from inside the SWSI Git repository"

# Restrict to a disposable local PostgreSQL instance and prove actual server identity.
python3 "$repo_root/scripts/restore_destination_guard.py" || fail "restore routing preflight failed"
target_identity="$(psql -X -qAt --set=ON_ERROR_STOP=1 --dbname="$SWSI_RESTORE_TARGET_DB_URL" <<'SQL'
SELECT json_build_object(
  'database', current_database(),
  'target_id', current_setting('swsi.disposable_target_id', true),
  'server_addr', inet_server_addr()::text
);
SQL
)"
printf '%s\n' "$target_identity" | python3 "$repo_root/scripts/restore_destination_guard.py" --identity-stdin || fail "isolated target identity could not be established"

report_dir="${SWSI_RESTORE_REPORT_DIR:-$HOME/swsi-private-backups/restore-reports}"
if ! python3 - "$repo_root" "$report_dir" <<'PY'
import os
import sys
repo = os.path.realpath(sys.argv[1])
dest = os.path.realpath(os.path.expanduser(sys.argv[2]))
try:
    inside = os.path.commonpath([repo, dest]) == repo
except ValueError:
    inside = False
raise SystemExit(1 if inside else 0)
PY
then
  fail "SWSI_RESTORE_REPORT_DIR must be outside the Git worktree"
fi
mkdir -p "$report_dir"
chmod 700 "$report_dir" 2>/dev/null || true

printf '[restore] verifying encrypted bundle integrity locally\n'
bash "$repo_root/scripts/verify_supabase_private_backup_local.sh" "$bundle"

printf '[restore] verifying all isolated-target private table counts\n'
preflight="$(python3 "$repo_root/scripts/private_backup_count_query.py" --connection-env SWSI_RESTORE_TARGET_DB_URL)" || fail "target count capture failed"
export SWSI_RESTORE_PREFLIGHT="$preflight"
python3 "$repo_root/scripts/private_restore_target_preflight.py" || fail "isolated target is not empty or schema count is ambiguous"
unset SWSI_RESTORE_PREFLIGHT preflight target_identity

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/swsi-private-restore.XXXXXX")"
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT HUP INT TERM

age -d "$bundle" | tar -xf - -C "$work_dir"
for required in roles.sql schema.sql data.sql source-counts.json metadata.json; do
  [[ -s "$work_dir/$required" ]] || fail "decrypted component is missing or empty: $required"
done

python3 "$repo_root/scripts/private_backup_counts_guard.py" "$work_dir/source-counts.json" || fail "source count baseline invalid"

source_storage_objects="$(python3 - "$work_dir/source-counts.json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
print(int(d.get("storage_objects", 0)))
PY
)"
if [[ "$source_storage_objects" -gt 0 ]]; then
  fail "source backup reports Storage objects > 0; restore object bytes separately before this drill can be accepted"
fi

restore_start_epoch="$(date +%s)"
restore_started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf '[restore] applying roles -> schema -> data to isolated target\n'
psql -X   --single-transaction   --variable ON_ERROR_STOP=1   --file "$work_dir/roles.sql"   --file "$work_dir/schema.sql"   --command 'SET session_replication_role = replica'   --file "$work_dir/data.sql"   --dbname "$SWSI_RESTORE_TARGET_DB_URL"

printf '[restore] capturing schema-aware restored target count-only baseline\n'
python3 "$repo_root/scripts/private_backup_count_query.py" --connection-env SWSI_RESTORE_TARGET_DB_URL > "$work_dir/target-counts.json"
python3 "$repo_root/scripts/private_backup_counts_guard.py" "$work_dir/source-counts.json" --target "$work_dir/target-counts.json" || fail "restored schema/count mismatch"

restore_end_epoch="$(date +%s)"
restore_finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
elapsed="$((restore_end_epoch - restore_start_epoch))"

export SWSI_RESTORE_STARTED_AT="$restore_started_at"
export SWSI_RESTORE_FINISHED_AT="$restore_finished_at"
export SWSI_RESTORE_ELAPSED_SECONDS="$elapsed"
export SWSI_RESTORE_TARGET_KIND_VALUE="$SWSI_RESTORE_TARGET_KIND"
export SWSI_RESTORE_REPORT_DIR_VALUE="$report_dir"
export SWSI_RESTORE_BUNDLE_NAME="$(basename "$bundle")"

report_path="$(python3 - "$work_dir" <<'PY'
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

work = pathlib.Path(sys.argv[1])
source = json.loads((work / "source-counts.json").read_text(encoding="utf-8"))
target = json.loads((work / "target-counts.json").read_text(encoding="utf-8"))
meta = json.loads((work / "metadata.json").read_text(encoding="utf-8"))

keys = (
    "auth_users",
    "feedback_reports",
    "usage_daily_rows",
    "ai_telemetry_client_daily_rows",
    "ai_telemetry_5m_rows",
    "storage_buckets",
    "storage_objects",
    "admin_allowlist_rows",
    "ops_task_runs", "ops_review_items",
    "ops_task_runs_present", "ops_review_items_present",
)
mismatches = {
    key: {"source": source.get(key), "target": target.get(key)}
    for key in keys
    if source.get(key) != target.get(key)
}
if mismatches:
    raise SystemExit("restore count mismatch: " + json.dumps(mismatches, ensure_ascii=False, sort_keys=True))

report = {
    "format": "swsi-private-restore-proof-v1",
    "result": "pass",
    "source_git_commit": meta.get("source_git_commit"),
    "source_backup_created_at_utc": meta.get("created_at_utc"),
    "source_count_captured_at_utc": source.get("captured_at_utc"),
    "restore_started_at_utc": os.environ["SWSI_RESTORE_STARTED_AT"],
    "restore_finished_at_utc": os.environ["SWSI_RESTORE_FINISHED_AT"],
    "measured_restore_rto_seconds": int(os.environ["SWSI_RESTORE_ELAPSED_SECONDS"]),
    "target_kind": os.environ["SWSI_RESTORE_TARGET_KIND_VALUE"],
    "bundle_name": os.environ["SWSI_RESTORE_BUNDLE_NAME"],
    "counts": {key: source.get(key) for key in keys},
    "storage_object_bytes_proven": source.get("storage_objects", 0) == 0,
    "notes": [
        "Count-only proof; no personal row contents are written to the report.",
        "Secret values, Auth provider settings, SMTP/DNS, Edge Function deployment state are outside this database restore proof."
    ],
}
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
dest = pathlib.Path(os.path.expanduser(os.environ["SWSI_RESTORE_REPORT_DIR_VALUE"]))
path = dest / f"swsi-private-restore-{stamp}.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(path)
PY
)"

chmod 600 "$report_path"
printf '\nISOLATED PRIVATE-DATA RESTORE PROOF OK\n'
printf 'Measured database restore RTO: %s seconds\n' "$elapsed"
printf 'Count-only report: %s\n' "$report_path"
printf 'Production was not selected by this helper. Keep the report private unless only non-sensitive count/timing fields are shared.\n'
