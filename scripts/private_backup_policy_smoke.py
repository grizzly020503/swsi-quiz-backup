#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
backup = (ROOT / "scripts/supabase_private_backup_local.sh").read_text(encoding="utf-8")
verify = (ROOT / "scripts/verify_supabase_private_backup_local.sh").read_text(encoding="utf-8")
restore = (ROOT / "scripts/restore_supabase_private_backup_isolated.sh").read_text(encoding="utf-8")
gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/private-backup-policy-qa.yml").read_text(encoding="utf-8")

required_backup_markers = [
    'refuses to run in CI',
    'SWSI_SUPABASE_DB_URL',
    'SWSI_BACKUP_AGE_RECIPIENT',
    'SWSI_BACKUP_DIR must be outside the Git worktree',
    'supabase db dump',
    '--role-only',
    '--data-only',
    '--use-copy',
    'age -r "$SWSI_BACKUP_AGE_RECIPIENT"',
    'source-counts.json',
    'restore_validation_required',
]
for marker in required_backup_markers:
    if marker not in backup:
        raise SystemExit(f"backup policy marker missing: {marker}")

required_verify_markers = [
    'refuses to decrypt backups in CI',
    'age -d "$bundle"',
    'PRIVATE BACKUP BUNDLE STRUCTURE OK',
    'restore proof',
]
for marker in required_verify_markers:
    if marker not in verify:
        raise SystemExit(f"verifier policy marker missing: {marker}")


required_restore_markers = [
    'refuses to run in CI',
    'I_UNDERSTAND_THIS_WRITES_THE_ISOLATED_TARGET',
    'SWSI_RESTORE_TARGET_KIND',
    'target project ref equals production project ref',
    'target database URL appears to reference production',
    'auth_users=0 storage_objects=0',
    'source backup reports Storage objects > 0',
    'restore count mismatch',
    'ISOLATED PRIVATE-DATA RESTORE PROOF OK',
]
for marker in required_restore_markers:
    if marker not in restore:
        raise SystemExit(f"restore policy marker missing: {marker}")

for forbidden in (
    "yumjtrdctaxyczpspuyo",
    "postgresql://postgres.",
    "service_role=",
    "sb_secret_",
):
    if forbidden in backup or forbidden in verify or forbidden in restore:
        raise SystemExit(f"private backup scripts contain forbidden concrete secret/project material: {forbidden}")

for ignore_marker in (
    "/private-backups/",
    "swsi-supabase-private-*.tar.age",
    "swsi-supabase-private-*.tar.age.sha256",
    "*.agekey",
    "/restore-reports/",
    "swsi-private-restore-*.json",
):
    if ignore_marker not in gitignore:
        raise SystemExit(f".gitignore backup guard missing: {ignore_marker}")

if "upload-artifact" in workflow:
    raise SystemExit("private-backup policy workflow must never upload backup artifacts")
if "secrets." in workflow:
    raise SystemExit("private-backup policy workflow must not read repository secrets")
if "bash scripts/supabase_private_backup_local.sh" not in workflow:
    raise SystemExit("workflow does not prove that the backup helper refuses CI execution")
if "bash scripts/restore_supabase_private_backup_isolated.sh" not in workflow:
    raise SystemExit("workflow does not prove that the restore helper refuses CI execution")

print("SWSI PRIVATE BACKUP POLICY SMOKE OK")
