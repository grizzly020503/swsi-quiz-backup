export type LegalWatchRecordLike = {
  found?: unknown;
  changed?: unknown;
};

export type LegalWatchRunHealth = {
  id: true;
  schema_version: 1;
  checked_at: string;
  baseline: boolean;
  watch_count: number;
  matched_count: number;
  missing_count: number;
  changed_count: number;
  lookup_error_count: number;
  sync_status: "syncing" | "complete" | "failed";
  source: "github_actions";
  updated_at: string;
};

function integer(value: unknown, label: string): number {
  const n = Number(value);
  if (!Number.isInteger(n) || n < 0) {
    throw new Error(`${label} must be a non-negative integer`);
  }
  return n;
}

export function normalizeCheckedAt(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error("checked_at is required");
  }
  const t = Date.parse(value);
  if (!Number.isFinite(t)) throw new Error("checked_at is invalid");
  return new Date(t).toISOString();
}

export function normalizeRunHealth(
  body: Record<string, unknown>,
  records: LegalWatchRecordLike[],
  syncStatus: LegalWatchRunHealth["sync_status"] = "syncing",
): LegalWatchRunHealth {
  const watchCount = integer(body.watch_count ?? records.length, "watch_count");
  const matchedCount = integer(body.matched_count, "matched_count");
  const missingCount = integer(body.missing_count, "missing_count");
  const changedCount = integer(body.changed_count, "changed_count");
  const lookupErrorCount = integer(body.lookup_error_count, "lookup_error_count");

  if (watchCount !== records.length) {
    throw new Error(`watch_count mismatch: ${watchCount} != ${records.length}`);
  }
  const actualMatched = records.filter((r) => r?.found === true).length;
  const actualMissing = records.length - actualMatched;
  const actualChanged = records.filter((r) => r?.found === true && r?.changed === true).length;
  if (matchedCount !== actualMatched) {
    throw new Error(`matched_count mismatch: ${matchedCount} != ${actualMatched}`);
  }
  if (missingCount !== actualMissing) {
    throw new Error(`missing_count mismatch: ${missingCount} != ${actualMissing}`);
  }
  if (changedCount !== actualChanged) {
    throw new Error(`changed_count mismatch: ${changedCount} != ${actualChanged}`);
  }
  if (lookupErrorCount > watchCount) {
    throw new Error("lookup_error_count exceeds watch_count");
  }

  return {
    id: true,
    schema_version: 1,
    checked_at: normalizeCheckedAt(body.checked_at),
    baseline: body.baseline === true,
    watch_count: watchCount,
    matched_count: matchedCount,
    missing_count: missingCount,
    changed_count: changedCount,
    lookup_error_count: lookupErrorCount,
    sync_status: syncStatus,
    source: "github_actions",
    updated_at: new Date().toISOString(),
  };
}

export function withSyncStatus(
  row: LegalWatchRunHealth,
  syncStatus: LegalWatchRunHealth["sync_status"],
): LegalWatchRunHealth {
  return { ...row, sync_status: syncStatus, updated_at: new Date().toISOString() };
}
