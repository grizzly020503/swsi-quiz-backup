import { assertEquals, assertRejects, assertThrows } from "jsr:@std/assert";
import {
  ADJUDICATED_LEVEL,
  MACHINE_LEVEL,
  assertMonotonic,
  materializeRegistry,
  normalizeRegistry,
} from "./runtime_evidence.ts";

function row(overrides: Record<string, unknown> = {}) {
  return {
    law_name: "社會救助法",
    question_id: "SP115-1-01",
    exam_code: "115-1",
    article: "4",
    historical_version_checked: true,
    verification_level: MACHINE_LEVEL,
    verification_basis: "verified Stage7 fixture",
    selected_version: {
      kind: "oldver",
      version_date: "2024-01-01",
      effective_date: "2024-01-01",
      effective_date_scope: "target_article",
      url: "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode=D0050078&lnndate=20240101",
    },
    historical_article_sha256: "a".repeat(64),
    official_history_url: "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode=D0050078",
    exam_date_source_url: "https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=115030",
    ...overrides,
  };
}

function registry(records = [row()]) {
  const machine = records.filter((r: any) => r.verification_level === MACHINE_LEVEL).length;
  const adjudicated = records.filter((r: any) => r.verification_level === ADJUDICATED_LEVEL).length;
  return {
    schema_version: 1,
    verified_record_count: records.length,
    historical_version_checked_count: records.length,
    verification_level_counts: {
      [MACHINE_LEVEL]: machine,
      [ADJUDICATED_LEVEL]: adjudicated,
    },
    records,
  };
}

Deno.test("verified registry normalizes to minimized runtime evidence", () => {
  const out = normalizeRegistry(registry());
  assertEquals(out.record_count, 1);
  assertEquals(out.machine_verified_count, 1);
  assertEquals(out.evidence_adjudicated_count, 0);
  const first = out.records[0];
  assertEquals(first.question_id, "SP115-1-01");
  assertEquals(first.selected_version_kind, "oldver");
  assertEquals((first as any).question, undefined);
  assertEquals((first as any).historical_semantic, undefined);
});

Deno.test("protected Official Core and unchecked evidence fail closed", () => {
  assertThrows(() => normalizeRegistry(registry([row({ question: "do not copy official core" })])));
  assertThrows(() => normalizeRegistry(registry([row({ historical_version_checked: false })])));
  assertThrows(() => normalizeRegistry(registry([row({ verification_level: "manual_guess" })])));
});

Deno.test("counts, duplicate keys, URL hosts and hashes fail closed", () => {
  const countDrift: any = registry();
  countDrift.verified_record_count = 2;
  assertThrows(() => normalizeRegistry(countDrift));
  assertThrows(() => normalizeRegistry(registry([row(), row()])));
  assertThrows(() => normalizeRegistry(registry([row({ official_history_url: "https://example.com/x" })])));
  assertThrows(() => normalizeRegistry(registry([row({ historical_article_sha256: "bad" })])));
});

Deno.test("fingerprints are stable and registry order independent", async () => {
  const a = row({ question_id: "SP115-1-01", historical_article_sha256: "a".repeat(64) });
  const b = row({
    question_id: "SP114-2-02",
    exam_code: "114-2",
    verification_level: ADJUDICATED_LEVEL,
    historical_article_sha256: "b".repeat(64),
  });
  const first = await materializeRegistry(normalizeRegistry(registry([a, b])));
  const second = await materializeRegistry(normalizeRegistry(registry([b, a])));
  assertEquals(first.registry_sha256, second.registry_sha256);
  assertEquals(first.rows.map((r) => r.evidence_sha256), second.rows.map((r) => r.evidence_sha256));
});

Deno.test("monotonic registry accepts append-only growth", async () => {
  const one = await materializeRegistry(normalizeRegistry(registry([row()])));
  const extra = row({
    question_id: "SP114-2-02",
    exam_code: "114-2",
    verification_level: ADJUDICATED_LEVEL,
    historical_article_sha256: "b".repeat(64),
  });
  const two = await materializeRegistry(normalizeRegistry(registry([row(), extra])));
  assertMonotonic(one.rows, two.rows);
});

Deno.test("monotonic registry rejects deletion and evidence drift", async () => {
  const base = await materializeRegistry(normalizeRegistry(registry([row()])));
  assertThrows(() => assertMonotonic(base.rows, []));

  const drifted = await materializeRegistry(normalizeRegistry(registry([
    row({ historical_article_sha256: "c".repeat(64) }),
  ])));
  assertThrows(() => assertMonotonic(base.rows, drifted.rows));
});

Deno.test("malformed selected version date rejects before hashing", async () => {
  await assertRejects(async () => {
    const normalized = normalizeRegistry(registry([row({
      selected_version: {
        kind: "current",
        version_date: "not-a-date",
        effective_date: null,
        url: "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050078",
      },
    })]));
    await materializeRegistry(normalized);
  });
});
