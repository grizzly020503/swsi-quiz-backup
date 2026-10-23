import { validateCurrentAffairsPayload } from "./payload_contract.ts";

function expect(actual: string | null, expected: string | null, label: string) {
  if (actual !== expected) throw new Error(label + ": got " + actual + "; expected " + expected);
}
const ID1 = "a".repeat(32), ID2 = "b".repeat(32);
const NOW = Date.parse("2026-10-23T12:00:00Z");
const FEEDS = { total: 5, required: 3 };
function validate(body: unknown) { return validateCurrentAffairsPayload(body, FEEDS, NOW); }
function valid() {
  return {
    schema_version: 1,
    generated_at: "2026-10-23T12:00:00Z",
    fetched_count: 8,
    accepted_count: 2,
    feed_count: 5,
    feed_errors: ["example unavailable"],
    optional_feed_errors: [],
    items: [{ id: ID1 }, { id: ID2 }],
  };
}
Deno.test("scanner payload accepts normal, zero-match, optional outage and legitimate 100-item caps", () => {
  expect(validate(valid()), null, "normal");
  expect(validate({ ...valid(), generated_at: "2026-10-23T12:05:00Z" }), null, "clock skew boundary");
  expect(validate({ ...valid(), generated_at: "2026-10-23T10:00:00Z" }), null, "freshness boundary");
  expect(validate({ ...valid(), items: [], accepted_count: 0 }), null, "zero-match");
  expect(validate({ ...valid(), optional_feed_errors: ["optional unavailable", "optional timeout"] }), null, "optional-only outage");
  const capped = { ...valid(), fetched_count: 180, accepted_count: 130,
    items: Array.from({ length: 100 }, (_, i) => ({ id: i.toString(16).padStart(32, "0") })) };
  expect(validate(capped), null, "capped");
});
Deno.test("scanner rejects malformed/inconsistent envelope and mandatory-feed outage without DB effects", () => {
  const invalid: Array<[unknown, string]> = [
    [null, "invalid scanner payload object"],
    [[], "invalid scanner payload object"],
    [{ ...valid(), schema_version: 2 }, "invalid scanner schema_version"],
    [{ ...valid(), generated_at: null }, "invalid scanner generated_at"],
    [{ ...valid(), generated_at: "2026-10-23T12:00:00+08:00" }, "invalid scanner generated_at"],
    [{ ...valid(), generated_at: "2026-02-30T12:00:00Z" }, "invalid scanner generated_at"],
    [{ ...valid(), generated_at: "2026-10-23T12:05:01Z" }, "scanner timestamp is in future"],
    [{ ...valid(), generated_at: "2026-10-23T09:59:59Z" }, "scanner timestamp too old"],
    [{ ...valid(), items: undefined }, "invalid scanner items"],
    [{ ...valid(), feed_errors: null }, "invalid scanner feed error lists"],
    [{ ...valid(), optional_feed_errors: [4] }, "invalid scanner feed error item"],
    [{ ...valid(), fetched_count: -1 }, "invalid scanner fetched_count"],
    [{ ...valid(), accepted_count: 2.5 }, "invalid scanner accepted_count"],
    [{ ...valid(), feed_count: 0 }, "invalid scanner feed_count"],
    [{ ...valid(), fetched_count: 1 }, "scanner accepted_count exceeds fetched_count"],
    [{ ...valid(), feed_count: 1, feed_errors: ["a", "b"] }, "scanner feed error count exceeds feed_count"],
    [{ ...valid(), feed_count: 6 }, "scanner feed registry count mismatch"],
    [{ ...valid(), feed_errors: ["a", "b", "c", "d"] }, "scanner feed class error count mismatch"],
    [{ ...valid(), optional_feed_errors: ["a", "b", "c"] }, "scanner feed class error count mismatch"],
    [{ ...valid(), fetched_count: 0, accepted_count: 0, items: [], feed_errors: ["a", "b", "c"], optional_feed_errors: ["x", "y"] }, "scanner all feeds failed"],
    [{ ...valid(), fetched_count: 0, accepted_count: 0, items: [], feed_errors: ["a", "b", "c"], optional_feed_errors: [] }, "scanner required feeds all failed"],
    [{ ...valid(), fetched_count: 0, accepted_count: 0, items: [] }, "scanner fetched no source entries"],
    [{ ...valid(), items: [{ id: ID1 }] }, "scanner items count mismatch"],
    [{ ...valid(), items: [{ id: ID1 }, { id: ID1 }] }, "duplicate scanner item id"],
    [{ ...valid(), items: [{ id: ID1 }, null] }, "invalid scanner item object"],
    [{ ...valid(), items: [{ id: ID1 }, { id: ID2.toUpperCase() }] }, "invalid scanner item id"],
  ];
  for (const [payload, expected] of invalid) {
    expect(validate(payload), expected, expected);
  }
});
