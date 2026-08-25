export default {
  async fetch(request, env) {
    const PUBLIC_ORIGINS = new Set([
      "https://swsi-quiznetlify.netlify.app"
    ]);

    const PUBLIC_MODEL = "qwen/qwen3.6-27b";
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
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }
      );
    }

    // 瀏覽器 CORS preflight 只對公開來源開放。
    if (request.method === "OPTIONS") {
      if (!isPublic) return new Response(null, { status: 403 });
      return new Response(null, {
        status: 204,
        headers: corsHeaders()
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
          { error: { message: "操作太快了，請等一分鐘再使用 AI 批改。" } },
          429,
          { "Retry-After": "60" }
        );
      }

      const ipLimit = await env.AI_IP_LIMIT.limit({ key: ip });
      if (!ipLimit.success) {
        return json(
          { error: { message: "目前這個網路的 AI 使用量太高，請稍後再試。" } },
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
    } else if (body.model !== PUBLIC_MODEL) {
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

    // Qwen 3.6 官方模型限制採保守值：最多 3 張輸入圖片。
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
            429
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
            429
          );
        }
        quotaReserved = true;
      } catch {
        return json(
          { error: { message: "AI 額度服務暫時無法使用，請稍後再試。" } },
          503
        );
      }
    }

    const maxTokensRequested = Number(body.max_tokens) || 1000;
    const publicMaxTokens = quotaKind === "photo" ? 1100 : 800;
    const maxTokens = isInternal
      ? Math.min(Math.max(maxTokensRequested, 100), 1600)
      : Math.min(Math.max(maxTokensRequested, 100), publicMaxTokens);

    const safePayload = {
      model: body.model,
      messages: body.messages,
      reasoning_effort: isInternal && ["none", "low", "medium", "high"].includes(body.reasoning_effort)
        ? body.reasoning_effort
        : "none",
      temperature: Math.min(
        Math.max(Number(body.temperature) || 0.4, 0),
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
            { error: { message: "AI 免費額度目前較忙碌，請稍後再試。" } },
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
          "Content-Type": "application/json; charset=utf-8"
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