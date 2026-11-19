import { assertEquals } from "jsr:@std/assert";
import {
  HISTORICAL_ADJUDICATED_LEVEL,
  HISTORICAL_MACHINE_LEVEL,
  canonicalExamCode,
  evaluateHistoricalLawTrust,
  historicalReasonIsOperationalRetry,
} from "./historical_law_trust.ts";

const registrySha = "a".repeat(64);

function snapshot(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 1,
    registry_sha256: registrySha,
    record_count: 19,
    historical_version_checked_count: 19,
    sync_status: "complete",
    source: "github_actions",
    ...overrides,
  };
}

function row(lawName = "社會救助法", overrides: Record<string, unknown> = {}) {
  return {
    question_id: "SP115-1-01",
    law_name: lawName,
    exam_code: "115-1",
    historical_version_checked: true,
    verification_level: HISTORICAL_MACHINE_LEVEL,
    evidence_sha256: "b".repeat(64),
    source_registry_sha256: registrySha,
    ...overrides,
  };
}

Deno.test("canonical exam code prefers year/round and can fall back to id", () => {
  assertEquals(canonicalExamCode({ year: "115", round: "第一次", id: "x" }), "115-1");
  assertEquals(canonicalExamCode({ year: "114", round: "2", id: "x" }), "114-2");
  assertEquals(canonicalExamCode({ id: "SP113-2-40" }), "113-2");
  assertEquals(canonicalExamCode({ year: "115", round: "unknown", id: "bad" }), null);
});

Deno.test("all named laws need same complete verified registry batch", () => {
  const decision = evaluateHistoricalLawTrust(
    "SP115-1-01",
    "115-1",
    ["社會救助法", "老人福利法"],
    snapshot(),
    [row(), row("老人福利法", { verification_level: HISTORICAL_ADJUDICATED_LEVEL, evidence_sha256: "c".repeat(64) })],
  );
  assertEquals(decision.trusted, true);
  assertEquals(decision.historical_version_proof, true);
  assertEquals(decision.reason, "verified_exam_time_historical_law");
});

Deno.test("missing evidence, exam mismatch and registry mismatch fail closed", () => {
  assertEquals(
    evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法", "老人福利法"], snapshot(), [row()]).reason,
    "historical_evidence_missing",
  );
  assertEquals(
    evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], snapshot(), [row("社會救助法", { exam_code: "114-2" })]).reason,
    "historical_exam_code_mismatch",
  );
  assertEquals(
    evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], snapshot(), [row("社會救助法", { source_registry_sha256: "d".repeat(64) })]).reason,
    "historical_registry_batch_mismatch",
  );
});

Deno.test("snapshot and verification anomalies fail closed", () => {
  assertEquals(evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], null, []).reason, "historical_snapshot_missing");
  assertEquals(evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], snapshot({ sync_status: "syncing" }), [row()]).reason, "historical_snapshot_not_complete");
  assertEquals(evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], snapshot({ registry_sha256: "bad" }), [row()]).reason, "historical_snapshot_hash_invalid");
  assertEquals(evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], snapshot(), [row("社會救助法", { historical_version_checked: false })]).reason, "historical_checked_flag_missing");
  assertEquals(evaluateHistoricalLawTrust("SP115-1-01", "115-1", ["社會救助法"], snapshot(), [row("社會救助法", { verification_level: "guess" })]).reason, "historical_verification_level_untrusted");
});

Deno.test("only incomplete/missing snapshot are operational retry reasons", () => {
  assertEquals(historicalReasonIsOperationalRetry("historical_snapshot_missing"), true);
  assertEquals(historicalReasonIsOperationalRetry("historical_snapshot_not_complete"), true);
  assertEquals(historicalReasonIsOperationalRetry("historical_evidence_missing"), false);
  assertEquals(historicalReasonIsOperationalRetry("historical_registry_batch_mismatch"), false);
});
