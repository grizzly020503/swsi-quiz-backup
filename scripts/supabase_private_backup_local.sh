#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 64
}

if [[ -n "${CI:-}" || "${GITHUB_ACTIONS:-}" == "true" ]]; then
  fail "this private-data backup helper refuses to run in CI; run it only on a maintainer-controlled local machine"
fi

: "${SWSI_SUPABASE_DB_URL:?Set SWSI_SUPABASE_DB_URL to the Supabase session-pooler or direct database connection string.}"
: "${SWSI_BACKUP_AGE_RECIPIENT:?Set SWSI_BACKUP_AGE_RECIPIENT to an age public recipient (age1...).}"

for cmd in supabase psql age python3 tar git; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required command not found: $cmd"
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$repo_root" ]] || fail "run this script from inside the SWSI Git repository"

backup_dir="${SWSI_BACKUP_DIR:-$HOME/swsi-private-backups}"

if ! python3 - "$repo_root" "$backup_dir" <<'PY'
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
  fail "SWSI_BACKUP_DIR must be outside the Git worktree"
fi

mkdir -p "$backup_dir"
chmod 700 "$backup_dir" 2>/dev/null || true

tmp_root="${TMPDIR:-/tmp}"
work_dir="$(mktemp -d "$tmp_root/swsi-supabase-backup.XXXXXX")"
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT HUP INT TERM

created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
source_commit="$(git rev-parse HEAD)"
short_commit="$(git rev-parse --short=12 HEAD)"

printf '[backup] capturing count-only source baseline\n'
psql -X -qAt --set=ON_ERROR_STOP=1 --dbname="$SWSI_SUPABASE_DB_URL" > "$work_dir/source-counts.json" <<'SQL'
select json_build_object(
  'captured_at_utc', to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
  'auth_users', (select count(*) from auth.users),
  'feedback_reports', (select count(*) from public.swsi_feedback_reports),
  'usage_daily_rows', (select count(*) from public.swsi_usage_daily),
  'ai_telemetry_client_daily_rows', (select count(*) from public.swsi_ai_telemetry_client_daily),
  'ai_telemetry_5m_rows', (select count(*) from public.swsi_ai_telemetry_5m),
  'storage_buckets', (select count(*) from storage.buckets),
  'storage_objects', (select count(*) from storage.objects)
);
SQL

python3 -m json.tool "$work_dir/source-counts.json" >/dev/null

printf '[backup] dumping roles\n'
supabase db dump --db-url "$SWSI_SUPABASE_DB_URL" -f "$work_dir/roles.sql" --role-only

printf '[backup] dumping schema\n'
supabase db dump --db-url "$SWSI_SUPABASE_DB_URL" -f "$work_dir/schema.sql"

printf '[backup] dumping data\n'
supabase db dump   --db-url "$SWSI_SUPABASE_DB_URL"   -f "$work_dir/data.sql"   --use-copy   --data-only   -x "storage.buckets_vectors"   -x "storage.vector_indexes"

for required in roles.sql schema.sql data.sql source-counts.json; do
  [[ -s "$work_dir/$required" ]] || fail "backup component is missing or empty: $required"
done

export SWSI_BACKUP_CREATED_AT="$created_at"
export SWSI_BACKUP_SOURCE_COMMIT="$source_commit"
export SWSI_BACKUP_REPO_ROOT="$repo_root"
python3 - "$work_dir" <<'PY'
import hashlib
import json
import os
import pathlib
import subprocess
import sys

work = pathlib.Path(sys.argv[1])
files = {}
for name in ("roles.sql", "schema.sql", "data.sql", "source-counts.json"):
    raw = (work / name).read_bytes()
    files[name] = {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

def version(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip().splitlines()[0]
    except Exception as exc:
        return f"unavailable: {type(exc).__name__}"

metadata = {
    "format": "swsi-supabase-private-backup-v1",
    "created_at_utc": os.environ["SWSI_BACKUP_CREATED_AT"],
    "source_git_commit": os.environ["SWSI_BACKUP_SOURCE_COMMIT"],
    "plaintext_location": "temporary local directory only; removed after encryption",
    "ci_allowed": False,
    "restore_validation_required": True,
    "auth_coverage_note": (
        "Do not assume auth.users coverage from dump creation alone. "
        "An isolated restore must compare target counts with source-counts.json."
    ),
    "storage_note": (
        "Database dumps do not restore Storage object bytes. "
        "If source-counts.json reports storage_objects > 0, back up objects separately."
    ),
    "tools": {
        "supabase": version(["supabase", "--version"]),
        "psql": version(["psql", "--version"]),
        "age": version(["age", "--version"]),
    },
    "files": files,
}
(work / "metadata.json").write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

bundle_name="swsi-supabase-private-${stamp}-${short_commit}.tar.age"
partial="$backup_dir/.${bundle_name}.partial"
bundle="$backup_dir/$bundle_name"
checksum="$bundle.sha256"

rm -f "$partial"

printf '[backup] encrypting bundle before it leaves the temporary directory\n'
tar -C "$work_dir" -cf -   roles.sql schema.sql data.sql source-counts.json metadata.json   | age -r "$SWSI_BACKUP_AGE_RECIPIENT" -o "$partial"

[[ -s "$partial" ]] || fail "encrypted bundle was not created"
mv "$partial" "$bundle"
chmod 600 "$bundle"

python3 - "$bundle" "$checksum" <<'PY'
import hashlib
import pathlib
import sys

bundle = pathlib.Path(sys.argv[1])
checksum = pathlib.Path(sys.argv[2])
digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
checksum.write_text(f"{digest}  {bundle.name}\n", encoding="utf-8")
PY
chmod 600 "$checksum"

printf '\nBACKUP CREATED\n'
printf 'Encrypted bundle: %s\n' "$bundle"
printf 'Checksum:        %s\n' "$checksum"
printf 'Source commit:   %s\n' "$source_commit"
printf 'Created UTC:     %s\n' "$created_at"
printf '\nNext: copy BOTH encrypted files to at least one additional off-site location, then run the local verifier.\n'
printf 'Do not upload the plaintext SQL files, database URL, age private identity, or decrypted contents to GitHub.\n'
