import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "grizzly020503/swsi-quiz-backup";

type SourcePolicy = {
  feed: string;
  region: "taiwan" | "international";
  source_type: "official" | "news";
  article_hosts: string[];
};

// Keep this explicit and fail-closed. scripts/current_affairs_supabase_sync_smoke.py
// compares the policy to data/current_affairs_sources.json so a source-registry
// expansion cannot silently break or broaden the production sync endpoint.
const SOURCE_POLICY_JSON = String.raw`{
  "衛生福利部焦點新聞":{"feed":"https://www.mohw.gov.tw/rss-16-1.html","region":"taiwan","source_type":"official","article_hosts":["mohw.gov.tw"]},
  "衛生福利部公告訊息":{"feed":"https://www.mohw.gov.tw/rss-18-1.html","region":"taiwan","source_type":"official","article_hosts":["mohw.gov.tw"]},
  "中央社社會":{"feed":"https://feeds.feedburner.com/rsscna/social","region":"taiwan","source_type":"news","article_hosts":["cna.com.tw"]},
  "中央社生活":{"feed":"https://feeds.feedburner.com/rsscna/lifehealth","region":"taiwan","source_type":"news","article_hosts":["cna.com.tw"]},
  "中央社政治":{"feed":"https://feeds.feedburner.com/rsscna/politics","region":"taiwan","source_type":"news","article_hosts":["cna.com.tw"]},
  "中央社國際":{"feed":"https://feeds.feedburner.com/rsscna/intworld","region":"international","source_type":"news","article_hosts":["cna.com.tw"]},
  "內政部新聞發布":{"feed":"https://www.moi.gov.tw/OpenData.aspx?SN=76F358C679FAD4CF","region":"taiwan","source_type":"official","article_hosts":["moi.gov.tw"]},
  "行政院本院新聞":{"feed":"https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=3","region":"taiwan","source_type":"official","article_hosts":["ey.gov.tw"]},
  "教育部即時新聞":{"feed":"https://www.edu.tw/Rss_News.aspx?n=9E7AC85F1954DDA8","region":"taiwan","source_type":"official","article_hosts":["edu.tw"]},
  "教育部重要政策":{"feed":"https://www.edu.tw/Rss_WebArchive.aspx?n=FB01D469347C76A7","region":"taiwan","source_type":"official","article_hosts":["edu.tw"]},
  "移民署新住民政策法規":{"feed":"https://news.immigration.gov.tw/Rss/Content/8?lang=TW","region":"taiwan","source_type":"official","article_hosts":["immigration.gov.tw"]},
  "勞動部新聞稿":{"feed":"https://www.mol.gov.tw/1607/1632/1633/RssList","region":"taiwan","source_type":"official","article_hosts":["mol.gov.tw"]},
  "法務部新聞發布":{"feed":"https://www.moj.gov.tw/2204/2795/2796/rss","region":"taiwan","source_type":"official","article_hosts":["moj.gov.tw"]},
  "UN News English":{"feed":"https://news.un.org/feed/subscribe/en/news/all/rss.xml","region":"international","source_type":"official","article_hosts":["un.org"]},
  "WHO Newsroom":{"feed":"https://www.who.int/api/newsroom/newsitems","region":"international","source_type":"official","article_hosts":["who.int"]},
  "UNICEF Press Releases":{"feed":"https://www.unicef.org/media/press-releases","region":"international","source_type":"official","article_hosts":["unicef.org"]},
  "ILO Newsroom":{"feed":"https://www.ilo.org/resource/news/all-news-recent","region":"international","source_type":"official","article_hosts":["ilo.org"]},
  "TVBS新聞社會":{"feed":"https://news.tvbs.com.tw/realtime/local","region":"taiwan","source_type":"news","article_hosts":["tvbs.com.tw"]},
  "中天新聞社會":{"feed":"https://ctinews.com/rss/google-society.xml","region":"taiwan","source_type":"news","article_hosts":["ctinews.com"]},
  "中天新聞生活":{"feed":"https://ctinews.com/rss/google-life.xml","region":"taiwan","source_type":"news","article_hosts":["ctinews.com"]},
  "自由時報社會":{"feed":"https://news.ltn.com.tw/rss/society.xml","region":"taiwan","source_type":"news","article_hosts":["ltn.com.tw"]},
  "自由時報生活":{"feed":"https://news.ltn.com.tw/rss/life.xml","region":"taiwan","source_type":"news","article_hosts":["ltn.com.tw"]},
  "聯合新聞網社會":{"feed":"https://udn.com/rssfeed/news/2/6639?ch=news","region":"taiwan","source_type":"news","article_hosts":["udn.com"]}
}`;

const CATEGORIES_JSON = String.raw`[
  "兒少保護","家暴與性暴力","心理健康與成癮","長照與高齡","社會救助與居住","身障與人權",
  "移工與新住民","勞動與社會保障","教育與學生輔導","司法保護與修復式司法","少年司法與犯罪防治",
  "性別與家庭政策","災害與社區工作","社工專業與社福制度"
]`;

