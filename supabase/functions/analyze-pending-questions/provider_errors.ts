// Which AI proxy failures are the provider's fault rather than the question's.
//
// A question only loses an attempt (and is parked for review after three) when
// the model answered but the answer failed validation. When the model itself is
// gone (retired, renamed, not allowlisted in the Worker) the other internal
// model takes over; when the provider or proxy is down the question simply
// stays pending and the next scheduled run retries it. The pipeline watchdog
// reports a queue that stops moving.

export type ProviderFailure = "model_unavailable" | "provider_down" | null;

const MODEL_GONE =
  /invalid (internal |ai )?model|model[_ ]not[_ ]found|model_decommissioned|decommissioned|does not exist|no longer (supported|available)|not supported for this model|unknown model/i;

export function providerFailure(status: number, body: string): ProviderFailure {
  if (status === 404 || status === 405 || status === 410) return "model_unavailable";
  if (MODEL_GONE.test(body || "")) return "model_unavailable";
  if (status === 401 || status === 403 || status === 408 || status === 425 || status === 429 || status >= 500) {
    return "provider_down";
  }
  return null;
}

export const MODEL_UNAVAILABLE = "model unavailable";
export const PROVIDER_UNAVAILABLE = "provider unavailable";

// Errors that must not cost the question an attempt.
export function isTransient(msg: string): boolean {
  return /HTTP 429|rate limit|fetch failed|network|timed?\s*out|temporar|provider unavailable|model unavailable/i.test(msg);
}
