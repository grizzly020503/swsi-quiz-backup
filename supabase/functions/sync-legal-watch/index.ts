import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "grizzly020503/swsi-quiz-backup";

type WatchRecord = {
  canonical_name: string;
  question_count?: number;
  found: boolean;
  source_type?: string | null;
  official_url?: string | null;
  official_modified_date?: string | null;
  previous_modified_date?: string | null;
  changed?: boolean;
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function verifyGitHubRepoToken(token: string) {
  const r = await fetch(`https://api.github.com/repos/${REPO}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "swsi-supabase-legal-watch/1.1",
    },
  });
  if (!r.ok) return false;
  const repo = await r.json();
  return repo?.full_name === REPO && repo?.private === true;
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

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const token = (req.headers.get("authorization") || "")
    .replace(/^Bearer\s+/i, "")
    .trim();
  if (!token) return json({ error: "missing GitHub Actions token" }, 401);
  if (!(await verifyGitHubRepoToken(token))) {
    return json({ error: "GitHub token cannot prove access to expected private repo" }, 403);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  const records: WatchRecord[] = Array.isArray(body?.records) ? body.records : [];
  const baseline = body?.baseline === true;
  const checkedAt = typeof body?.checked_at === "string" && body.checked_at
    ? body.checked_at
    : new Date().toISOString();

  if (!records.length || records.length > 200) {
    return json({ error: "records must contain 1-200 items" }, 400);
  }

  for (const r of records) {
    if (!r || typeof r.canonical_name !== "string" || !r.canonical_name.trim()) {
      return json({ error: "invalid canonical_name" }, 400);
    }
    if (r.official_url && !safeOfficialUrl(r.official_url)) {
      return json({ error: `non-MOJ official_url rejected: ${r.canonical_name}` }, 400);
    }
  }

  const url = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return json({ error: "Supabase server env missing" }, 500);
  const sb = createClient(url, serviceRole, { auth: { persistSession: false } });

  let changedLaws = 0;
  let impactedQuestions = 0;
  const errors: string[] = [];

  for (const r of records) {
    const canonicalName = r.canonical_name.trim();
    const officialUrl = safeOfficialUrl(r.official_url);
    const changed = r.changed === true && !baseline && r.found === true;
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
      note: !r.found ? "Official MOJ dataset did not contain an exact matching name on this check." : null,
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

    const { data: questions, error: qErr } = await sb
      .from("questions")
      .select("id")
      .contains("legal_canonical_names", [canonicalName]);
    if (qErr) {
      errors.push(`${canonicalName}: questions ${qErr.message}`);
      continue;
    }

    const ids = (questions || []).map((q: any) => String(q.id));
    impactedQuestions += ids.length;

    if (ids.length) {
      const hits = ids.map((questionId: string) => ({
        question_id: questionId,
        canonical_name: canonicalName,
        previous_modified_date: r.previous_modified_date || null,
        new_modified_date: String(r.official_modified_date),
        official_url: officialUrl,
        detected_at: checkedAt,
        note: "Official MOJ latest-modified date changed; question requires legal review. Official question/answer were not modified.",
      }));

      const { error: hitErr } = await sb
        .from("legal_watch_hits")
        .upsert(hits, {
          onConflict: "question_id,canonical_name,new_modified_date",
          ignoreDuplicates: true,
        });
      if (hitErr) errors.push(`${canonicalName}: hits ${hitErr.message}`);

      const { error: updateErr } = await sb
        .from("questions")
        .update({
          legal_status: "changed",
          legal_checked_at: null,
          legal_note: `監測到《${canonicalName}》官方修正日期變動；本題需依最新法規重新核對。`,
          legal_source_url: officialUrl,
        })
        .contains("legal_canonical_names", [canonicalName]);
      if (updateErr) errors.push(`${canonicalName}: mark changed ${updateErr.message}`);
    }
  }

  if (errors.length) {
    return json({ ok: false, changed_laws: changedLaws, impacted_questions: impactedQuestions, errors }, 500);
  }

  return json({
    ok: true,
    baseline,
    records: records.length,
    changed_laws: changedLaws,
    impacted_questions: impactedQuestions,
  });
});