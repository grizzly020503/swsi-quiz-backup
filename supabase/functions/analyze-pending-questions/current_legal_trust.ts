export type LegalWatchRunHealthRow = {
  schema_version?: unknown;
  checked_at?: unknown;
  baseline?: unknown;
  lookup_error_count?: unknown;
  sync_status?: unknown;
  source?: unknown;
};

export type LegalReferenceRegistryRow = {
  canonical_name?: unknown;
  watch_status?: unknown;
  last_checked_at?: unknown;
};

export type CurrentLegalTrustDecision = {
  trusted: boolean;
  reason: string;
  checked_at: string | null;
  historical_version_proof: false;
};

export const DEFAULT_CURRENT_LEGAL_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
const MAX_FUTURE_SKEW_MS = 10 * 60 * 1000;

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim();
}

function nonNegativeInteger(value: unknown): number | null {
  const n = Number(value);
  return Number.isInteger(n) && n >= 0 ? n : null;
}

function parseTime(value: unknown): number | null {
  const raw = text(value);
  if (!raw) return null;
  const t = Date.parse(raw);
  return Number.isFinite(t) ? t : null;
}

function reject(reason: string, checkedAt: string | null = null): CurrentLegalTrustDecision {
  return { trusted: false, reason, checked_at: checkedAt, historical_version_proof: false };
}

export function evaluateCurrentLegalTrust(
  canonicalNames: string[],
  run: LegalWatchRunHealthRow | null | undefined,
  registryRows: LegalReferenceRegistryRow[],
  options: { nowMs?: number; maxAgeMs?: number } = {},
): CurrentLegalTrustDecision {
  const names = [...new Set(canonicalNames.map((x) => text(x)).filter(Boolean))];
  if (!names.length) return reject("no_canonical_law");
  if (!run) return reject("run_health_missing");

  if (Number(run.schema_version) !== 1) return reject("run_schema_untrusted");
  if (text(run.source) !== "github_actions") return reject("run_source_untrusted");
  if (text(run.sync_status) !== "complete") return reject("run_not_complete");
  if (run.baseline === true) return reject("run_is_baseline");

  const lookupErrors = nonNegativeInteger(run.lookup_error_count);
  if (lookupErrors === null) return reject("run_lookup_error_invalid");
  if (lookupErrors !== 0) return reject("run_lookup_error_present");

  const checkedMs = parseTime(run.checked_at);
  if (checkedMs === null) return reject("run_checked_at_invalid");
  const checkedAt = new Date(checkedMs).toISOString();
  const nowMs = options.nowMs ?? Date.now();
  const maxAgeMs = options.maxAgeMs ?? DEFAULT_CURRENT_LEGAL_MAX_AGE_MS;
  if (!Number.isFinite(nowMs) || !Number.isFinite(maxAgeMs) || maxAgeMs <= 0) {
    return reject("trust_clock_invalid", checkedAt);
  }
  if (checkedMs > nowMs + MAX_FUTURE_SKEW_MS) return reject("run_checked_at_future", checkedAt);
  if (nowMs - checkedMs > maxAgeMs) return reject("run_stale", checkedAt);

  const byName = new Map<string, LegalReferenceRegistryRow>();
  for (const row of registryRows) {
    const name = text(row?.canonical_name);
    if (name && !byName.has(name)) byName.set(name, row);
  }

  for (const name of names) {
    const row = byName.get(name);
    if (!row) return reject("law_registry_missing", checkedAt);
    if (text(row.watch_status) !== "unchanged") return reject("law_not_unchanged", checkedAt);
    const rowCheckedMs = parseTime(row.last_checked_at);
    if (rowCheckedMs === null) return reject("law_checked_at_invalid", checkedAt);
    if (rowCheckedMs !== checkedMs) return reject("law_batch_mismatch", checkedAt);
  }

  return {
    trusted: true,
    reason: "trusted_current_intake",
    checked_at: checkedAt,
    historical_version_proof: false,
  };
}
