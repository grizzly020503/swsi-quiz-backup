import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const PRODUCTION_ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev";
const CLIENT_RE = /^[A-Za-z0-9_-]{16,128}$/;
const MODES = new Set(["text", "photo"]);
const OUTCOMES = new Set([
  "success",
  "rate_limited",
  "service_error",
  "timeout",
  "network_error",
  "client_error",
]);

function cors(origin: string) {
  return {
    "Access-Control-Allow-Origin": origin === PRODUCTION_ORIGIN ? origin : "",
    "Access-Control-Allow-Headers": "content-type, x-swsi-client-id",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function json(origin: string, payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors(origin) },
  });
}

async function sha256Hex(input: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("Origin") || "";
  if (origin !== PRODUCTION_ORIGIN) {
    return new Response(JSON.stringify({ error: "forbidden_origin" }), {
      status: 403,
      headers: { "Content-Type": "application/json; charset=utf-8", "Vary": "Origin" },
    });
  }

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors(origin) });
  }
  if (req.method !== "POST") return json(origin, { error: "method_not_allowed" }, 405);

  const type = (req.headers.get("Content-Type") || "").toLowerCase();
  if (!type.includes("application/json")) return json(origin, { error: "json_required" }, 415);

  const clientId = (req.headers.get("X-SWSI-Client-ID") || "").trim();
  if (!CLIENT_RE.test(clientId)) return json(origin, { error: "invalid_client" }, 400);

  let raw = "";
  try {
    raw = await req.text();
  } catch {
    return json(origin, { error: "invalid_body" }, 400);
  }
  if (new TextEncoder().encode(raw).byteLength > 512) {
    return json(origin, { error: "request_too_large" }, 413);
  }

  let body: Record<string, unknown> = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    return json(origin, { error: "invalid_json" }, 400);
  }

  const allowedKeys = new Set(["event", "mode", "outcome", "latency_ms"]);
  if (Object.keys(body).some((key) => !allowedKeys.has(key))) {
    return json(origin, { error: "unexpected_field" }, 400);
  }
  if (body.event !== "ai_request") return json(origin, { error: "invalid_event" }, 400);

  const mode = String(body.mode || "");
  const outcome = String(body.outcome || "");
  if (!MODES.has(mode) || !OUTCOMES.has(outcome)) {
    return json(origin, { error: "invalid_telemetry" }, 400);
  }

  const latencyRaw = Number(body.latency_ms);
  if (!Number.isFinite(latencyRaw)) return json(origin, { error: "invalid_latency" }, 400);
  const latencyMs = Math.max(0, Math.min(120000, Math.round(latencyRaw)));

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRole) return json(origin, { error: "service_unavailable" }, 503);

  const clientHash = await sha256Hex(clientId);
  const db = createClient(supabaseUrl, serviceRole, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const { error } = await db.rpc("record_swsi_ai_telemetry", {
    p_client_hash: clientHash,
    p_mode: mode,
    p_outcome: outcome,
    p_latency_ms: latencyMs,
  });

  if (error) {
    console.error("[swsi-ai-telemetry] record failed", { code: String(error.code || "unknown") });
    return json(origin, { error: "record_failed" }, 503);
  }

  return new Response(null, { status: 204, headers: cors(origin) });
});
