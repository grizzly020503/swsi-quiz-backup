import { assertEquals } from "jsr:@std/assert";
import {
  finalizeValidatedCandidate,
  hasLegalRiskSignal,
  preflightQuestion,
  RUNTIME_LEGAL_HIGH_PATTERNS,
} from "./enrichment_route.ts";

const trusted = {
  trusted: true,
  reason: "trusted_current_intake",
  checked_at: "2026-10-05T00:00:00.000Z",
  historical_version_proof: false as const,
};

const retryTrust = {
  trusted: false,
  reason: "run_stale",
  checked_at: "2026-09-01T00:00:00.000Z",
  historical_version_proof: false as const,
};

function q(overrides: Record<string, unknown> = {}) {
  return {
    id: "115-2-社會工作-1",
    subject: "社會工作",
    question: "下列何者最符合優勢觀點？",
    opt_a: "重視案主優勢",
    opt_b: "只看病理",
    opt_c: "忽略環境",
    opt_d: "否定資源",
    answer: "A",
    accepted_answers: ["A"],
    grading_mode: "standard",
    legal_canonical_names: [],
    ...overrides,
  };
}

function candidate(overrides: Record<string, unknown> = {}) {
  return {
    major: "社會工作理論",
    topic: "優勢觀點 > 核心概念",
    keywords: "優勢,資源",
    exp_why: "A 選項符合題幹所描述的核心概念。",
    exp_others: "B：只看病理。C：忽略環境。D：否定資源。",
    exp_trap: "不要只看問題。",
    exp_raw: null,
    mnemonic: "先看優勢。",
    extension: "比較優勢與病理觀點。",
    law: "",
    mistake: "概念混淆",
    analysis_status: "ready",
    analysis_attempts: 0,
    analysis_error: null,
    analysis_started_at: null,
    ...overrides,
  };
}

Deno.test("runtime legal risk patterns stay identical to Unified QA policy", async () => {
  const policy = JSON.parse(await Deno.readTextFile("data/question_qa_policy_v1.json"));
  assertEquals(RUNTIME_LEGAL_HIGH_PATTERNS, policy.risk_signals.legal_or_policy_high);
});

Deno.test("ordinary clean single-answer question proceeds without legal evidence", () => {
  const p = preflightQuestion(q(), null);
  assertEquals(p.action, "proceed");
  const f = finalizeValidatedCandidate(q(), candidate(), p);
  assertEquals(f.action, "ready");
});

Deno.test("special grading and multi-answer are held before model publication", () => {
  assertEquals(preflightQuestion(q({ grading_mode: "all_credit" }), null).action, "review");
  assertEquals(preflightQuestion(q({ accepted_answers: ["A", "B"] }), null).action, "review");
});

Deno.test("legal question requires mapping, current trust, and exam-time evidence", () => {
  const legal = q({
    subject: "社會政策與社會立法",
    question: "依社會救助法規定，下列何者正確？",
    legal_canonical_names: ["社會救助法"],
  });
  assertEquals(hasLegalRiskSignal(legal), true);
  assertEquals(preflightQuestion(legal, retryTrust).action, "hold_retry");
  const currentOnly = preflightQuestion(legal, trusted);
  assertEquals(currentOnly.action, "review");
  if (currentOnly.action === "review") assertEquals(currentOnly.reason, "historical_law_evidence_required");
  assertEquals(preflightQuestion(legal, trusted, true).action, "proceed");

  const unmapped = q({ question: "依第十條規定，下列何者正確？" });
  const p = preflightQuestion(unmapped, null);
  assertEquals(p.action, "review");
  if (p.action === "review") assertEquals(p.reason, "legal_mapping_required");
});

Deno.test("trusted historical legal candidate law is replaced by deterministic canonical mapping", () => {
  const legal = q({ question: "依社會救助法規定，下列何者正確？", legal_canonical_names: ["社會救助法"] });
  const p = preflightQuestion(legal, trusted, true);
  const f = finalizeValidatedCandidate(legal, candidate({ law: "其他錯誤法規" }), p);
  assertEquals(f.action, "sanitized_ready");
  if (f.patch) assertEquals(f.patch.law, "社會救助法");
});

Deno.test("nonlegal AI law hallucination is dropped without human review", () => {
  const p = preflightQuestion(q(), null);
  const f = finalizeValidatedCandidate(q(), candidate({ law: "不存在的法" }), p);
  assertEquals(f.action, "sanitized_ready");
  if (f.patch) assertEquals(f.patch.law, "");
});

Deno.test("accepted answer explicitly placed in exp_others routes to review", () => {
  const p = preflightQuestion(q(), null);
  const f = finalizeValidatedCandidate(q(), candidate({ exp_others: "A：其實是錯的。B：不符。" }), p);
  assertEquals(f.action, "review");
  assertEquals(f.patch, null);
});

Deno.test("changed/missing or contract-anomalous legal evidence is review, not retry", () => {
  const legal = q({ question: "依社會救助法規定，下列何者正確？", legal_canonical_names: ["社會救助法"] });
  for (const reason of ["law_not_unchanged", "law_registry_missing", "law_batch_mismatch", "run_schema_untrusted"]) {
    const d = { trusted: false, reason, checked_at: null, historical_version_proof: false as const };
    const p = preflightQuestion(legal, d);
    assertEquals(p.action, "review");
  }
});

Deno.test("operational legal-watch problems hold retry rather than creating human debt", () => {
  const legal = q({ question: "依社會救助法規定，下列何者正確？", legal_canonical_names: ["社會救助法"] });
  for (const reason of ["run_health_missing", "run_not_complete", "run_is_baseline", "run_lookup_error_present", "run_stale"]) {
    const d = { trusted: false, reason, checked_at: null, historical_version_proof: false as const };
    const p = preflightQuestion(legal, d);
    assertEquals(p.action, "hold_retry");
  }
});
