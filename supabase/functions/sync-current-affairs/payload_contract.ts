/** Versioned envelope produced by scripts/current_affairs_watch.py.
 * Reject malformed, truncated or contradictory scanner output before any DB write.
 */
export type FeedPolicyCounts = { total: number; required: number };

export function validateCurrentAffairsPayload(
  body: unknown,
  feedsPolicy: FeedPolicyCounts,
  nowMs = Date.now(),
): string | null {
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return "invalid scanner payload object";
  }
  const payload = body as Record<string, unknown>;
  if (payload.schema_version !== 1) return "invalid scanner schema_version";
  // The scanner always stamps its UTC payload at the end of each run. Refuse
  // stale/replayed or future-dated output before creating a service-role client.
  const timestamp = payload.generated_at;
  if (typeof timestamp !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(timestamp)) {
    return "invalid scanner generated_at";
  }
  const generatedMs = Date.parse(timestamp);
  if (!Number.isFinite(generatedMs) || new Date(generatedMs).toISOString() !== timestamp.replace("Z", ".000Z")) {
    return "invalid scanner generated_at";
  }
  if (generatedMs > nowMs + 5 * 60 * 1000) return "scanner timestamp is in future";
  if (nowMs - generatedMs > 2 * 60 * 60 * 1000) return "scanner timestamp too old";
  if (!Array.isArray(payload.items)) return "invalid scanner items";
  if (!Array.isArray(payload.feed_errors) || !Array.isArray(payload.optional_feed_errors)) {
    return "invalid scanner feed error lists";
  }
  if (![...payload.feed_errors, ...payload.optional_feed_errors].every((item) => typeof item === "string")) {
    return "invalid scanner feed error item";
  }
  for (const key of ["fetched_count", "accepted_count", "feed_count"]) {
    const count = payload[key];
    if (!Number.isSafeInteger(count) || (count as number) < (key === "feed_count" ? 1 : 0)) {
      return "invalid scanner " + key;
    }
  }
  const fetched = payload.fetched_count as number;
  const accepted = payload.accepted_count as number;
  const feeds = payload.feed_count as number;
  if (accepted > fetched) return "scanner accepted_count exceeds fetched_count";
  if (feeds < payload.feed_errors.length + payload.optional_feed_errors.length) {
    return "scanner feed error count exceeds feed_count";
  }
  // Fail closed if scanner silently fell back from the reviewed 23-source registry
  // to the six default feeds, or if the curated required/optional split drifts.
  if (
    !Number.isSafeInteger(feedsPolicy.total) ||
    !Number.isSafeInteger(feedsPolicy.required) ||
    feedsPolicy.required < 1 || feedsPolicy.required > feedsPolicy.total
  ) return "invalid expected feed policy";
  if (feeds !== feedsPolicy.total) return "scanner feed registry count mismatch";
  if (
    payload.feed_errors.length > feedsPolicy.required ||
    payload.optional_feed_errors.length > feedsPolicy.total - feedsPolicy.required
  ) return "scanner feed class error count mismatch";
  if (feeds === payload.feed_errors.length + payload.optional_feed_errors.length) {
    return "scanner all feeds failed";
  }
  // Even if one optional media feed succeeded, an outage across ALL mandatory
  // official/primary sources must never create a successful durable audit row.
  if (payload.feed_errors.length === feedsPolicy.required) {
    return "scanner required feeds all failed";
  }
  // A healthy multi-source scan should see at least one upstream entry.
  // Zero *accepted* study events is legitimate; zero *fetched* entries from
  // every source is a degraded scan that must not refresh the DB audit.
  if (fetched === 0) return "scanner fetched no source entries";
  // The trusted scanner emits accepted[:100] while preserving the untruncated
  // accepted_count. A short/partial JSON payload must never be audited as success.
  if (payload.items.length !== Math.min(accepted, 100)) {
    return "scanner items count mismatch";
  }
  const seen = new Set<string>();
  for (const item of payload.items) {
    if (item === null || typeof item !== "object" || Array.isArray(item)) {
      return "invalid scanner item object";
    }
    const id = (item as Record<string, unknown>).id;
    if (typeof id !== "string" || !/^[a-f0-9]{32}$/.test(id)) {
      return "invalid scanner item id";
    }
    if (seen.has(id)) return "duplicate scanner item id";
    seen.add(id);
  }
  return null;
}
