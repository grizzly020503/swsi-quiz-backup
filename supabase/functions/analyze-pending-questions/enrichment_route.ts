import type { CurrentLegalTrustDecision } from "./current_legal_trust.ts";

export type AnalyzerQuestionLike = {
  id?: unknown;
  subject?: unknown;
  question?: unknown;
  opt_a?: unknown;
  opt_b?: unknown;
  opt_c?: unknown;
  opt_d?: unknown;
  answer?: unknown;
  accepted_answers?: unknown;
  grading_mode?: unknown;
  legal_canonical_names?: unknown;
};

export type ValidatedCandidatePatch = Record<string, unknown> & {
  exp_others?: unknown;
  law?: unknown;
};

export type PreflightRoute =
  | { action: "proceed"; legal_names: string[]; legal_required: boolean }
  | { action: "hold_retry"; reason: string; legal_names: string[]; legal_required: boolean }
  | { action: "review"; reason: string; legal_names: string[]; legal_required: boolean };

export type FinalRoute =
  | { action: "ready" | "sanitized_ready"; patch: Record<string, unknown>; reason: string | null }
  | { action: "review"; patch: null; reason: string };

const LEGAL_HIGH_PATTERNS = [
  "家庭暴力防治法",
  "老人福利法",
  "社會救助法",
  "社會工作師法",
  "性別平等工作法",
  "兒童及少年福利與權益保障法",
  "兒童及少年性剝削防制條例",
  "長期照顧服務法",
  "性侵害犯罪防治法",
  "第\\s*[0-9一二三四五六七八九十百]+\\s*條(?:之\\s*[0-9一二三四五六七八九十百]+)?(?=$|[\\s，、。；：規定第項款])",
  "修正",
  "公布",
  "施行",
  "政策綱領",
  "計畫第?[一二三四五六七八九十0-9]+期",
] as const;

const RETRYABLE_LEGAL_TRUST_REASONS = new Set([
  "run_health_missing",
  "run_not_complete",
  "run_is_baseline",
  "run_lookup_error_present",
  "run_stale",
]);

function clean(value: unknown): string {
  return String(value ?? "").trim();
}

export function canonicalLegalNames(q: AnalyzerQuestionLike): string[] {
  const raw = Array.isArray(q.legal_canonical_names) ? q.legal_canonical_names : [];
  return [...new Set(raw.map((x) => clean(x)).filter(Boolean))];
}

export function officialAnswers(q: AnalyzerQuestionLike): string[] {
  const raw = Array.isArray(q.accepted_answers) ? q.accepted_answers : [];
  const multi = raw
    .map((x) => clean(x).toUpperCase())
    .filter((x) => ["A", "B", "C", "D"].includes(x));
  if (multi.length) return [...new Set(multi)];
  const single = clean(q.answer).toUpperCase();
  return ["A", "B", "C", "D"].includes(single) ? [single] : [];
}

export function officialQuestionText(q: AnalyzerQuestionLike): string {
  return [q.question, q.opt_a, q.opt_b, q.opt_c, q.opt_d].map(clean).filter(Boolean).join(" ");
}

export function hasLegalRiskSignal(q: AnalyzerQuestionLike): boolean {
  if (canonicalLegalNames(q).length) return true;
  const text = officialQuestionText(q);
  return LEGAL_HIGH_PATTERNS.some((pattern) => {
    try {
      return new RegExp(pattern, "i").test(text);
    } catch {
      return text.includes(pattern);
    }
  });
}

function acceptedOptionLabelsInOthers(text: string): Set<string> {
  const labels = new Set<string>();
  const patterns = [
    /(?:^|[\n。；;])\s*(?:選項\s*)?([ABCD])(?:\s*選項)?\s*[：:]/gim,
    /(?:^|[\n。；;])\s*([ABCD])\s*選項\s*[：:]?/gim,
  ];
  for (const pattern of patterns) {
    for (const match of text.matchAll(pattern)) labels.add(String(match[1]).toUpperCase());
  }
  return labels;
}

export function preflightQuestion(
  q: AnalyzerQuestionLike,
  legalTrust: CurrentLegalTrustDecision | null,
): PreflightRoute {
  const names = canonicalLegalNames(q);
  const legalRequired = hasLegalRiskSignal(q);
  const gradingMode = clean(q.grading_mode);
  const answers = officialAnswers(q);

  if (gradingMode !== "standard") {
    return { action: "review", reason: `special_grading:${gradingMode || "missing"}`, legal_names: names, legal_required: legalRequired };
  }
  if (!answers.length) {
    return { action: "review", reason: "official_answer_missing", legal_names: names, legal_required: legalRequired };
  }
  if (answers.length > 1) {
    return { action: "review", reason: "multiple_accepted_answers", legal_names: names, legal_required: legalRequired };
  }

  if (!legalRequired) {
    return { action: "proceed", legal_names: names, legal_required: false };
  }
  if (!names.length) {
    return { action: "review", reason: "legal_mapping_required", legal_names: names, legal_required: true };
  }
  if (!legalTrust?.trusted) {
    const reason = legalTrust?.reason || "legal_trust_unavailable";
    if (RETRYABLE_LEGAL_TRUST_REASONS.has(reason)) {
      return { action: "hold_retry", reason, legal_names: names, legal_required: true };
    }
    return { action: "review", reason, legal_names: names, legal_required: true };
  }

  return { action: "proceed", legal_names: names, legal_required: true };
}

export function finalizeValidatedCandidate(
  q: AnalyzerQuestionLike,
  candidate: ValidatedCandidatePatch,
  preflight: PreflightRoute,
): FinalRoute {
  if (preflight.action !== "proceed") {
    return { action: "review", patch: null, reason: preflight.reason };
  }

  const answers = new Set(officialAnswers(q));
  const mentioned = acceptedOptionLabelsInOthers(clean(candidate.exp_others));
  const conflicts = [...mentioned].filter((label) => answers.has(label));
  if (conflicts.length) {
    return { action: "review", patch: null, reason: `accepted_answer_in_exp_others:${conflicts.join(",")}` };
  }

  const patch: Record<string, unknown> = { ...candidate };
  let sanitized = false;
  if (preflight.legal_names.length) {
    const canonicalLaw = preflight.legal_names.join("、");
    if (clean(patch.law) !== canonicalLaw) sanitized = true;
    patch.law = canonicalLaw;
  } else if (clean(patch.law)) {
    patch.law = "";
    sanitized = true;
  }

  patch.analysis_status = "ready";
  patch.analysis_attempts = 0;
  patch.analysis_error = null;
  patch.analysis_started_at = null;

  return {
    action: sanitized ? "sanitized_ready" : "ready",
    patch,
    reason: sanitized ? "deterministic_law_projection" : null,
  };
}

export const RUNTIME_LEGAL_HIGH_PATTERNS = [...LEGAL_HIGH_PATTERNS];
