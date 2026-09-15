import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const STATIC_ALLOWED_ORIGINS = new Set([
  "https://swsi-quiznetlify.netlify.app",
  "https://wandering-wave-4418.c022050333.workers.dev"
]);
const NETLIFY_PREVIEW_ORIGIN = /^https:\/\/deploy-preview-\d+--swsi-quiznetlify\.netlify\.app$/;

function isAllowedOrigin(origin: string) {
  return STATIC_ALLOWED_ORIGINS.has(origin) || NETLIFY_PREVIEW_ORIGIN.test(origin);
}

function cors(origin: string) {
  const allowed = isAllowedOrigin(origin) ? origin : "";
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

function safeString(value: unknown, max = 240) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

function normalizeRisk(value: unknown) {
  const risk = safeString(value, 24).toLowerCase();
  return risk === "high" || risk === "medium" || risk === "low" ? risk : "untriaged";
}

function fallbackClusterKey(row: any) {
  const context = safeString(row?.context_id, 120);
  if (context) return `untriaged:${safeString(row?.context_type, 40) || "general"}:${context}:${safeString(row?.category, 60) || "other"}`;
  const path = safeString(row?.page_path, 180).split("?")[0] || "/";
  return `untriaged:${safeString(row?.context_type, 40) || "general"}:${safeString(row?.category, 60) || "other"}:${path}`;
}

function buildFeedbackClusters(rows: any[]) {
  const map = new Map<string, any>();
  for (const row of rows) {
    const triage = row?.metadata && typeof row.metadata === "object" ? row.metadata.triage : null;
    const clusterKey = safeString(triage?.cluster_key, 240) || fallbackClusterKey(row);
    const triageRisk = normalizeRisk(triage?.risk_level);
    let cluster = map.get(clusterKey);
    if (!cluster) {
      cluster = {
        cluster_key: clusterKey,
        count: 0,
        report_nos: [],
        category: safeString(row?.category, 60) || "other",
        context_type: safeString(row?.context_type, 40) || "general",
        context_id: safeString(row?.context_id, 120) || null,
        context_title: safeString(row?.context_title, 240) || null,
        subject: safeString(row?.subject, 120) || null,
        risk_level: triageRisk,
        confidence: Number.isFinite(Number(triage?.confidence)) ? Number(triage.confidence) : null,
        summary: safeString(triage?.summary, 500) || safeString(row?.message, 240) || "尚待自動分流",
        github_issue: safeString(triage?.github_issue, 240) || null,
        github_pr: safeString(triage?.github_pr, 240) || null,
        action: safeString(triage?.action, 40) || "pending_triage",
        latest_at: row?.created_at || null,
        status_counts: { pending: 0, reviewed: 0, fixed: 0, no_change: 0 },
      };
      map.set(clusterKey, cluster);
    }
    cluster.count += 1;
    if (cluster.report_nos.length < 50) cluster.report_nos.push(Number(row.report_no));
    if (row?.created_at && (!cluster.latest_at || String(row.created_at) > String(cluster.latest_at))) cluster.latest_at = row.created_at;
    if (row?.status && Object.prototype.hasOwnProperty.call(cluster.status_counts, row.status)) cluster.status_counts[row.status] += 1;
    if (cluster.risk_level === "untriaged" && triageRisk !== "untriaged") cluster.risk_level = triageRisk;
    if (!cluster.github_issue && safeString(triage?.github_issue, 240)) cluster.github_issue = safeString(triage.github_issue, 240);
    if (!cluster.github_pr && safeString(triage?.github_pr, 240)) cluster.github_pr = safeString(triage.github_pr, 240);
  }
  const riskRank: Record<string, number> = { high: 0, medium: 1, low: 2, untriaged: 3 };
  return Array.from(map.values()).sort((a, b) => {
    const ar = riskRank[a.risk_level] ?? 4;
    const br = riskRank[b.risk_level] ?? 4;
    if (ar !== br) return ar - br;
    if (b.status_counts.pending !== a.status_counts.pending) return b.status_counts.pending - a.status_counts.pending;
    if (b.count !== a.count) return b.count - a.count;
    return String(b.latest_at || "").localeCompare(String(a.latest_at || ""));
  });
}

function isActionableCluster(cluster: any) {
  return Number(cluster?.status_counts?.pending || 0) + Number(cluster?.status_counts?.reviewed || 0) > 0;
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("Origin") || "";
  if (!isAllowedOrigin(origin)) return json(origin, { error: "forbidden_origin" }, 403);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
  if (!["GET", "PATCH"].includes(req.method)) return json(origin, { error: "method_not_allowed" }, 405);

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const authHeader = req.headers.get("Authorization") || "";
  const token = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!token) return json(origin, { error: "missing_token" }, 401);

  const admin = createClient(supabaseUrl, serviceRole, {
    auth: { persistSession: false, autoRefreshToken: false },
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

  const [questionsRes, essaysRes, feedbackRes, feedbackCountRes, pendingRes, legalHitsRes, analyticsRes, aiTelemetryRes] = await Promise.all([
    admin.from("questions").select("id", { count: "exact", head: true }),
    admin.from("essays").select("id", { count: "exact", head: true }),
    admin.from("swsi_feedback_reports")
      .select("report_no,created_at,updated_at,status,category,context_type,context_id,context_title,subject,exam_year,exam_round,question_no,message,contact,page_path,app_version,metadata,reviewer_note,resolved_at")
      .order("created_at", { ascending: false })
      .limit(1000),
    admin.from("swsi_feedback_reports").select("id", { count: "exact", head: true }),
    admin.from("swsi_feedback_reports").select("id", { count: "exact", head: true }).eq("status", "pending"),
    admin.from("legal_watch_hits").select("id", { count: "exact", head: true }).is("resolved_at", null),
    admin.rpc("swsi_usage_summary"),
    admin.rpc("swsi_ai_telemetry_summary"),
  ]);

  if (questionsRes.error || essaysRes.error || feedbackRes.error || feedbackCountRes.error || pendingRes.error || legalHitsRes.error) {
    return json(origin, { error: "admin_query_failed" }, 500);
  }

  const feedbackRows = feedbackRes.data ?? [];
  const allFeedbackClusters = buildFeedbackClusters(feedbackRows);
  const feedbackClusters = allFeedbackClusters.filter(isActionableCluster);
  const rawFeedbackRows = feedbackRows.slice(0, 100);

  return json(origin, {
    ok: true,
    generated_at: new Date().toISOString(),
    summary: {
      database: "ok",
      questions: questionsRes.count ?? 0,
      essays: essaysRes.count ?? 0,
      feedback_total: feedbackCountRes.count ?? 0,
      feedback_pending: pendingRes.count ?? 0,
      feedback_cluster_count: feedbackClusters.length,
      feedback_resolved_cluster_count: allFeedbackClusters.length - feedbackClusters.length,
      feedback_window_count: feedbackRows.length,
      feedback_raw_count: rawFeedbackRows.length,
      unresolved_legal_watch_hits: legalHitsRes.count ?? 0,
      analytics: analyticsRes.error ? "unavailable" : "enabled",
      ai_telemetry: aiTelemetryRes.error ? "unavailable" : "enabled",
    },
    analytics: analyticsRes.error ? { enabled: false, status: "unavailable" } : (analyticsRes.data ?? { enabled: false, status: "empty" }),
    ai_telemetry: aiTelemetryRes.error
      ? { enabled: false, status: "unavailable" }
      : (aiTelemetryRes.data ?? { enabled: true, status: "idle", window_minutes: 60 }),
    feedback_clusters: feedbackClusters,
    feedback: rawFeedbackRows,
  });
});
