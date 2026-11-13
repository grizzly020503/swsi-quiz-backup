export default {
  async scheduled(controller, env) {
    if (controller.cron !== '*/15 * * * *') throw Error('unexpected heartbeat cron');
    await runTaskHeartbeat(env, controller.scheduledTime);
  },
  async fetch(request, env) {
    if (new URL(request.url).pathname === '/ops/task-heartbeat') {
      return readTaskHeartbeat(request, env);
    }
    const PUBLIC_ORIGINS = new Set([
      "https://swsi-quiznetlify.netlify.app",
      "https://wandering-wave-4418.c022050333.workers.dev"
    ]);

    const PUBLIC_MODEL = "qwen/qwen3.8-27b";
    const LEGACY_PUBLIC_MODEL = "qwen/qwen3.6-27b";
    const PUBLIC_MODELS = new Set([PUBLIC_MODEL, LEGACY_PUBLIC_MODEL]);
    const INTERNAL_MODELS = new Set([
      PUBLIC_MODEL,
      "openai/gpt-oss-120b"
    ]);

    // 目前先採保守免費額度；觀察一週後再調整。
    const CLIENT_TEXT_DAILY = 10;
    const CLIENT_PHOTO_DAILY = 3;
    const GLOBAL_TEXT_DAILY = 50;
    const GLOBAL_PHOTO_DAILY = 10;

    const origin = request.headers.get("Origin") || "";
    const suppliedInternalKey = request.headers.get("X-SWSI-Internal-Key") || "";
    const isPublic = PUBLIC_ORIGINS.has(origin);
    const isInternal = await safeSecretEqual(
      suppliedInternalKey,
      env.SWSI_INTERNAL_KEY || ""
    );

    function corsHeaders() {
      if (!isPublic) return {};
      return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-SWSI-Client-ID",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin"
      };
    }

    function json(data, status = 200, extraHeaders = {}) {
      return new Response(JSON.stringify(data), {
        status,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-store",
          ...corsHeaders(),
          ...extraHeaders
        }
      });
    }

    if (!isPublic && !isInternal) {
      return new Response(
        JSON.stringify({ error: { message: "Forbidden" } }),
        {
          status: 403,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store"
          }
        }
      );
    }

    // 瀏覽器 CORS preflight 只對公開來源開放。
    if (request.method === "OPTIONS") {
      if (!isPublic) return new Response(null, { status: 403, headers: { "Cache-Control": "no-store" } });
      return new Response(null, {
        status: 204,
        headers: { ...corsHeaders(), "Cache-Control": "no-store" }
      });
    }

    if (request.method !== "POST") {
      return json(
        { error: { message: "POST only" } },
        405,
        { "Allow": "POST, OPTIONS" }
      );
    }

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const ua = request.headers.get("User-Agent") || "unknown";

    // 月更前舊前端沒有 X-SWSI-Client-ID，先 fallback 到 IP + UA。
    // 下一次 Netlify 月更後，前端應改成 localStorage UUID 並送此 header。
    const suppliedClientId = (request.headers.get("X-SWSI-Client-ID") || "").trim();
    const validClientId = /^[A-Za-z0-9_-]{16,128}$/.test(suppliedClientId)
      ? suppliedClientId
      : "";
    const rawClientKey = validClientId
      ? `cid:${validClientId}`
      : `fallback:${ip}|${ua}`;
    const clientKey = await sha256Short(rawClientKey);

    // 公開學生請求才套防暴衝；後台自動解析有自己的 job-key / 每日排程限制。
    if (isPublic && !isInternal) {
      const clientLimit = await env.AI_RATE_LIMIT.limit({ key: clientKey });
      if (!clientLimit.success) {
        return json(
          { error: { message: "操作太快了，請等一分鐘再使用 AI 批改。", code: "CLIENT_MINUTE_RATE_LIMIT" } },
          429,
          { "Retry-After": "60" }
        );
      }

      const ipLimit = await env.AI_IP_LIMIT.limit({ key: ip });
      if (!ipLimit.success) {
        return json(
          { error: { message: "目前這個網路的 AI 使用量太高，請稍後再試。", code: "IP_MINUTE_RATE_LIMIT" } },
          429,
          { "Retry-After": "60" }
        );
      }
    }

    let raw;
    try {
      raw = await request.text();
    } catch {
      return json({ error: { message: "Invalid request body" } }, 400);
    }

    if (new TextEncoder().encode(raw).byteLength > 4_000_000) {
      return json({ error: { message: "Request too large" } }, 413);
    }

    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return json({ error: { message: "Invalid JSON" } }, 400);
    }

    if (
      !body ||
      !Array.isArray(body.messages) ||
      body.messages.length < 1 ||
      body.messages.length > 3
    ) {
      return json({ error: { message: "Invalid AI request" } }, 400);
    }

    if (isInternal) {
      if (!INTERNAL_MODELS.has(body.model)) {
        return json({ error: { message: "Invalid internal model" } }, 400);
      }
    } else if (!PUBLIC_MODELS.has(body.model)) {
      return json({ error: { message: "Invalid AI model" } }, 400);
    }

    let imageCount = 0;
    for (const message of body.messages) {
      if (!message || !["user", "system"].includes(message.role)) {
        return json({ error: { message: "Invalid message" } }, 400);
      }
      if (Array.isArray(message.content)) {
        for (const item of message.content) {
          if (item?.type === "image_url") {
            imageCount++;
            // 公開瀏覽器只接受前端 canvas 產生的 JPEG data URL；
            // 後台內部請求仍保留較彈性的模型輸入能力。
            if (!isInternal) {
              const imageUrl = String(item?.image_url?.url || "");
              if (!imageUrl.startsWith("data:image/jpeg;base64,")) {
                return json({ error: { message: "公開照片只接受 JPEG 上傳內容。" } }, 400);
              }
            }
          }
        }
      }
    }

    // Qwen 3.8 官方模型限制採保守值：最多 3 張輸入圖片。
    if (imageCount > 3) {
      return json({ error: { message: "最多一次上傳 3 張照片。" } }, 400);
    }

    const quotaKind = imageCount > 0 ? "photo" : "text";
    let quotaReserved = false;

    // 只有完整、有效、真的要送 Groq 的公開請求才占每日額度。
    if (isPublic && !isInternal) {
      try {
        const date = taipeiDate();
        const limits = {
          clientText: CLIENT_TEXT_DAILY,
          clientPhoto: CLIENT_PHOTO_DAILY,
          globalText: GLOBAL_TEXT_DAILY,
          globalPhoto: GLOBAL_PHOTO_DAILY
        };

        // 全站額度已滿時先讀一行就直接拒絕，避免每次重試都先寫 client 再退款。
        if (await isGlobalQuotaFull(env.AI_QUOTA_DB, date, quotaKind, limits)) {
          return json(
            { error: { message: "今天全平台的免費 AI 額度已用完，題庫、錯題與申論骨架仍可正常使用。", code: "GLOBAL_DAILY_QUOTA" } },
            429,
            { "Retry-After": String(secondsUntilTaipeiMidnight()) }
          );
        }

        const q = await reservePublicQuota(
          env.AI_QUOTA_DB,
          date,
          clientKey,
          quotaKind,
          limits
        );

        if (!q.ok) {
          const msg = q.scope === "client"
            ? (quotaKind === "photo"
              ? `你今天的照片 AI 批改 ${CLIENT_PHOTO_DAILY} 次已用完，明天再試。`
              : `你今天的文字 AI 批改 ${CLIENT_TEXT_DAILY} 次已用完，明天再試。`)
            : "今天全平台的免費 AI 額度已用完，題庫、錯題與申論骨架仍可正常使用。";

          return json(
            { error: { message: msg, code: q.scope === "client" ? "CLIENT_DAILY_QUOTA" : "GLOBAL_DAILY_QUOTA" } },
            429,
            { "Retry-After": String(secondsUntilTaipeiMidnight()) }
          );
        }
        quotaReserved = true;
      } catch {
        return json(
          { error: { message: "AI 額度服務暫時無法使用，請稍後再試。", code: "QUOTA_SERVICE_UNAVAILABLE" } },
          503
        );
      }
    }

    const maxTokensRequested = Number(body.max_tokens) || 1000;
    const publicMaxTokens = quotaKind === "photo" ? 1100 : 800;
    const maxTokens = isInternal
      ? Math.min(Math.max(maxTokensRequested, 100), 1600)
      : Math.min(Math.max(maxTokensRequested, 100), publicMaxTokens);

    const requestedTemperature = typeof body.temperature === "number" && Number.isFinite(body.temperature)
      ? body.temperature
      : 0.4;
    const safePayload = {
      // Cached pre-migration clients may still request Qwen 3.6; never forward the retired model upstream.
      model: isInternal ? body.model : PUBLIC_MODEL,
      messages: body.messages,
      reasoning_effort: isInternal && ["none", "low", "medium", "high"].includes(body.reasoning_effort)
        ? body.reasoning_effort
        : "none",
      temperature: Math.min(
        Math.max(requestedTemperature, 0),
        isInternal ? 1 : 0.7
      ),
      max_tokens: maxTokens
    };

    try {
      const resp = await fetch(
        "https://api.groq.com/openai/v1/chat/completions",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${env.GROQ_KEY}`
          },
          body: JSON.stringify(safePayload)
        }
      );

      if (!resp.ok) {
        if (quotaReserved) {
          await refundPublicQuota(
            env.AI_QUOTA_DB,
            taipeiDate(),
            clientKey,
            quotaKind
          ).catch(() => {});
        }

        if (resp.status === 429) {
          return json(
            { error: { message: "AI 免費額度目前較忙碌，請稍後再試。", code: "UPSTREAM_RATE_LIMIT" } },
            429,
            { "Retry-After": resp.headers.get("retry-after") || "60" }
          );
        }

        return json(
          { error: { message: "AI service temporarily unavailable" } },
          502
        );
      }

      const result = await resp.text();
      return new Response(result, {
        status: 200,
        headers: {
          ...corsHeaders(),
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-store"
        }
      });
    } catch {
      if (quotaReserved) {
        await refundPublicQuota(
          env.AI_QUOTA_DB,
          taipeiDate(),
          clientKey,
          quotaKind
        ).catch(() => {});
      }

      return json(
        { error: { message: "AI service temporarily unavailable" } },
        502
      );
    }
  }
};

async function safeSecretEqual(a, b) {
  if (!a || !b) return false;
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(a)),
    crypto.subtle.digest("SHA-256", enc.encode(b))
  ]);
  const aa = new Uint8Array(ha);
  const bb = new Uint8Array(hb);
  let diff = 0;
  for (let i = 0; i < aa.length; i++) diff |= aa[i] ^ bb[i];
  return diff === 0;
}

async function sha256Short(value) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value)
  );
  return Array.from(new Uint8Array(digest))
    .slice(0, 16)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function taipeiDate() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(new Date());
  const obj = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${obj.year}-${obj.month}-${obj.day}`;
}

function secondsUntilTaipeiMidnight() {
  const now = new Date();
  const taipeiNow = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  const nextUtc = Date.UTC(
    taipeiNow.getUTCFullYear(),
    taipeiNow.getUTCMonth(),
    taipeiNow.getUTCDate() + 1,
    0, 0, 0
  ) - 8 * 60 * 60 * 1000;
  return Math.max(1, Math.ceil((nextUtc - now.getTime()) / 1000));
}

function changed(result) {
  return Number(result?.meta?.changes || result?.meta?.rows_written || 0) > 0;
}

async function isGlobalQuotaFull(db, date, kind, limits) {
  const row = await db.prepare(`
    SELECT text_count, photo_count
    FROM ai_daily_global_usage
    WHERE usage_date = ?
    LIMIT 1
  `).bind(date).first();

  if (!row) return false;
  if (kind === "photo") {
    return Number(row.photo_count || 0) >= Number(limits.globalPhoto || 0);
  }
  return Number(row.text_count || 0) >= Number(limits.globalText || 0);
}

async function reservePublicQuota(db, date, clientKey, kind, limits) {
  const textInc = kind === "text" ? 1 : 0;
  const photoInc = kind === "photo" ? 1 : 0;

  const clientResult = await db.prepare(`
    INSERT INTO ai_daily_client_usage
      (usage_date, client_key, text_count, photo_count, updated_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(usage_date, client_key) DO UPDATE SET
      text_count = text_count + excluded.text_count,
      photo_count = photo_count + excluded.photo_count,
      updated_at = CURRENT_TIMESTAMP
    WHERE
      (excluded.text_count = 0 OR text_count < ?)
      AND (excluded.photo_count = 0 OR photo_count < ?)
  `).bind(
    date,
    clientKey,
    textInc,
    photoInc,
    limits.clientText,
    limits.clientPhoto
  ).run();

  if (!changed(clientResult)) {
    return { ok: false, scope: "client" };
  }

  try {
    const globalResult = await db.prepare(`
      INSERT INTO ai_daily_global_usage
        (usage_date, text_count, photo_count, updated_at)
      VALUES (?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(usage_date) DO UPDATE SET
        text_count = text_count + excluded.text_count,
        photo_count = photo_count + excluded.photo_count,
        updated_at = CURRENT_TIMESTAMP
      WHERE
        (excluded.text_count = 0 OR text_count < ?)
        AND (excluded.photo_count = 0 OR photo_count < ?)
    `).bind(
      date,
      textInc,
      photoInc,
      limits.globalText,
      limits.globalPhoto
    ).run();

    if (!changed(globalResult)) {
      await refundClientQuota(db, date, clientKey, kind);
      return { ok: false, scope: "global" };
    }
  } catch (err) {
    await refundClientQuota(db, date, clientKey, kind).catch(() => {});
    throw err;
  }

  return { ok: true };
}

async function refundClientQuota(db, date, clientKey, kind) {
  const textDec = kind === "text" ? 1 : 0;
  const photoDec = kind === "photo" ? 1 : 0;
  await db.prepare(`
    UPDATE ai_daily_client_usage
    SET
      text_count = MAX(text_count - ?, 0),
      photo_count = MAX(photo_count - ?, 0),
      updated_at = CURRENT_TIMESTAMP
    WHERE usage_date = ? AND client_key = ?
  `).bind(textDec, photoDec, date, clientKey).run();
}

async function refundPublicQuota(db, date, clientKey, kind) {
  const textDec = kind === "text" ? 1 : 0;
  const photoDec = kind === "photo" ? 1 : 0;
  await db.batch([
    db.prepare(`
      UPDATE ai_daily_client_usage
      SET
        text_count = MAX(text_count - ?, 0),
        photo_count = MAX(photo_count - ?, 0),
        updated_at = CURRENT_TIMESTAMP
      WHERE usage_date = ? AND client_key = ?
    `).bind(textDec, photoDec, date, clientKey),
    db.prepare(`
      UPDATE ai_daily_global_usage
      SET
        text_count = MAX(text_count - ?, 0),
        photo_count = MAX(photo_count - ?, 0),
        updated_at = CURRENT_TIMESTAMP
      WHERE usage_date = ?
    `).bind(textDec, photoDec, date)
  ]);
}

// Public schedule metadata only. Never calls AI, Supabase, or write-capable GitHub APIs.
const HEARTBEAT_TASKS = [{"id":"public-monitoring-feed","workflow_file":"public-monitoring-feed.yml","max_age_hours":8,"accepted_events":["schedule"]},{"id":"public-uptime","workflow_file":"public-uptime.yml","max_age_hours":30,"accepted_events":["schedule"]},{"id":"backup-uptime","workflow_file":"backup-uptime.yml","max_age_hours":30,"accepted_events":["schedule"]},{"id":"moex-social-worker-sync","workflow_file":"moex-social-worker-sync.yml","max_age_hours":192,"accepted_events":["schedule"]},{"id":"full-corpus-question-qa","workflow_file":"full-corpus-qa.yml","max_age_hours":840,"accepted_events":["schedule"]},{"id":"official-pdf-batch-pipeline","workflow_file":"official-pdf-batch-pipeline.yml","max_age_hours":36,"accepted_events":["schedule"]}];
const HEARTBEAT_SCHEMA = `CREATE TABLE IF NOT EXISTS ops_task_heartbeat (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  scheduled_at TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  payload TEXT NOT NULL
)`;
const HEARTBEAT_SAVE = `INSERT INTO ops_task_heartbeat (id, scheduled_at, observed_at, payload)
VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
scheduled_at=excluded.scheduled_at, observed_at=excluded.observed_at, payload=excluded.payload
WHERE excluded.scheduled_at > ops_task_heartbeat.scheduled_at`;

function heartbeatTask(task, runs, now) {
  const base = {id:task.id, workflow_file:task.workflow_file, max_age_hours:task.max_age_hours};
  if (!Array.isArray(runs)) return {...base,status:'error',failure_class:'invalid_response'};
  // A manual recovery or PR must never erase a failed scheduled run.
  const accepted = runs.filter(r=>r.event==='schedule' && r.head_branch==='main' &&
    r.status==='completed' && r.head_repository?.full_name==='grizzly020503/swsi-quiz-backup');
  accepted.sort((a,b)=>String(b.run_started_at||b.created_at||'').localeCompare(String(a.run_started_at||a.created_at||'')));
  if (!accepted.length) return {...base,status:'missing',failure_class:'no_scheduled_evidence'};
  const run=accepted[0], stamp=Date.parse(run.run_started_at||run.created_at);
  if (!Number.isFinite(stamp) || stamp>now+300000)
    return {...base,status:'error',failure_class:'invalid_run_timestamp'};
  const age=Math.max(0,(now-stamp)/3600000);
  const status=run.conclusion!=='success'?'failed':age>task.max_age_hours?'stale':'healthy';
  return {...base,status,run_id:run.id,last_run_at:new Date(stamp).toISOString(),
    age_hours:Math.round(age*100)/100,failure_class:status==='healthy'?'none':status};
}

async function heartbeatRuns(task) {
  const url='https://api.github.com/repos/grizzly020503/swsi-quiz-backup/actions/workflows/'+
    encodeURIComponent(task.workflow_file)+'/runs?event=schedule&branch=main&status=completed&per_page=10';
  const response=await fetch(url,{method:'GET',redirect:'error',signal:AbortSignal.timeout(10000),
    headers:{'User-Agent':'swsi-cloudflare-task-heartbeat','Accept':'application/vnd.github+json'}});
  if (!response.ok) throw Error('github_http_'+response.status);
  if (Number(response.headers.get('content-length')||0)>1000000) throw Error('response_too_large');
  const reader=response.body.getReader();let bytes=0;const chunks=[];
  try {
    for (;;) {const {done,value}=await reader.read();if(done)break;bytes+=value.byteLength;
      if(bytes>1000000) throw Error('response_too_large');chunks.push(value);}
  } finally {await reader.cancel().catch(()=>{});}
  const buffer=new Uint8Array(bytes);let offset=0;for(const c of chunks){buffer.set(c,offset);offset+=c.byteLength;}
  const data=JSON.parse(new TextDecoder().decode(buffer));
  if (!Array.isArray(data.workflow_runs)) throw Error('invalid_response');
  return data.workflow_runs;
}

async function runTaskHeartbeat(env, scheduledTime) {
  const now=Date.now();
  if (!Number.isFinite(scheduledTime)||scheduledTime>now+300000) throw Error('invalid_schedule');
  const observed=new Date(now).toISOString(), scheduled=new Date(scheduledTime).toISOString();
  const tasks=await Promise.all(HEARTBEAT_TASKS.map(async task=>{
    try {return heartbeatTask(task,await heartbeatRuns(task),now);}
    catch (error) {
      // Publish only bounded classifications; URLs, upstream bodies and secrets never leave this handler.
      const message=String(error?.message||'');
      const failure=/^github_http_\d{3}$/.test(message)?message:
        ['response_too_large','invalid_response'].includes(message)?message:'source_unavailable';
      return {id:task.id,workflow_file:task.workflow_file,max_age_hours:task.max_age_hours,status:'error',failure_class:failure};
    }
  }));
  const unhealthy=tasks.filter(t=>t.status!=='healthy');
  const components={};
  for (const component of ['site','data_freshness','grading','ai','review_backlog']) {
    components[component]={status:'unknown',checked_at:observed,scope:component,
      failure_class:'not_probed',detail:{note:'This observer verifies scheduled tasks only.'}};
  }
  components.task_heartbeat={status:unhealthy.length?'failed':'healthy',checked_at:observed,
    scope:'github-main-schedules',failure_class:unhealthy.length?'scheduled_task_attention':'none',
    detail:{tasks_checked:tasks.length,attention:unhealthy.length}};
  const payload={schema_version:1,producer:'cloudflare-cron',generated_at:observed,
    scheduled_at:scheduled,independent_of:'github-actions',components,tasks};
  await env.AI_QUOTA_DB.prepare(HEARTBEAT_SCHEMA).run();
  await env.AI_QUOTA_DB.prepare(HEARTBEAT_SAVE).bind(scheduled,observed,JSON.stringify(payload)).run();
}

async function readTaskHeartbeat(request, env) {
  const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
    'X-Content-Type-Options':'nosniff'};
  const reply=(data,status)=>new Response(JSON.stringify(data),{status,headers});
  if (request.method!=='GET') return new Response(null,{status:405,headers:{...headers,Allow:'GET'}});
  try {
    // GET never creates tables, triggers probes, writes state, or accepts caller-provided URLs.
    const row=await env.AI_QUOTA_DB.prepare('SELECT payload FROM ops_task_heartbeat WHERE id=1').first();
    if (!row) return reply({status:'awaiting_first_schedule',independent_monitoring_active:false},503);
    const data=JSON.parse(row.payload), age=(Date.now()-Date.parse(data.generated_at))/60000;
    const valid=data.producer==='cloudflare-cron' && data.schema_version===1 &&
      Array.isArray(data.tasks) && data.tasks.length===HEARTBEAT_TASKS.length;
    if(!valid) throw Error('invalid_stored_observation');
    const fresh=Number.isFinite(age)&&age>=-5&&age<=45;
    return reply({...data,observer_status:fresh?'fresh':'stale',independent_monitoring_active:fresh},fresh?200:503);
  } catch {
    return reply({status:'observation_unavailable',independent_monitoring_active:false},503);
  }
}
