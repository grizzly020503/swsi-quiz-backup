import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "grizzly020503/swsi-quiz-backup";
const REPO_ID = 1345053575;
const ANALYSIS_FIELDS = [
  "topic", "major", "keywords", "theories", "laws", "difficulty", "frequency",
  "qtype", "related", "cluster", "cluster_name", "analysis_status",
] as const;
const LIST_FIELDS = new Set(["keywords", "theories", "laws", "related"]);
const DIFFICULTIES = new Set(["基礎", "中等", "困難"]);
const FREQUENCIES = new Set(["低頻", "中頻", "高頻"]);
const QTYPES = new Set([
  "理論說明題", "案例分析題", "比較題", "政策分析題", "法規題", "方案設計題", "綜合申論題",
]);
const ANALYSIS_STATES = new Set(["ready", "reviewed", "verified"]);
const TOP_LEVEL_FIELDS = new Set(["schema_version", "purpose", "records"]);
const RECORD_FIELDS = new Set(["id", ...ANALYSIS_FIELDS]);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
function fail(message: string): never { throw new Error(message); }
function exactKeys(value: Record<string, unknown>, allowed: Set<string>, label: string) {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (unknown.length) fail(`${label} contains unsupported fields: ${unknown.sort().join(",")}`);
}
function nonEmptyString(value: unknown, label: string) {
  if (typeof value !== "string" || !value.trim()) fail(`${label} must be a non-empty string`);
  return value.trim();
}
function stringList(value: unknown, label: string) {
  if (!Array.isArray(value)) fail(`${label} must be an array`);
  const out: string[] = [];
  for (const item of value) {
    const text = nonEmptyString(item, `${label} item`);
    if (!out.includes(text)) out.push(text);
  }
  return out;
}
async function verifyGitHubRepoWriteToken(token: string) {
  const response = await fetch(`https://api.github.com/repos/${REPO}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "swsi-essay-enrichment-sync/1.1",
    },
  });
  if (!response.ok) return false;
  const repo = await response.json();
  // Public visibility makes repository readability useless as an auth proof.
  // Require write capability on the immutable SWSI repository id instead.
  return Number(repo?.id) === REPO_ID && repo?.permissions?.push === true;
}

function validatePayload(payload: unknown) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) fail("payload must be an object");
  const root = payload as Record<string, unknown>;
  exactKeys(root, TOP_LEVEL_FIELDS, "payload");
  if (root.schema_version !== 1) fail("schema_version must equal 1");
  if (root.purpose !== undefined) nonEmptyString(root.purpose, "purpose");
  if (!Array.isArray(root.records) || root.records.length < 1 || root.records.length > 500) {
    fail("records must contain 1..500 essay enrichment rows");
  }

  const seen = new Set<string>();
  return root.records.map((raw, index) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) fail(`record ${index} must be an object`);
    const row = raw as Record<string, unknown>;
    exactKeys(row, RECORD_FIELDS, `record ${index}`);
    const id = nonEmptyString(row.id, `record ${index}.id`);
    if (!/^E-\d{3}-[12]-(HBSE|SW|DS|R|SP)-[12]$/.test(id)) fail(`record ${index}.id has invalid essay identity: ${id}`);
    if (seen.has(id)) fail(`duplicate essay id: ${id}`);
    seen.add(id);

    const update: Record<string, unknown> = {};
    for (const field of ANALYSIS_FIELDS) {
      if (!(field in row)) fail(`${id}.${field} is required`);
      if (LIST_FIELDS.has(field)) update[field] = stringList(row[field], `${id}.${field}`);
      else update[field] = nonEmptyString(row[field], `${id}.${field}`);
    }
    if (!DIFFICULTIES.has(String(update.difficulty))) fail(`${id}.difficulty invalid`);
    if (!FREQUENCIES.has(String(update.frequency))) fail(`${id}.frequency invalid`);
    if (!QTYPES.has(String(update.qtype))) fail(`${id}.qtype invalid`);
    if (!ANALYSIS_STATES.has(String(update.analysis_status))) fail(`${id}.analysis_status cannot regress to pending`);
    if (!/^[A-Z]{3,4}\d+$/.test(String(update.cluster))) fail(`${id}.cluster invalid`);
    return { id, update };
  });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!token) return json({ error: "missing GitHub Actions token" }, 401);
  if (!(await verifyGitHubRepoWriteToken(token))) {
    return json({ error: "GitHub token lacks write access to the SWSI repository" }, 403);
  }

  let payload: unknown;
  try { payload = await req.json(); }
  catch { return json({ error: "invalid JSON" }, 400); }

  let records: Array<{ id: string; update: Record<string, unknown> }>;
  try { records = validatePayload(payload); }
  catch (error) { return json({ error: error instanceof Error ? error.message : String(error) }, 400); }

  const url = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return json({ error: "Supabase server env missing" }, 500);
  const sb = createClient(url, serviceRole, { auth: { persistSession: false } });

  try {
    // Preflight every target before the first write. A typo/orphan ID must produce
    // zero writes rather than silently creating or partially targeting records.
    const ids = records.map((record) => record.id);
    const { data: existing, error: readError } = await sb
      .from("essays")
      .select("id")
      .in("id", ids);
    if (readError) throw new Error(`essay preflight read: ${readError.message}`);
    const existingIds = new Set((existing || []).map((row: { id: string }) => String(row.id)));
    const missing = ids.filter((id) => !existingIds.has(id));
    if (missing.length) return json({ error: `overlay targets missing from essays: ${missing.sort().join(",")}` }, 409);

    let updated = 0;
    for (const record of records) {
      const { data, error } = await sb
        .from("essays")
        .update(record.update)
        .eq("id", record.id)
        .select("id");
      if (error) throw new Error(`essay ${record.id} update: ${error.message}`);
      if (!data || data.length !== 1) throw new Error(`essay ${record.id} update affected ${data?.length || 0} rows`);
      updated += 1;
    }
    return json({ ok: true, updated, schema_version: 1 });
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : String(error) }, 500);
  }
});
