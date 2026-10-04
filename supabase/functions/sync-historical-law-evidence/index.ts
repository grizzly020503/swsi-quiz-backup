import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import {
  verifyGitHubActionsOidcToken,
  type GitHubActionsOidcPolicy,
} from "../_shared/github_actions_oidc.ts";
import {
  assertMonotonic,
  materializeRegistry,
  normalizeRegistry,
} from "./runtime_evidence.ts";

const HISTORICAL_SYNC_POLICY: GitHubActionsOidcPolicy = {
  allowedWorkflowRefs: new Set([
    "grizzly020503/swsi-quiz-backup/.github/workflows/historical-law-runtime-sync.yml@refs/heads/main",
  ]),
  allowedEvents: new Set(["workflow_dispatch"]),
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function markSnapshot(sb: any, row: Record<string, unknown>) {
  return sb
    .from("historical_law_runtime_evidence_snapshot")
    .upsert({ id: true, schema_version: 1, source: "github_actions", ...row, updated_at: new Date().toISOString() }, { onConflict: "id" });
}

async function assertQuestionIdsExist(sb: any, ids: string[]) {
  const unique = [...new Set(ids)].sort();
  const found = new Set<string>();
  for (let i = 0; i < unique.length; i += 100) {
    const batch = unique.slice(i, i + 100);
    const { data, error } = await sb.from("questions").select("id").in("id", batch);
    if (error) throw new Error(`question existence query: ${error.message}`);
    for (const row of data || []) found.add(String(row.id));
  }
  const missing = unique.filter((id) => !found.has(id));
  if (missing.length) throw new Error(`verified evidence references unknown question ids: ${missing.slice(0, 20).join(",")}`);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const token = (req.headers.get("authorization") || "")
    .replace(/^Bearer\s+/i, "")
    .trim();
  if (!token) return json({ error: "missing GitHub Actions OIDC token" }, 401);
  try {
    await verifyGitHubActionsOidcToken(token, HISTORICAL_SYNC_POLICY);
  } catch (e) {
    console.warn("historical-law OIDC auth rejected", e instanceof Error ? e.message : String(e));
    return json({ error: "GitHub Actions OIDC authorization rejected" }, 403);
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  let normalized;
  let materialized;
  try {
    normalized = normalizeRegistry(body);
    materialized = await materializeRegistry(normalized);
  } catch (e) {
    return json({ error: `invalid historical-law registry: ${e instanceof Error ? e.message : String(e)}` }, 400);
  }

  const url = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return json({ error: "Supabase server env missing" }, 500);
  const sb = createClient(url, serviceRole, { auth: { persistSession: false } });

  const { data: previousSnapshot, error: snapshotReadError } = await sb
    .from("historical_law_runtime_evidence_snapshot")
    .select("registry_sha256,record_count,sync_status")
    .eq("id", true)
    .maybeSingle();
  if (snapshotReadError) return json({ error: `snapshot read: ${snapshotReadError.message}` }, 500);

  const { data: existingRows, error: existingError } = await sb
    .from("historical_law_runtime_evidence")
    .select("question_id,law_name,evidence_sha256");
  if (existingError) return json({ error: `existing evidence read: ${existingError.message}` }, 500);

  try {
    const existing = existingRows || [];
    if (previousSnapshot?.sync_status === "complete" && Number(previousSnapshot.record_count) !== existing.length) {
      throw new Error(
        `existing runtime evidence completeness drift: snapshot=${previousSnapshot.record_count} rows=${existing.length}`,
      );
    }
    assertMonotonic(existing, materialized.rows);
    await assertQuestionIdsExist(sb, materialized.rows.map((r) => r.question_id));
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : String(e) }, 409);
  }

  const snapshotBase = {
    registry_sha256: materialized.registry_sha256,
    record_count: normalized.record_count,
    historical_version_checked_count: normalized.historical_version_checked_count,
    machine_verified_count: normalized.machine_verified_count,
    evidence_adjudicated_count: normalized.evidence_adjudicated_count,
  };

  const { error: startError } = await markSnapshot(sb, { ...snapshotBase, sync_status: "syncing" });
  if (startError) return json({ error: `snapshot syncing: ${startError.message}` }, 500);

  const syncedAt = new Date().toISOString();
  const rows = materialized.rows.map((r) => ({
    ...r,
    source_registry_sha256: materialized.registry_sha256,
    synced_at: syncedAt,
  }));
  const { error: upsertError } = await sb
    .from("historical_law_runtime_evidence")
    .upsert(rows, { onConflict: "question_id,law_name" });
  if (upsertError) {
    await markSnapshot(sb, { ...snapshotBase, sync_status: "failed" });
    return json({ error: `evidence upsert: ${upsertError.message}`, sync_status: "failed" }, 500);
  }

  const { error: completeError } = await markSnapshot(sb, { ...snapshotBase, sync_status: "complete" });
  if (completeError) {
    return json({ error: `snapshot complete: ${completeError.message}`, sync_status: "syncing" }, 500);
  }

  return json({
    ok: true,
    sync_status: "complete",
    registry_sha256: materialized.registry_sha256,
    record_count: normalized.record_count,
    machine_verified_count: normalized.machine_verified_count,
    evidence_adjudicated_count: normalized.evidence_adjudicated_count,
    previous_registry_sha256: previousSnapshot?.registry_sha256 || null,
  });
});
