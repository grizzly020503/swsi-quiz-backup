export const MACHINE_LEVEL = "machine_verified_historical_v1";
export const ADJUDICATED_LEVEL = "evidence_adjudicated_historical_v1";
export const ALLOWED_LEVELS = new Set([MACHINE_LEVEL, ADJUDICATED_LEVEL]);

const PROTECTED_CORE_FIELDS = new Set([
  "stem",
  "question",
  "options",
  "official_answer",
  "answer",
  "accepted_answers",
  "grading_mode",
]);

export type RuntimeEvidenceRecord = {
  question_id: string;
  law_name: string;
  exam_code: string;
  article: string;
  historical_version_checked: true;
  verification_level: string;
  verification_basis: string;
  selected_version_kind: "current" | "oldver";
  selected_version_date: string;
  selected_effective_date: string | null;
  selected_effective_date_scope: string | null;
  selected_version_url: string;
  historical_article_sha256: string;
  official_history_url: string;
  exam_date_source_url: string;
};

export type NormalizedRegistry = {
  schema_version: 1;
  record_count: number;
  historical_version_checked_count: number;
  machine_verified_count: number;
  evidence_adjudicated_count: number;
  records: RuntimeEvidenceRecord[];
};

function clean(value: unknown): string {
  return String(value ?? "").trim();
}

function requireHttpsHost(value: unknown, host: string, label: string): string {
  const raw = clean(value);
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error(`${label} invalid URL`);
  }
  if (url.protocol !== "https:" || url.hostname !== host) {
    throw new Error(`${label} must use https://${host}`);
  }
  return url.toString();
}

function dateOrNull(value: unknown, label: string, required = false): string | null {
  const raw = clean(value);
  if (!raw && !required) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw) || Number.isNaN(Date.parse(`${raw}T00:00:00Z`))) {
    throw new Error(`${label} must be YYYY-MM-DD`);
  }
  return raw;
}

function sha256(value: unknown, label: string): string {
  const raw = clean(value).toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(raw)) throw new Error(`${label} must be sha256 hex`);
  return raw;
}

export function evidenceKey(row: { question_id?: unknown; law_name?: unknown }): string {
  return `${clean(row.question_id)}\u0000${clean(row.law_name)}`;
}

export function normalizeRecord(raw: unknown): RuntimeEvidenceRecord {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("historical-law evidence record must be an object");
  }
  const row = raw as Record<string, unknown>;
  for (const key of PROTECTED_CORE_FIELDS) {
    if (Object.prototype.hasOwnProperty.call(row, key)) {
      throw new Error(`protected Official Core field rejected: ${key}`);
    }
  }

  const questionId = clean(row.question_id);
  const lawName = clean(row.law_name);
  const examCode = clean(row.exam_code);
  const article = clean(row.article);
  const verificationLevel = clean(row.verification_level);
  const verificationBasis = clean(row.verification_basis);
  if (!questionId || !lawName || !article || !verificationBasis) {
    throw new Error("question_id, law_name, article, verification_basis are required");
  }
  if (!/^\d{3}-[12]$/.test(examCode)) throw new Error(`invalid exam_code: ${examCode}`);
  if (row.historical_version_checked !== true) {
    throw new Error(`historical_version_checked must be true: ${questionId}/${lawName}`);
  }
  if (!ALLOWED_LEVELS.has(verificationLevel)) {
    throw new Error(`unsupported verification_level: ${verificationLevel}`);
  }

  const version = row.selected_version;
  if (!version || typeof version !== "object" || Array.isArray(version)) {
    throw new Error(`selected_version missing: ${questionId}/${lawName}`);
  }
  const selected = version as Record<string, unknown>;
  const kind = clean(selected.kind);
  if (kind !== "current" && kind !== "oldver") {
    throw new Error(`selected_version.kind invalid: ${kind}`);
  }

  return {
    question_id: questionId,
    law_name: lawName,
    exam_code: examCode,
    article,
    historical_version_checked: true,
    verification_level: verificationLevel,
    verification_basis: verificationBasis,
    selected_version_kind: kind,
    selected_version_date: dateOrNull(selected.version_date, "selected_version.version_date", true)!,
    selected_effective_date: dateOrNull(selected.effective_date, "selected_version.effective_date"),
    selected_effective_date_scope: clean(selected.effective_date_scope) || null,
    selected_version_url: requireHttpsHost(selected.url, "law.moj.gov.tw", "selected_version.url"),
    historical_article_sha256: sha256(row.historical_article_sha256, "historical_article_sha256"),
    official_history_url: requireHttpsHost(row.official_history_url, "law.moj.gov.tw", "official_history_url"),
    exam_date_source_url: requireHttpsHost(row.exam_date_source_url, "wwwc.moex.gov.tw", "exam_date_source_url"),
  };
}

