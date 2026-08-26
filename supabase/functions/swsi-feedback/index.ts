import { createClient } from "npm:@supabase/supabase-js@2.57.4";

const ALLOWED_ORIGINS = new Set([
  "https://swsi-quiznetlify.netlify.app",
  "https://wandering-wave-4418.c022050333.workers.dev",
]);

const ALLOWED_CATEGORIES = new Set([
  "question_display",
  "answer_question",
  "explanation_error",
  "law_outdated",
  "theory_question",
  "site_bug",
  "ai_feedback",
  "suggestion",
  "other",
]);

const ALLOWED_CONTEXTS = new Set(["mcq", "essay", "theory", "law", "general"]);
const ALLOWED_SOURCES = new Set(["official_exam", "swsi", "ai", "unknown"]);

function cors(origin: string) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-SWSI-Client-ID",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function json(origin: string, payload: unknown, status = 200, extra: Record<string, string> = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...cors(origin),
      ...extra,
    },
  });
}

function cleanText(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  const s = value.replace(/\u0000/g, "").trim();
  if (!s) return null;
  return s.slice(0, max);
}

function intOrNull(value: unknown, min: number, max: number): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (!Number.isInteger(n) || n < min || n > max) return null;
  return n;
}

async function sha256Hex(input: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("Origin") || "";
  if (!ALLOWED_ORIGINS.has(origin)) {
    return new Response(JSON.stringify({ error: { message: "Forbidden origin" } }), {
      status: 403,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
  if (req.method !== "POST") return json(origin, { error: { message: "POST only" } }, 405, { Allow: "POST, OPTIONS" });

  const contentType = req.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    return json(origin, { error: { message: "JSON required" } }, 415);
  }

  let raw = "";
  try {
    raw = await req.text();
  } catch {
    return json(origin, { error: { message: "Invalid request body" } }, 400);
  }
  if (new TextEncoder().encode(raw).byteLength > 20_000) {
    return json(origin, { error: { message: "Request too large" } }, 413);
  }

  let body: Record<string, unknown>;
  try {
    body = JSON.parse(raw);
  } catch {
    return json(origin, { error: { message: "Invalid JSON" } }, 400);
  }

  const category = cleanText(body.category, 40);
  const contextType = cleanText(body.context_type, 20) || "general";
  const sourceKind = cleanText(body.source_kind, 30) || "unknown";
  const message = cleanText(body.message, 2000);
  const contact = cleanText(body.contact, 200);

  if (!category || !ALLOWED_CATEGORIES.has(category)) return json(origin, { error: { message: "Invalid category" } }, 400);
  if (!ALLOWED_CONTEXTS.has(contextType)) return json(origin, { error: { message: "Invalid context" } }, 400);
  if (!ALLOWED_SOURCES.has(sourceKind)) return json(origin, { error: { message: "Invalid source kind" } }, 400);
  if (!message || message.length < 3) return json(origin, { error: { message: "請至少寫 3 個字。" } }, 400);

  const clientId = cleanText(req.headers.get("X-SWSI-Client-ID"), 200);
  if (!clientId || clientId.length < 8) return json(origin, { error: { message: "Missing client identifier" } }, 400);
  const clientHash = await sha256Hex(clientId);

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRole) return json(origin, { error: { message: "Service unavailable" } }, 503);
  const db = createClient(supabaseUrl, serviceRole, { auth: { persistSession: false, autoRefreshToken: false } });

  const now = Date.now();
  const oneMinuteAgo = new Date(now - 60_000).toISOString();
  const oneDayAgo = new Date(now - 86_400_000).toISOString();

  const [{ count: minuteCount, error: minuteError }, { count: dayCount, error: dayError }] = await Promise.all([
    db.from("swsi_feedback_reports").select("id", { count: "exact", head: true }).eq("client_hash", clientHash).gte("created_at", oneMinuteAgo),
    db.from("swsi_feedback_reports").select("id", { count: "exact", head: true }).eq("client_hash", clientHash).gte("created_at", oneDayAgo),
  ]);
  if (minuteError || dayError) return json(origin, { error: { message: "Service unavailable" } }, 503);
  if ((minuteCount || 0) >= 3) return json(origin, { error: { message: "回報太快了，請一分鐘後再試。" } }, 429, { "Retry-After": "60" });
  if ((dayCount || 0) >= 30) return json(origin, { error: { message: "今天的回報次數已達上限，請明天再試。" } }, 429);

  const metadataInput = body.metadata && typeof body.metadata === "object" && !Array.isArray(body.metadata) ? body.metadata as Record<string, unknown> : {};
  const metadata = {
    screen_width: intOrNull(metadataInput.screen_width, 1, 10000),
    screen_height: intOrNull(metadataInput.screen_height, 1, 10000),
    locale: cleanText(metadataInput.locale, 40),
    referrer_host: cleanText(metadataInput.referrer_host, 200),
  };

  const row = {
    category,
    context_type: contextType,
    context_id: cleanText(body.context_id, 240),
    context_title: cleanText(body.context_title, 500),
    source_kind: sourceKind,
    subject: cleanText(body.subject, 120),
    exam_year: intOrNull(body.exam_year, 1, 9999),
    exam_round: intOrNull(body.exam_round, 1, 20),
    question_no: intOrNull(body.question_no, 1, 999),
    message,
    contact,
    page_path: cleanText(body.page_path, 500),
    site_origin: origin,
    app_version: cleanText(body.app_version, 120),
    user_agent: cleanText(req.headers.get("User-Agent"), 500),
    client_hash: clientHash,
    metadata,
  };

  const { data, error } = await db.from("swsi_feedback_reports").insert(row).select("report_no").single();
  if (error) return json(origin, { error: { message: "回報暫時無法送出，請稍後再試。" } }, 503);

  return json(origin, {
    ok: true,
    report_no: data.report_no,
    message: "收到，我們會核對這個問題。你可以繼續作答。",
  }, 201);
});
