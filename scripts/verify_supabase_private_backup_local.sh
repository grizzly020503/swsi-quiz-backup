#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 64
}

if [[ -n "${CI:-}" || "${GITHUB_ACTIONS:-}" == "true" ]]; then
  fail "this private-data backup verifier refuses to decrypt backups in CI"
fi

[[ $# -eq 1 ]] || fail "usage: bash scripts/verify_supabase_private_backup_local.sh /path/to/swsi-supabase-private-....tar.age"

bundle="$1"
[[ -f "$bundle" && -s "$bundle" ]] || fail "encrypted bundle not found: $bundle"

for cmd in age python3 tar; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required command not found: $cmd"
done

checksum="$bundle.sha256"
if [[ -f "$checksum" ]]; then
  python3 - "$bundle" "$checksum" <<'PY'
import hashlib
import pathlib
import sys

bundle = pathlib.Path(sys.argv[1])
checksum_file = pathlib.Path(sys.argv[2])
expected = checksum_file.read_text(encoding="utf-8").strip().split()[0]
actual = hashlib.sha256(bundle.read_bytes()).hexdigest()
if expected != actual:
    raise SystemExit(f"checksum mismatch: expected={expected} actual={actual}")
print(f"ENCRYPTED BUNDLE SHA256 OK {actual}")
PY
else
  printf 'WARNING: checksum sidecar not found; continuing with authenticated age decryption only\n' >&2
fi

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/swsi-backup-verify.XXXXXX")"
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT HUP INT TERM

age -d "$bundle" | tar -xf - -C "$work_dir"

for required in roles.sql schema.sql data.sql source-counts.json metadata.json; do
  [[ -s "$work_dir/$required" ]] || fail "decrypted component is missing or empty: $required"
done

python3 - "$work_dir" <<'PY'
import hashlib
import json
import pathlib
import sys

work = pathlib.Path(sys.argv[1])
metadata = json.loads((work / "metadata.json").read_text(encoding="utf-8"))
counts = json.loads((work / "source-counts.json").read_text(encoding="utf-8"))

if metadata.get("format") != "swsi-supabase-private-backup-v1":
    raise SystemExit("unexpected backup format")
if metadata.get("ci_allowed") is not False:
    raise SystemExit("backup metadata does not preserve local-only policy")
if metadata.get("restore_validation_required") is not True:
    raise SystemExit("backup metadata does not require isolated restore validation")

for name in ("roles.sql", "schema.sql", "data.sql", "source-counts.json"):
    raw = (work / name).read_bytes()
    recorded = metadata["files"][name]
    if len(raw) != int(recorded["bytes"]):
        raise SystemExit(f"{name}: byte-length mismatch")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != recorded["sha256"]:
        raise SystemExit(f"{name}: SHA-256 mismatch")

visible_counts = {
    key: counts.get(key)
    for key in (
        "captured_at_utc",
        "auth_users",
        "feedback_reports",
        "usage_daily_rows",
        "ai_telemetry_client_daily_rows",
        "ai_telemetry_5m_rows",
        "storage_buckets",
        "storage_objects",
    )
}
print("PRIVATE BACKUP BUNDLE STRUCTURE OK")
print("source_git_commit=" + str(metadata.get("source_git_commit")))
print("source_count_baseline=" + json.dumps(visible_counts, ensure_ascii=False, sort_keys=True))
print("NOTE: bundle integrity is not the same as restore proof; perform the isolated restore drill in the runbook.")
PY