export function normalizeRegistry(payload: unknown): NormalizedRegistry {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("historical-law registry must be an object");
  }
  const src = payload as Record<string, unknown>;
  if (Number(src.schema_version) !== 1) throw new Error("registry schema_version must be 1");
  const rawRows = src.records;
  if (!Array.isArray(rawRows) || rawRows.length === 0 || rawRows.length > 5000) {
    throw new Error("registry records must contain 1-5000 items");
  }

  const records = rawRows.map(normalizeRecord).sort((a, b) =>
    evidenceKey(a).localeCompare(evidenceKey(b), "en")
  );
  const seen = new Set<string>();
  for (const row of records) {
    const key = evidenceKey(row);
    if (seen.has(key)) throw new Error(`duplicate historical-law evidence key: ${row.question_id}/${row.law_name}`);
    seen.add(key);
  }

  const machine = records.filter((r) => r.verification_level === MACHINE_LEVEL).length;
  const adjudicated = records.filter((r) => r.verification_level === ADJUDICATED_LEVEL).length;
  const declaredCount = Number(src.verified_record_count);
  const declaredChecked = Number(src.historical_version_checked_count);
  if (declaredCount !== records.length || declaredChecked !== records.length) {
    throw new Error("registry verified/check counts drift");
  }
  const levels = src.verification_level_counts;
  if (levels && typeof levels === "object" && !Array.isArray(levels)) {
    const map = levels as Record<string, unknown>;
    if (Number(map[MACHINE_LEVEL] ?? 0) !== machine || Number(map[ADJUDICATED_LEVEL] ?? 0) !== adjudicated) {
      throw new Error("registry verification_level_counts drift");
    }
  }

  return {
    schema_version: 1,
    record_count: records.length,
    historical_version_checked_count: records.length,
    machine_verified_count: machine,
    evidence_adjudicated_count: adjudicated,
    records,
  };
}

function stable(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  const obj = value as Record<string, unknown>;
  return `{${Object.keys(obj).sort().map((k) => `${JSON.stringify(k)}:${stable(obj[k])}`).join(",")}}`;
}

async function hashText(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function fingerprintRecord(row: RuntimeEvidenceRecord): Promise<string> {
  return hashText(stable(row));
}

export async function materializeRegistry(registry: NormalizedRegistry) {
  const rows = [];
  for (const row of registry.records) {
    rows.push({ ...row, evidence_sha256: await fingerprintRecord(row) });
  }
  const registrySha256 = await hashText(stable(rows.map((r) => ({
    question_id: r.question_id,
    law_name: r.law_name,
    evidence_sha256: r.evidence_sha256,
  }))));
  return { rows, registry_sha256: registrySha256 };
}

export function assertMonotonic(
  existing: Array<{ question_id?: unknown; law_name?: unknown; evidence_sha256?: unknown }>,
  incoming: Array<{ question_id: string; law_name: string; evidence_sha256: string }>,
): void {
  const incomingByKey = new Map(incoming.map((r) => [evidenceKey(r), r]));
  if (incoming.length < existing.length) {
    throw new Error(`verified registry shrank: incoming=${incoming.length} existing=${existing.length}`);
  }
  for (const old of existing) {
    const key = evidenceKey(old);
    const next = incomingByKey.get(key);
    if (!next) throw new Error(`verified evidence key disappeared: ${clean(old.question_id)}/${clean(old.law_name)}`);
    if (clean(next.evidence_sha256) !== clean(old.evidence_sha256)) {
      throw new Error(`verified evidence drift: ${clean(old.question_id)}/${clean(old.law_name)}`);
    }
  }
}
