export const HISTORICAL_MACHINE_LEVEL = "machine_verified_historical_v1";
export const HISTORICAL_ADJUDICATED_LEVEL = "evidence_adjudicated_historical_v1";
const ALLOWED_LEVELS = new Set([HISTORICAL_MACHINE_LEVEL, HISTORICAL_ADJUDICATED_LEVEL]);

export type HistoricalLawTrustDecision = {
  trusted: boolean;
  reason: string;
  registry_sha256: string | null;
  historical_version_proof: boolean;
};

export type HistoricalEvidenceSnapshotLike = {
  schema_version?: unknown;
  registry_sha256?: unknown;
  record_count?: unknown;
  historical_version_checked_count?: unknown;
  sync_status?: unknown;
  source?: unknown;
};

export type HistoricalEvidenceRowLike = {
  question_id?: unknown;
  law_name?: unknown;
  exam_code?: unknown;
  historical_version_checked?: unknown;
  verification_level?: unknown;
  evidence_sha256?: unknown;
  source_registry_sha256?: unknown;
};

function clean(value: unknown): string {
  return String(value ?? "").trim();
}

function fail(reason: string, registrySha: string | null = null): HistoricalLawTrustDecision {
  return { trusted: false, reason, registry_sha256: registrySha, historical_version_proof: false };
}

function validSha(value: unknown): string | null {
  const raw = clean(value).toLowerCase();
  return /^[0-9a-f]{64}$/.test(raw) ? raw : null;
}

export function canonicalExamCode(q: { year?: unknown; round?: unknown; id?: unknown }): string | null {
  const year = clean(q.year);
  const round = clean(q.round);
  const aliases: Record<string, string> = {
    "1": "1",
    "第1次": "1",
    "第一次": "1",
    "第一試": "1",
    "2": "2",
    "第2次": "2",
    "第二次": "2",
    "第二試": "2",
  };
  if (/^\d{3}$/.test(year) && aliases[round]) return `${year}-${aliases[round]}`;
  // Real SWSI ids are shaped like SP115-1-40 / SW113-2-08, without a
  // separator between the subject prefix and ROC year.
  const match = clean(q.id).match(/(\d{3})-([12])-/);
  return match ? `${match[1]}-${match[2]}` : null;
}

export function evaluateHistoricalLawTrust(
  questionId: string,
  examCode: string | null,
  lawNames: string[],
  snapshot: HistoricalEvidenceSnapshotLike | null | undefined,
  rows: HistoricalEvidenceRowLike[] | null | undefined,
): HistoricalLawTrustDecision {
  const qid = clean(questionId);
  const names = [...new Set(lawNames.map(clean).filter(Boolean))].sort();
  if (!qid) return fail("question_id_missing");
  if (!examCode || !/^\d{3}-[12]$/.test(examCode)) return fail("exam_code_unresolved");
  if (!names.length) return fail("law_names_missing");
  if (!snapshot) return fail("historical_snapshot_missing");
  if (Number(snapshot.schema_version) !== 1) return fail("historical_snapshot_schema_untrusted");
  if (clean(snapshot.source) !== "github_actions") return fail("historical_snapshot_source_untrusted");
  if (clean(snapshot.sync_status) !== "complete") return fail("historical_snapshot_not_complete");
  const registrySha = validSha(snapshot.registry_sha256);
  if (!registrySha) return fail("historical_snapshot_hash_invalid");
  const count = Number(snapshot.record_count);
  const checkedCount = Number(snapshot.historical_version_checked_count);
  if (!Number.isInteger(count) || count <= 0 || checkedCount !== count) {
    return fail("historical_snapshot_counts_invalid", registrySha);
  }

  const list = Array.isArray(rows) ? rows : [];
  const byLaw = new Map<string, HistoricalEvidenceRowLike>();
  for (const row of list) {
    if (clean(row.question_id) !== qid) return fail("historical_question_mismatch", registrySha);
    const name = clean(row.law_name);
    if (!name || byLaw.has(name)) return fail("historical_evidence_duplicate", registrySha);
    byLaw.set(name, row);
  }

  for (const name of names) {
    const row = byLaw.get(name);
    if (!row) return fail("historical_evidence_missing", registrySha);
    if (clean(row.exam_code) !== examCode) return fail("historical_exam_code_mismatch", registrySha);
    if (row.historical_version_checked !== true) return fail("historical_checked_flag_missing", registrySha);
    if (!ALLOWED_LEVELS.has(clean(row.verification_level))) {
      return fail("historical_verification_level_untrusted", registrySha);
    }
    if (!validSha(row.evidence_sha256)) return fail("historical_evidence_hash_invalid", registrySha);
    if (validSha(row.source_registry_sha256) !== registrySha) {
      return fail("historical_registry_batch_mismatch", registrySha);
    }
  }

  return {
    trusted: true,
    reason: "verified_exam_time_historical_law",
    registry_sha256: registrySha,
    historical_version_proof: true,
  };
}

export function historicalReasonIsOperationalRetry(reason: string): boolean {
  return new Set([
    "historical_snapshot_missing",
    "historical_snapshot_not_complete",
  ]).has(reason);
}
