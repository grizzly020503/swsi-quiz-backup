import { isTransient, providerFailure } from "./provider_errors.ts";

function eq(actual: unknown, expected: unknown, label: string) {
  if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

Deno.test("retired or unknown models are the provider's fault", () => {
  eq(providerFailure(405, ""), "model_unavailable", "HTTP 405 (qwen3.6 retirement)");
  eq(providerFailure(404, "{}"), "model_unavailable", "HTTP 404");
  eq(providerFailure(410, ""), "model_unavailable", "HTTP 410");
  eq(providerFailure(400, '{"error":{"message":"Invalid internal model"}}'), "model_unavailable", "Worker allowlist");
  eq(providerFailure(400, '{"error":{"code":"model_decommissioned"}}'), "model_unavailable", "Groq decommissioned");
  eq(providerFailure(400, "The model `x` does not exist"), "model_unavailable", "does not exist");
});

Deno.test("outages and auth problems keep the question pending", () => {
  for (const s of [500, 502, 503, 504, 520, 524, 408, 425, 429, 401, 403]) {
    eq(providerFailure(s, "upstream error"), "provider_down", `HTTP ${s}`);
  }
});

Deno.test("a real bad request still counts against the question", () => {
  eq(providerFailure(400, '{"error":{"message":"context length exceeded"}}'), null, "HTTP 400 other");
  eq(providerFailure(422, "unprocessable"), null, "HTTP 422");
});

Deno.test("which errors cost an attempt", () => {
  eq(isTransient("AI qwen/qwen3.8-27b model unavailable HTTP 405"), true, "model unavailable");
  eq(isTransient("AI provider unavailable HTTP 503"), true, "provider unavailable");
  eq(isTransient("AI openai/gpt-oss-120b HTTP 429: slow down"), true, "rate limit");
  eq(isTransient("新增題面沒有的數字: 3"), false, "validation failure");
  eq(isTransient("AI openai/gpt-oss-120b HTTP 400: context length exceeded"), false, "bad request");
  eq(isTransient("AI 最終驗證失敗"), false, "final validation");
});
