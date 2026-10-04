import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import {
  verifyGitHubActionsOidcToken,
  type GitHubActionsOidcPolicy,
} from "../_shared/github_actions_oidc.ts";
import {
  questionArticleRefs,
  questionTouchesChangedArticles,
  normalizeArticleNo,
} from "./article_scope.ts";
import { normalizeRunHealth, withSyncStatus } from "./run_health.ts";

const LEGAL_WATCH_SYNC_POLICY: GitHubActionsOidcPolicy = {
  allowedWorkflowRefs: new Set([
    "grizzly020503/swsi-quiz-backup/.github/workflows/moex-social-worker-sync.yml@refs/heads/main",
  ]),
  allowedEvents: new Set(["schedule", "workflow_dispatch", "push"]),
};

type WatchRecord = {
  canonical_name: string;
  question_count?: number;
  found: boolean;
  source_type?: string | null;
  official_url?: string | null;
  official_modified_date?: string | null;
  previous_modified_date?: string | null;
  changed?: boolean;
  article_diff_available?: boolean;
  changed_articles?: unknown[];
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function safeOfficialUrl(value: unknown) {
  if (!value) return null;
  try {
    const u = new URL(String(value));
    if (u.protocol !== "https:") return null;
    if (!["law.moj.gov.tw", "sendlaw.moj.gov.tw"].includes(u.hostname)) return null;
    return u.toString();
  } catch {
    return null;
  }
}

function normalizedChangedArticles(record: WatchRecord): string[] {
  const out = new Set<string>();
  for (const value of Array.isArray(record.changed_articles) ? record.changed_articles : []) {
    const normalized = normalizeArticleNo(value);
    if (normalized) out.add(normalized);
  }
  return [...out].sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const token = (req.headers.get("authorization") || "")
    .replace(/^Bearer\s+/i, "")
    .trim();
  if (!token) return json({ error: "missing GitHub Actions OIDC token" }, 401);
  try {
    await verifyGitHubActionsOidcToken(token, LEGAL_WATCH_SYNC_POLICY);
  } catch (e) {
    console.warn("legal-watch OIDC auth rejected", e instanceof Error ? e.message : String(e));
    return json({ error: "GitHub Actions OIDC authorization rejected" }, 403);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  const records: WatchRecord[] = Array.isArray(body?.records) ? body.records : [];
  if (!records.length || records.length > 200) {
    return json({ error: "records must contain 1-200 items" }, 400);
  }

  let runHealth;
  try {
    runHealth = normalizeRunHealth(body as Record<string, unknown>, records, "syncing");
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return json({ error: `invalid legal-watch run health: ${message}` }, 400);
  }
  const baseline = runHealth.baseline;
  const checkedAt = runHealth.checked_at;

  for (const r of records) {
    if (!r || typeof r.canonical_name !== "string" || !r.canonical_name.trim()) {
      return json({ error: "invalid canonical_name" }, 400);
    }
    if (r.official_url && !safeOfficialUrl(r.official_url)) {
      return json({ error: `non-MOJ official_url rejected: ${r.canonical_name}` }, 400);
    }
    if (r.article_diff_available === true && !Array.isArray(r.changed_articles)) {
      return json({ error: `changed_articles must be an array: ${r.canonical_name}` }, 400);
    }
  }

  const url = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return json({ error: "Supabase server env missing" }, 500);
  const sb = createClient(url, serviceRole, { auth: { persistSession: false } });

  const { error: healthStartError } = await sb
    .from("legal_watch_run_health")
    .upsert(runHealth, { onConflict: "id" });
  if (healthStartError) {
    return json({ error: `legal watch run health start: ${healthStartError.message}` }, 500);
  }

  let changedLaws = 0;
  let articleScopedLaws = 0;
  let impactedQuestions = 0;
  let canonicalOnlyReferences = 0;
  const errors: string[] = [];

  for (const r of records) {
    const canonicalName = r.canonical_name.trim();
    const officialUrl = safeOfficialUrl(r.official_url);
    const changed = r.changed === true && !baseline && r.found === true;
    const changedArticles = normalizedChangedArticles(r);
    const articleScoped = changed && r.article_diff_available === true && changedArticles.length > 0;
    const watchStatus = !r.found ? "missing" : baseline ? "baseline" : changed ? "changed" : "unchanged";

    const registryRow: Record<string, unknown> = {
      canonical_name: canonicalName,
      question_count: Math.max(0, Number(r.question_count || 0)),
      source_type: r.source_type || null,
      official_url: officialUrl,
      official_modified_date: r.official_modified_date || null,
      previous_modified_date: r.previous_modified_date || null,
      last_checked_at: checkedAt,
      watch_status: watchStatus,
      note: !r.found
        ? "Official MOJ dataset did not contain an exact matching name on this check."
        : articleScoped
          ? `Article-level MOJ diff available: ${changedArticles.map((a) => `§${a}`).join(", ")}.`
          : changed
            ? "Article-level diff unavailable; broad law-level fallback remains active."
            : null,
      updated_at: new Date().toISOString(),
    };
    if (changed) registryRow.last_change_detected_at = checkedAt;

    const { error: registryError } = await sb
      .from("legal_reference_registry")
      .upsert(registryRow, { onConflict: "canonical_name" });
    if (registryError) {
      errors.push(`${canonicalName}: registry ${registryError.message}`);
      continue;
    }

    if (!changed || !r.official_modified_date) continue;
    changedLaws += 1;
    if (articleScoped) articleScopedLaws += 1;

    const { data: questions, error: qErr } = await sb
      .from("questions")
      .select("id,law,question,exp_why,exp_others,exp_trap,exp_raw,extension")
      .contains("legal_canonical_names", [canonicalName]);
    if (qErr) {
      errors.push(`${canonicalName}: questions ${qErr.message}`);
      continue;
    }

    const candidates = questions || [];
    let selected = candidates;
    let unscopedCount = 0;

    if (articleScoped) {
      selected = candidates.filter((q: any) =>
        questionTouchesChangedArticles(q, changedArticles)
      );
      unscopedCount = candidates.filter((q: any) => questionArticleRefs(q).size === 0).length;
      canonicalOnlyReferences += unscopedCount;

      const { error: registryScopeError } = await sb
        .from("legal_reference_registry")
        .update({
          question_count: candidates.length,
          note:
            `Article-level MOJ diff: ${changedArticles.map((a) => `§${a}`).join(", ")}. ` +
            `${selected.length} explicit article citation(s) auto-flagged; ` +
            `${unscopedCount} canonical-only question reference(s) were not guessed and remain for periodic manual audit.`,
          updated_at: new Date().toISOString(),
        })
        .eq("canonical_name", canonicalName);
      if (registryScopeError) {
        errors.push(`${canonicalName}: registry scope ${registryScopeError.message}`);
      }
    }

    const ids = selected.map((q: any) => String(q.id));
    impactedQuestions += ids.length;

    if (ids.length) {
      const changedArticleText = changedArticles.map((a) => `§${a}`).join(", ");
      const hitNote = articleScoped
        ? `Official MOJ article-level diff detected (${changedArticleText}); this question explicitly cites an affected article and requires legal review. Official question/answer were not modified.`
        : "Official MOJ latest-modified date changed and article-level diff was unavailable; broad legal review fallback applied. Official question/answer were not modified.";

      const hits = ids.map((questionId: string) => ({
        question_id: questionId,
        canonical_name: canonicalName,
        previous_modified_date: r.previous_modified_date || null,
        new_modified_date: String(r.official_modified_date),
        official_url: officialUrl,
        detected_at: checkedAt,
        note: hitNote,
      }));

      const { error: hitErr } = await sb
        .from("legal_watch_hits")
        .upsert(hits, {
          onConflict: "question_id,canonical_name,new_modified_date",
          ignoreDuplicates: true,
        });
      if (hitErr) errors.push(`${canonicalName}: hits ${hitErr.message}`);

      const legalNote = articleScoped
        ? `監測到《${canonicalName}》條文異動（${changedArticleText}）；本題明確引用受影響條文，需依最新法規重新核對。`
        : `監測到《${canonicalName}》官方修正日期變動，但條文差異無法可靠解析；本題依保守策略重新核對。`;

      const { error: updateErr } = await sb
        .from("questions")
        .update({
          legal_status: "changed",
          legal_checked_at: null,
          legal_note: legalNote,
          legal_source_url: officialUrl,
        })
        .in("id", ids);
      if (updateErr) errors.push(`${canonicalName}: mark changed ${updateErr.message}`);
    }
  }

  if (errors.length) {
    const failedHealth = withSyncStatus(runHealth, "failed");
    const { error: healthFailError } = await sb
      .from("legal_watch_run_health")
      .upsert(failedHealth, { onConflict: "id" });
    if (healthFailError) errors.push(`run health failed ${healthFailError.message}`);
    return json({
      ok: false,
      changed_laws: changedLaws,
      article_scoped_laws: articleScopedLaws,
      impacted_questions: impactedQuestions,
      canonical_only_references: canonicalOnlyReferences,
      run_health: "failed",
      errors,
    }, 500);
  }

  const completeHealth = withSyncStatus(runHealth, "complete");
  const { error: healthCompleteError } = await sb
    .from("legal_watch_run_health")
    .upsert(completeHealth, { onConflict: "id" });
  if (healthCompleteError) {
    return json({
      ok: false,
      changed_laws: changedLaws,
      article_scoped_laws: articleScopedLaws,
      impacted_questions: impactedQuestions,
      canonical_only_references: canonicalOnlyReferences,
      run_health: "syncing",
      errors: [`run health complete ${healthCompleteError.message}`],
    }, 500);
  }

  return json({
    ok: true,
    baseline,
    records: records.length,
    changed_laws: changedLaws,
    article_scoped_laws: articleScopedLaws,
    impacted_questions: impactedQuestions,
    canonical_only_references: canonicalOnlyReferences,
    run_health: "complete",
    lookup_error_count: runHealth.lookup_error_count,
  });
});
