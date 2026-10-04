import { assertEquals } from "jsr:@std/assert";
import {
  DEFAULT_CURRENT_LEGAL_MAX_AGE_MS,
  evaluateCurrentLegalTrust,
} from "./current_legal_trust.ts";

const NOW = Date.parse("2026-10-05T03:30:00Z");
const CHECKED = "2026-10-02T15:29:31Z";

function run(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 1,
    checked_at: CHECKED,
    baseline: false,
    lookup_error_count: 0,
    sync_status: "complete",
    source: "github_actions",
    ...overrides,
  };
}

function law(name = "社會救助法", overrides: Record<string, unknown> = {}) {
  return {
    canonical_name: name,
    watch_status: "unchanged",
    last_checked_at: CHECKED,
    ...overrides,
  };
}

Deno.test("healthy same-batch unchanged law is trusted for current intake only", () => {
  const d = evaluateCurrentLegalTrust(["社會救助法"], run(), [law()], { nowMs: NOW });
  assertEquals(d.trusted, true);
  assertEquals(d.reason, "trusted_current_intake");
  assertEquals(d.historical_version_proof, false);
});

Deno.test("global run must be complete non-baseline and error free", () => {
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ sync_status: "syncing" }), [law()], { nowMs: NOW }).trusted, false);
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ sync_status: "failed" }), [law()], { nowMs: NOW }).trusted, false);
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ baseline: true }), [law()], { nowMs: NOW }).trusted, false);
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ lookup_error_count: 1 }), [law()], { nowMs: NOW }).trusted, false);
});

Deno.test("stale or future run fails closed", () => {
  const stale = new Date(NOW - DEFAULT_CURRENT_LEGAL_MAX_AGE_MS - 1).toISOString();
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ checked_at: stale }), [law("社會救助法", { last_checked_at: stale })], { nowMs: NOW }).reason, "run_stale");
  const future = new Date(NOW + 11 * 60 * 1000).toISOString();
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ checked_at: future }), [law("社會救助法", { last_checked_at: future })], { nowMs: NOW }).reason, "run_checked_at_future");
});

Deno.test("registry row must be same batch and unchanged", () => {
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run(), [law("社會救助法", { watch_status: "changed" })], { nowMs: NOW }).reason, "law_not_unchanged");
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run(), [law("社會救助法", { watch_status: "missing" })], { nowMs: NOW }).reason, "law_not_unchanged");
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run(), [law("社會救助法", { last_checked_at: "2026-10-01T00:00:00Z" })], { nowMs: NOW }).reason, "law_batch_mismatch");
});

Deno.test("every named canonical law must be present in the same healthy batch", () => {
  const d = evaluateCurrentLegalTrust(
    ["社會救助法", "老人福利法"],
    run(),
    [law("社會救助法")],
    { nowMs: NOW },
  );
  assertEquals(d.trusted, false);
  assertEquals(d.reason, "law_registry_missing");
});

Deno.test("missing names and malformed run metadata fail closed", () => {
  assertEquals(evaluateCurrentLegalTrust([], run(), [law()], { nowMs: NOW }).reason, "no_canonical_law");
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], null, [law()], { nowMs: NOW }).reason, "run_health_missing");
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ schema_version: 2 }), [law()], { nowMs: NOW }).reason, "run_schema_untrusted");
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ source: "unknown" }), [law()], { nowMs: NOW }).reason, "run_source_untrusted");
  assertEquals(evaluateCurrentLegalTrust(["社會救助法"], run({ lookup_error_count: -1 }), [law()], { nowMs: NOW }).reason, "run_lookup_error_invalid");
});
