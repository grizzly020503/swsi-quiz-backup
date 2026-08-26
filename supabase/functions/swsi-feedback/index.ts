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

function parseOfficialExamId(id: string | null) {
  if (!id) return null;
  const m = id.match(/^[A-Za-z]+-(\d{2,4})-(\d+)-(\d+)$/);
  if (!m) return null;
  return { year: Number(m[1]), round: Number(m[2]), qno: Number(m[3]) };
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

  const metadataInput = body.metadata && typeof body.metadata === "object" && !Array.isArray(body.metadata) ? body.metadata as Record<string, unknown> : {};
  const metadata = {
    screen_width: intOrNull(metadataInput.screen_width, 1, 10000),
    screen_height: intOrNull(metadataInput.screen_height, 1, 10000),
    locale: cleanText(metadataInput.locale, 40),
    referrer_host: cleanText(metadataInput.referrer_host, 200),
  };

  const contextId = cleanText(body.context_id, 240);
  let examYear = intOrNull(body.exam_year, 1, 9999);
  let examRound = intOrNull(body.exam_round, 1, 20);
  let questionNo = intOrNull(body.question_no, 1, 999);
  const parsed = (contextType === "mcq" || contextType === "essay") ? parseOfficialExamId(contextId) : null;
  if (parsed) {
    if (examYear === null) examYear = parsed.year;
    if (examRound === null) examRound = parsed.round;
    if (questionNo === null) questionNo = parsed.qno;
  }

  const { data, error } = await db.rpc("submit_swsi_feedback", {
    p_category: category,
    p_context_type: contextType,
    p_context_id: contextId,
    p_context_title: cleanText(body.context_title, 500),
    p_source_kind: sourceKind,
    p_subject: cleanText(body.subject, 120),
    p_exam_year: examYear,
    p_exam_round: examRound,
    p_question_no: questionNo,
    p_message: message,
    p_contact: contact,
    p_page_path: cleanText(body.page_path, 500),
    p_site_origin: origin,
    p_app_version: cleanText(body.app_version, 120),
    p_user_agent: cleanText(req.headers.get("User-Agent"), 500),
    p_client_hash: clientHash,
    p_metadata: metadata,
  });

  if (error) {
    const code = String(error.code || "");
    const msg = String(error.message || "");
    console.error("[swsi-feedback] rpc failed", { code, message: msg.slice(0, 160) });
    if (msg.includes("RATE_MINUTE")) return json(origin, { error: { message: "回報太快了，請一分鐘後再試。" } }, 429, { "Retry-After": "60" });
    if (msg.includes("RATE_DAY")) return json(origin, { error: { message: "今天的回報次數已達上限，請明天再試。" } }, 429);
    if (msg.includes("INVALID_CLIENT")) return json(origin, { error: { message: "Invalid client identifier" } }, 400);
    return json(origin, { error: { message: "回報暫時無法送出，請稍後再試。" } }, 503);
  }

  return json(origin, {
    ok: true,
    report_no: data,
    message: "收到，我們會核對這個問題。你可以繼續作答。",
  }, 201);
});
