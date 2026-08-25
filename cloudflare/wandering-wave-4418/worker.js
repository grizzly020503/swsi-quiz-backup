export default {
  async fetch(request, env) {
    const ALLOWED_ORIGINS = new Set([
      "https://swsi-quiznetlify.netlify.app"
    ]);

    const ALLOWED_MODEL = "qwen/qwen3.6-27b";
    const origin = request.headers.get("Origin") || "";

    function corsHeaders() {
      return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
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

    // 只允許正式 SWSI 網站的瀏覽器請求
    if (!ALLOWED_ORIGINS.has(origin)) {
      return new Response(
        JSON.stringify({ error: { message: "Forbidden origin" } }),
        {
          status: 403,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }
      );
    }

    // CORS preflight
    if (request.method === "OPTIONS") {
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

    // -------- 防暴衝 --------

    const ip =
      request.headers.get("CF-Connecting-IP") ||
      "unknown";

    const ua =
      request.headers.get("User-Agent") ||
      "unknown";

    // 用 IP + User-Agent 做「軟裝置識別」
    const rawClientKey = `${ip}|${ua}`;

    const digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(rawClientKey)
    );

    const clientKey = Array.from(
      new Uint8Array(digest)
    )
      .slice(0, 12)
      .map(b => b.toString(16).padStart(2, "0"))
      .join("");

    // 第一層：同一瀏覽器特徵每分鐘 3 次
    const clientLimit = await env.AI_RATE_LIMIT.limit({
      key: clientKey
    });

    if (!clientLimit.success) {
      return json(
        {
          error: {
            message: "操作太快了，請等一分鐘再使用 AI 批改。"
          }
        },
        429,
        { "Retry-After": "60" }
      );
    }

    // 第二層：同一 IP 每分鐘最多 30 次
    // 避免機器人大量轟炸，但不把 IP 當主要使用者識別
    const ipLimit = await env.AI_IP_LIMIT.limit({
      key: ip
    });

    if (!ipLimit.success) {
      return json(
        {
          error: {
            message: "目前這個網路的 AI 使用量太高，請稍後再試。"
          }
        },
        429,
        { "Retry-After": "60" }
      );
    }

    // -------- 請求大小限制 --------

    let raw;

    try {
      raw = await request.text();
    } catch {
      return json(
        { error: { message: "Invalid request body" } },
        400
      );
    }

    // 約 4 MB。
    // 足夠目前 1–4 張經前端壓縮的申論照片，
    // 又避免有人直接塞超大型 payload。
    if (
      new TextEncoder().encode(raw).byteLength >
      4_000_000
    ) {
      return json(
        { error: { message: "Request too large" } },
        413
      );
    }

    let body;

    try {
      body = JSON.parse(raw);
    } catch {
      return json(
        { error: { message: "Invalid JSON" } },
        400
      );
    }

    // -------- 限制 AI 使用方式 --------

    if (
      !body ||
      body.model !== ALLOWED_MODEL ||
      !Array.isArray(body.messages) ||
      body.messages.length < 1 ||
      body.messages.length > 3
    ) {
      return json(
        { error: { message: "Invalid AI request" } },
        400
      );
    }

    let imageCount = 0;

    for (const message of body.messages) {
      if (
        !message ||
        !["user", "system"].includes(message.role)
      ) {
        return json(
          { error: { message: "Invalid message" } },
          400
        );
      }

      if (Array.isArray(message.content)) {
        for (const item of message.content) {
          if (item?.type === "image_url") {
            imageCount++;
          }
        }
      }
    }

    // 目前網站本身最多使用 4 張照片
    if (imageCount > 4) {
      return json(
        {
          error: {
            message: "最多一次上傳 4 張照片。"
          }
        },
        400
      );
    }

    // 不讓外部呼叫者自行要求巨量 token、
    // 更換模型或調高生成成本。
    const safePayload = {
      model: ALLOWED_MODEL,
      messages: body.messages,
      reasoning_effort: "none",
      temperature: Math.min(
        Math.max(Number(body.temperature) || 0.4, 0),
        0.7
      ),
      max_tokens: Math.min(
        Math.max(Number(body.max_tokens) || 1000, 100),
        1200
      )
    };

    // -------- 呼叫 Groq --------

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

      // Groq 額度滿了，保留 429 給前端辨識
      if (resp.status === 429) {
        return json(
          {
            error: {
              message:
                "今日 AI 免費額度較忙碌，請稍後再試。"
            }
          },
          429,
          { "Retry-After": "60" }
        );
      }

      if (!resp.ok) {
        return json(
          {
            error: {
              message: "AI service temporarily unavailable"
            }
          },
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

    } catch (err) {
      return json(
        {
          error: {
            message: "AI service temporarily unavailable"
          }
        },
        502
      );
    }
  }
};
