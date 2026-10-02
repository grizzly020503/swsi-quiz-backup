import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "grizzly020503/swsi-quiz-backup";
const ALLOWED_TASKS = new Set([
  "full-corpus-question-qa",
  "moex-social-worker-sync",
  "historical-law-guardian-queue",
]);
const TERMINAL_REVIEW_STATES = new Set(["resolved", "superseded", "invalid"]);
const COMPLETION_OUTCOMES = new Set([
  "success",
  "no_change",
  "failed_retryable",
  "failed_terminal",
  "quarantined",
]);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function verifyGitHubRepoToken(token: string) {
  const response = await fetch(`https://api.github.com/repos/${REPO}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "swsi-ops-ledger-gateway/1.0",
    },
  });
  if (!response.ok) return false;
  const repo = await response.json();
  return repo?.full_name === REPO && repo?.private === true;
}

function requiredText(body: Record<string, unknown>, key: string, max = 512) {
  const value = String(body[key] ?? "").trim();
  if (!value || value.length > max) throw new Error(`${key} is required or too long`);
  return value;
}

function optionalText(body: Record<string, unknown>, key: string, max = 2000) {
  if (body[key] === null || body[key] === undefined || body[key] === "") return null;
  const value = String(body[key]).trim();
  if (value.length > max) throw new Error(`${key} is too long`);
  return value || null;
}

function boundedInt(
  body: Record<string, unknown>,
  key: string,
  fallback: number,
  min: number,
  max: number,
) {
  if (body[key] === null || body[key] === undefined || body[key] === "") return fallback;
  const value = Number(body[key]);
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(`${key} must be an integer ${min}..${max}`);
  }
  return value;
}

function requireTask(body: Record<string, unknown>) {
  const taskId = requiredText(body, "task_id", 128);
  if (!ALLOWED_TASKS.has(taskId)) throw new Error(`unsupported task_id: ${taskId}`);
  return taskId;
}

function checkpointPayload(body: Record<string, unknown>) {
  const raw = body.checkpoint;
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("checkpoint must be an object");
  }
  const encoded = JSON.stringify(raw);
  if (encoded.length > 20000) throw new Error("checkpoint is too large");
  return raw;
}

function metadataPayload(body: Record<string, unknown>) {
  const raw = body.metadata ?? {};
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("metadata must be an object");
  }
  const encoded = JSON.stringify(raw);
  if (encoded.length > 20000) throw new Error("metadata is too large");
  return raw;
}

function requireReviewItem(body: Record<string, unknown>) {
  const itemId = requiredText(body, "item_id", 512);
  if (!itemId.startsWith("historical-law:")) {
    throw new Error("review item is outside the historical-law namespace");
  }
  return itemId;
}

function requireGuardianTask(body: Record<string, unknown>) {
  const taskId = requireTask(body);
  if (taskId !== "historical-law-guardian-queue") {
    throw new Error("review queue access is limited to historical-law-guardian-queue");
  }
  return taskId;
}

function nextCheckAt(body: Record<string, unknown>, now: Date) {
  if (body.next_check_seconds === null || body.next_check_seconds === undefined) return null;
  const seconds = boundedInt(body, "next_check_seconds", 0, 60, 604800);
  return new Date(now.getTime() + seconds * 1000).toISOString();
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const token = (req.headers.get("authorization") || "")
    .replace(/^Bearer\s+/i, "")
    .trim();
  if (!token) return json({ error: "missing GitHub Actions token" }, 401);
  if (!(await verifyGitHubRepoToken(token))) {
    return json({ error: "GitHub token cannot prove access to expected private repo" }, 403);
  }

  let body: Record<string, unknown>;
  try {
    const parsed = await req.json();
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return json({ error: "JSON object required" }, 400);
    }
    body = parsed as Record<string, unknown>;
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  const url = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return json({ error: "Supabase server env missing" }, 500);

  const sb = createClient(url, serviceRole, { auth: { persistSession: false } });
  const action = String(body.action ?? "").trim();
  const now = new Date();

  try {
    if (action === "claim") {
      const taskId = requireTask(body);
      const idempotencyKey = requiredText(body, "idempotency_key", 256);
      const workerId = requiredText(body, "worker_id", 256);
      const leaseSeconds = boundedInt(body, "lease_seconds", 900, 30, 3600);
      const maxAttempts = boundedInt(body, "max_attempts", 3, 1, 10);
      const { data, error } = await sb.rpc("swsi_ops_claim_task", {
        p_task_id: taskId,
        p_idempotency_key: idempotencyKey,
        p_worker_id: workerId,
        p_now: now.toISOString(),
        p_lease_seconds: leaseSeconds,
        p_max_attempts: maxAttempts,
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "checkpoint") {
      const taskId = requireTask(body);
      const checkpointVersion = boundedInt(body, "checkpoint_version", 1, 1, 1);
      const processedCount = boundedInt(body, "processed_count", 0, 0, 100000000);
      const extendLeaseSeconds = boundedInt(
        body,
        "extend_lease_seconds",
        900,
        30,
        3600,
      );
      const { data, error } = await sb.rpc("swsi_ops_checkpoint_task", {
        p_task_id: taskId,
        p_idempotency_key: requiredText(body, "idempotency_key", 256),
        p_worker_id: requiredText(body, "worker_id", 256),
        p_checkpoint: checkpointPayload(body),
        p_processed_count: processedCount,
        p_now: now.toISOString(),
        p_checkpoint_version: checkpointVersion,
        p_extend_lease_seconds: extendLeaseSeconds,
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "heartbeat") {
      const taskId = requireTask(body);
      const extendLeaseSeconds = boundedInt(
        body,
        "extend_lease_seconds",
        900,
        30,
        3600,
      );
      const { data, error } = await sb.rpc("swsi_ops_heartbeat_task", {
        p_task_id: taskId,
        p_idempotency_key: requiredText(body, "idempotency_key", 256),
        p_worker_id: requiredText(body, "worker_id", 256),
        p_now: now.toISOString(),
        p_extend_lease_seconds: extendLeaseSeconds,
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "complete") {
      const taskId = requireTask(body);
      const outcome = requiredText(body, "outcome", 64);
      if (!COMPLETION_OUTCOMES.has(outcome)) throw new Error("invalid outcome");
      const retryAfterSeconds = boundedInt(body, "retry_after_seconds", 60, 1, 86400);
      const { data, error } = await sb.rpc("swsi_ops_complete_task", {
        p_task_id: taskId,
        p_idempotency_key: requiredText(body, "idempotency_key", 256),
        p_worker_id: requiredText(body, "worker_id", 256),
        p_outcome: outcome,
        p_now: now.toISOString(),
        p_error_class: optionalText(body, "error_class", 256),
        p_error_message: optionalText(body, "error_message", 2000),
        p_retry_after_seconds: retryAfterSeconds,
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "review_upsert") {
      const taskId = requireGuardianTask(body);
      const { data, error } = await sb.rpc("swsi_ops_upsert_review_item", {
        p_item_id: requireReviewItem(body),
        p_reason: requiredText(body, "reason", 512),
        p_task_id: taskId,
        p_source_ref: optionalText(body, "source_ref", 1000),
        p_now: now.toISOString(),
        p_metadata: metadataPayload(body),
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "review_touch") {
      requireGuardianTask(body);
      const { data, error } = await sb.rpc("swsi_ops_touch_review_item", {
        p_item_id: requireReviewItem(body),
        p_now: now.toISOString(),
        p_error: optionalText(body, "error", 2000),
        p_next_check_at: nextCheckAt(body, now),
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "review_resolve") {
      requireGuardianTask(body);
      const finalState = requiredText(body, "final_state", 64);
      if (!TERMINAL_REVIEW_STATES.has(finalState)) {
        throw new Error("invalid review terminal state");
      }
      const { data, error } = await sb.rpc("swsi_ops_resolve_review_item", {
        p_item_id: requireReviewItem(body),
        p_final_state: finalState,
        p_resolution: requiredText(body, "resolution", 2000),
        p_now: now.toISOString(),
      });
      if (error) return json({ ok: false, error: error.message }, 409);
      return json({ ok: true, action, data });
    }

    if (action === "get_run") {
      const taskId = requireTask(body);
      const { data, error } = await sb
        .from("swsi_ops_task_runs")
        .select(
          "task_id,idempotency_key,status,attempt,max_attempts,worker_id,started_at,heartbeat_at,lease_expires_at,completed_at,last_success_at,checkpoint_version,checkpoint,processed_count,error_class,error_message,next_retry_at",
        )
        .eq("task_id", taskId)
        .eq("idempotency_key", requiredText(body, "idempotency_key", 256))
        .maybeSingle();
      if (error) return json({ ok: false, error: error.message }, 500);
      return json({ ok: true, action, data });
    }

    if (action === "open_reviews") {
      requireGuardianTask(body);
      const limit = boundedInt(body, "limit", 100, 1, 200);
      const { data, error } = await sb
        .from("swsi_ops_review_items")
        .select(
          "item_id,task_id,reason,source_ref,state,first_seen_at,last_attempt_at,attempt,last_error,next_check_at,metadata",
        )
        .eq("state", "open")
        .eq("task_id", "historical-law-guardian-queue")
        .order("first_seen_at", { ascending: true })
        .limit(limit);
      if (error) return json({ ok: false, error: error.message }, 500);
      return json({ ok: true, action, data });
    }

    return json({ error: "unsupported action" }, 400);
  } catch (error) {
    return json(
      { error: error instanceof Error ? error.message : "invalid request" },
      400,
    );
  }
});
