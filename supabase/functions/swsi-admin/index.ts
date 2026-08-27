import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ALLOWED_ORIGINS = new Set([
  "https://swsi-quiznetlify.netlify.app",
  "https://wandering-wave-4418.c022050333.workers.dev"
]);

function cors(origin: string) {
  const allowed = ALLOWED_ORIGINS.has(origin) ? origin : "";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "GET, PATCH, OPTIONS",
    "Vary": "Origin",
  };
}

function json(origin: string, data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors(origin) },
  });
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("Origin") || "";
  if (!ALLOWED_ORIGINS.has(origin)) return json(origin, { error: "forbidden_origin" }, 403);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
  if (!['GET','PATCH'].includes(req.method)) return json(origin, { error: "method_not_allowed" }, 405);

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const authHeader = req.headers.get("Authorization") || "";
  const token = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!token) return json(origin, { error: "missing_token" }, 401);

  const admin = createClient(supabaseUrl, serviceRole, {
    auth: { persistSession: false, autoRefreshToken: false }
  });

  const { data: userData, error: userError } = await admin.auth.getUser(token);
  const user = userData?.user;
  if (userError || !user) return json(origin, { error: "invalid_session" }, 401);

  const { data: membership, error: membershipError } = await admin
    .from("swsi_admin_users")
    .select("user_id")
    .eq("user_id", user.id)
    .maybeSingle();
  if (membershipError || !membership) return json(origin, { error: "not_admin" }, 403);

  if (req.method === "PATCH") {
    let body: any;
    try { body = await req.json(); } catch { return json(origin, { error: "invalid_json" }, 400); }
    if (body?.action !== "feedback_update") return json(origin, { error: "invalid_action" }, 400);
    const reportNo = Number(body?.report_no);
    const allowedStatuses = new Set(["pending", "reviewed", "fixed", "no_change"]);
    const status = String(body?.status || "");
    const reviewerNote = typeof body?.reviewer_note === "string" ? body.reviewer_note.trim().slice(0, 3000) : null;
    if (!Number.isSafeInteger(reportNo) || reportNo < 1 || !allowedStatuses.has(status)) {
      return json(origin, { error: "invalid_feedback_update" }, 400);
    }
    const update: Record<string, unknown> = {
      status,
      reviewer_note: reviewerNote || null,
      updated_at: new Date().toISOString(),
      resolved_at: (status === "fixed" || status === "no_change") ? new Date().toISOString() : null,
    };
    const { data, error } = await admin
      .from("swsi_feedback_reports")
      .update(update)
      .eq("report_no", reportNo)
      .select("report_no,status,reviewer_note,resolved_at,updated_at")
      .single();
    if (error) return json(origin, { error: "feedback_update_failed" }, 500);
    return json(origin, { ok: true, feedback: data });
  }

  const [questionsRes, essaysRes, feedbackRes, feedbackCountRes, pendingRes, legalHitsRes] = await Promise.all([
    admin.from("questions").select("id", { count: "exact", head: true }),
    admin.from("essays").select("id", { count: "exact", head: true }),
    admin.from("swsi_feedback_reports")
      .select("report_no,created_at,updated_at,status,category,context_type,context_title,subject,exam_year,exam_round,question_no,message,contact,page_path,app_version,reviewer_note,resolved_at")
      .order("created_at", { ascending: false })
      .limit(100),
    admin.from("swsi_feedback_reports").select("id", { count: "exact", head: true }),
    admin.from("swsi_feedback_reports").select("id", { count: "exact", head: true }).eq("status", "pending"),
    admin.from("legal_watch_hits").select("id", { count: "exact", head: true }).is("resolved_at", null),
  ]);

  if (questionsRes.error || essaysRes.error || feedbackRes.error || feedbackCountRes.error || pendingRes.error || legalHitsRes.error) {
    return json(origin, { error: "admin_query_failed" }, 500);
  }

  return json(origin, {
    ok: true,
    generated_at: new Date().toISOString(),
    summary: {
      database: "ok",
      questions: questionsRes.count ?? 0,
      essays: essaysRes.count ?? 0,
      feedback_total: feedbackCountRes.count ?? 0,
      feedback_pending: pendingRes.count ?? 0,
      unresolved_legal_watch_hits: legalHitsRes.count ?? 0,
      analytics: "not_enabled",
      ai_telemetry: "not_enabled"
    },
    feedback: feedbackRes.data ?? []
  });
});
