import { assertEquals, assertThrows } from "jsr:@std/assert";
import { normalizeRunHealth, withSyncStatus } from "./run_health.ts";

const records = [
  { found: true, changed: false },
  { found: true, changed: true },
  { found: false, changed: false },
];

function body(overrides: Record<string, unknown> = {}) {
  return {
    checked_at: "2026-10-05T00:00:00Z",
    baseline: false,
    watch_count: 3,
    matched_count: 2,
    missing_count: 1,
    changed_count: 1,
    lookup_error_count: 0,
    ...overrides,
  };
}

Deno.test("healthy run is normalized and starts syncing", () => {
  const row = normalizeRunHealth(body(), records);
  assertEquals(row.checked_at, "2026-10-05T00:00:00.000Z");
  assertEquals(row.baseline, false);
  assertEquals(row.lookup_error_count, 0);
  assertEquals(row.sync_status, "syncing");
  assertEquals(row.source, "github_actions");
});

Deno.test("lookup errors are preserved rather than hidden", () => {
  const row = normalizeRunHealth(body({ lookup_error_count: 1 }), records);
  assertEquals(row.lookup_error_count, 1);
});

Deno.test("baseline remains explicit and cannot masquerade as current evidence", () => {
  const row = normalizeRunHealth(body({ baseline: true }), records);
  assertEquals(row.baseline, true);
});

Deno.test("count mismatch fails closed", () => {
  assertThrows(() => normalizeRunHealth(body({ watch_count: 4 }), records));
  assertThrows(() => normalizeRunHealth(body({ matched_count: 3 }), records));
  assertThrows(() => normalizeRunHealth(body({ missing_count: 0 }), records));
  assertThrows(() => normalizeRunHealth(body({ changed_count: 0 }), records));
});

Deno.test("invalid timestamp and negative counts fail closed", () => {
  assertThrows(() => normalizeRunHealth(body({ checked_at: "not-a-date" }), records));
  assertThrows(() => normalizeRunHealth(body({ lookup_error_count: -1 }), records));
});

Deno.test("sync status transitions are explicit", () => {
  const row = normalizeRunHealth(body(), records);
  assertEquals(withSyncStatus(row, "complete").sync_status, "complete");
  assertEquals(withSyncStatus(row, "failed").sync_status, "failed");
});