const SOURCE_POLICY = new Map<string, SourcePolicy>(
  Object.entries(JSON.parse(SOURCE_POLICY_JSON) as Record<string, SourcePolicy>),
);
const CATEGORIES = new Set<string>(JSON.parse(CATEGORIES_JSON) as string[]);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function verifyRepoToken(token: string) {
  const r = await fetch(`https://api.github.com/repos/${REPO}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "swsi-current-affairs-sync/1.1",
    },
  });
  if (!r.ok) return false;
  const repo = await r.json();
  return repo?.full_name === REPO && repo?.private === true;
}

function safeArticleUrl(value: unknown, allowedHosts: string[]) {
  try {
    const u = new URL(String(value || ""));
    if (u.protocol !== "https:") return false;
    const host = u.hostname.toLowerCase();
    return allowedHosts.some((raw) => {
      const root = String(raw || "").trim().toLowerCase();
      return Boolean(root) && (host === root || host.endsWith(`.${root}`));
    });
  } catch {
    return false;
  }
}

function normalizedSubjects(x: any) {
  const legacy = Array.isArray(x?.subjects) ? x.subjects.slice(0, 5).map(String) : [];
  const axes = Array.isArray(x?.exam_subject_axes)
    ? x.exam_subject_axes.slice(0, 5).map(String)
    : [];
  // The broad scanner category contains both profession and welfare-system lanes.
  // When the newer knowledge tree has positively classified the row as policy-only,
  // do not persist the older static category map that invents direct-practice or
  // professional-social-work relevance.
  if (
    String(x?.category || "") === "社工專業與社福制度" &&
    axes.includes("社會政策與社會立法") &&
    !axes.includes("社會工作")
  ) {
    return axes;
  }
  return legacy;
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const token = (req.headers.get("authorization") || "")
    .replace(/^Bearer\s+/i, "")
    .trim();
  if (!token || !(await verifyRepoToken(token))) {
    return json({ error: "unauthorized GitHub workflow" }, 403);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  const items = Array.isArray(body?.items) ? body.items : [];
  if (items.length > 200) return json({ error: "too many items" }, 400);

  for (const x of items) {
    if (!x || !/^[a-f0-9]{32}$/i.test(String(x.id || ""))) {
      return json({ error: "invalid id" }, 400);
    }
    if (typeof x.title !== "string" || !x.title.trim()) {
      return json({ error: `invalid title ${x.id}` }, 400);
    }

    const sourceName = String(x.source_name || "");
    const sourcePolicy = SOURCE_POLICY.get(sourceName);
    if (!sourcePolicy) return json({ error: `source rejected ${x.id}` }, 400);
    if (String(x.source_feed || "") !== sourcePolicy.feed) {
      return json({ error: `source_feed rejected ${x.id}` }, 400);
    }
    if (String(x.region || "") !== sourcePolicy.region) {
      return json({ error: `source region rejected ${x.id}` }, 400);
    }
    if (String(x.source_type || "") !== sourcePolicy.source_type) {
      return json({ error: `source type rejected ${x.id}` }, 400);
    }
    if (!safeArticleUrl(x.source_url, sourcePolicy.article_hosts)) {
      return json({ error: `source_url rejected ${x.id}` }, 400);
    }
    if (!CATEGORIES.has(String(x.category || ""))) {
      return json({ error: `category rejected ${x.id}` }, 400);
    }
    const score = Number(x.relevance_score);
    if (!Number.isInteger(score) || score < 0 || score > 10) {
      return json({ error: `score rejected ${x.id}` }, 400);
    }
  }

  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !key) return json({ error: "Supabase env missing" }, 500);
  const sb = createClient(url, key, { auth: { persistSession: false } });
  const now = new Date().toISOString();
  let upserted = 0;

  for (let i = 0; i < items.length; i += 100) {
    const batch = items.slice(i, i + 100);
    const ids = batch.map((x: any) => String(x.id));
    const { data: oldRows, error: oldErr } = await sb
      .from("current_affairs")
      .select("id,status,manual_note,first_seen_at")
      .in("id", ids);
    if (oldErr) return json({ error: `read existing: ${oldErr.message}` }, 500);
    const oldMap = new Map((oldRows || []).map((r: any) => [r.id, r]));
    const rows = batch.map((x: any) => {
      const old: any = oldMap.get(String(x.id));
      return {
        id: String(x.id),
        title: String(x.title).slice(0, 500),
        summary: String(x.summary || "").slice(0, 600),
        source_name: String(x.source_name),
        source_url: String(x.source_url),
        source_feed: String(x.source_feed || ""),
        published_at: x.published_at || null,
        region: String(x.region),
        category: String(x.category),
        relevance_score: Number(x.relevance_score),
        exam_tags: Array.isArray(x.exam_tags) ? x.exam_tags.slice(0, 15).map(String) : [],
        subjects: normalizedSubjects(x),
        status: old?.status || "candidate",
        manual_note: old?.manual_note || null,
        first_seen_at: old?.first_seen_at || now,
        last_seen_at: now,
        updated_at: now,
      };
    });
    const { error } = await sb.from("current_affairs").upsert(rows, { onConflict: "id" });
    if (error) return json({ error: `upsert: ${error.message}` }, 500);
    upserted += rows.length;
  }

  const cutoff = new Date(Date.now() - 1000 * 60 * 60 * 24 * 548).toISOString();
  await sb
    .from("current_affairs")
    .update({ status: "archived", updated_at: now })
    .eq("status", "candidate")
    .lt("published_at", cutoff);
  await sb.from("current_affairs_sync_runs").insert({
    fetched_count: Number(body?.fetched_count || 0),
    accepted_count: items.length,
    note: `feeds=${Array.isArray(body?.feed_errors) ? body.feed_errors.length : 0} errors`,
  });
  return json({ ok: true, upserted, feed_errors: Array.isArray(body?.feed_errors) ? body.feed_errors : [] });
});
