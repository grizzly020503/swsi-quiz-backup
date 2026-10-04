import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { evaluateCurrentLegalTrust, type CurrentLegalTrustDecision } from "./current_legal_trust.ts";
import {
  canonicalExamCode,
  evaluateHistoricalLawTrust,
  historicalReasonIsOperationalRetry,
  type HistoricalLawTrustDecision,
} from "./historical_law_trust.ts";
import {
  canonicalLegalNames,
  finalizeValidatedCandidate,
  hasLegalRiskSignal,
  preflightQuestion,
} from "./enrichment_route.ts";

const AI_PROXY_URL = "https://wandering-wave-4418.c022050333.workers.dev/api/ai";
const DRAFT_MODEL = "qwen/qwen3.8-27b";
const AUDIT_MODEL = "openai/gpt-oss-120b";
const FORMAT_ARTIFACT_TOKENS = new Set(["na", "nb", "nc", "nd"]);
const MISTAKES = new Set(["概念混淆", "法規混淆", "理論人物混淆", "流程順序錯誤", "計算邏輯錯誤", "關鍵字漏看", "題幹誤讀"]);
const MAJORS: Record<string, string[]> = {
  "人類行為與社會環境": ["各年齡發展", "家庭與社會", "發展理論", "社區與文化", "社會環境系統", "心理健康與偏差", "人格與情緒", "危機與壓力", "生理與遺傳", "社會化與社會角色", "認知與語言", "團體與組織"],
  "社會工作": ["社會工作專業", "社會工作倫理", "社會工作理論", "處遇模式", "工作技巧", "兒少服務", "心理健康", "老人服務", "障礙者服務", "性別與婦女服務", "多元文化能力", "社區工作", "社工管理"],
  "社會工作直接服務": ["社區工作", "團體工作", "處遇模式與理論", "評估與處遇計畫", "社會工作倫理", "個案工作", "會談與溝通技巧", "專業關係", "紀錄與評鑑", "社工角色", "結案與追蹤", "個案管理"],
  "社會工作研究方法": ["資料蒐集", "質性方法", "研究邏輯", "抽樣", "研究設計", "測量", "統計檢定", "信效度", "研究方法類型", "研究倫理", "變項", "因果關係", "資料分析", "內容分析", "方案評估", "縱貫研究", "研究典範", "推論謬誤", "文獻回顧"],
  "社會政策與社會立法": ["其他社會立法與人權公約", "社會政策概念與原則", "兒少福利法規", "社會保險", "身心障礙福利法規", "福利意識形態與理論", "社會救助", "老人福利法規", "社會政策過程與決策", "婦女與性別法規", "社會津貼與福利服務", "福利國家與體制"]
};
const FIELDS = ["id", "major", "topic", "keywords", "exp_why", "exp_others", "exp_trap", "mnemonic", "extension", "law", "mistake"];
const TEXT_FIELDS = ["topic", "keywords", "exp_why", "exp_others", "exp_trap", "mnemonic", "extension", "law"];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });
}
function clean(v: unknown) { return String(v ?? "").trim(); }
function delay(ms: number) { return new Promise((r) => setTimeout(r, ms)); }
function officialAnswers(q: any) {
  const multi = Array.isArray(q?.accepted_answers)
    ? q.accepted_answers.map((x: unknown) => clean(x).toUpperCase()).filter((x: string) => ["A", "B", "C", "D"].includes(x))
    : [];
  if (multi.length) return [...new Set(multi)];
  const single = clean(q?.answer);
  return single ? [single] : [];
}
function task(q: any) {
  return { id: q.id, subject: q.subject, question: q.question, A: q.opt_a, B: q.opt_b, C: q.opt_c, D: q.opt_d, official_answers: officialAnswers(q) };
}
function stripJsonFence(text: string) {
  let s = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  if (s.startsWith("[") && s.endsWith("]")) return s;
  const a = s.indexOf("["), b = s.lastIndexOf("]");
  if (a >= 0 && b > a) return s.slice(a, b + 1);
  throw new Error("AI 回傳找不到 JSON array");
}
function initialPrompt(q: any) {
  return `你是台灣社會工作師國家考試選擇題解析器。官方可接受答案已確定，可能有一個或多個。\n硬性規則：\n1. 不可修改或質疑官方題目、選項、答案，只寫解析。\n2. major 只能從：${JSON.stringify(MAJORS[q.subject] || [])}\n3. mistake 只能從：${JSON.stringify([...MISTAKES])}\n4. topic 用「主題 > 細目」；keywords 用半形逗號分隔。\n5. exp_why 必須說明所有 official_answers 為什麼都可接受；exp_others 只說明不在 official_answers 裡的選項錯在哪；不得把 official_answers 中任何一個寫成錯誤。\n6. 正解理由優先只用題幹/選項已提供的核心特徵。禁止新增題面未出現的人名、機構名、英文專名/縮寫、任何阿拉伯數字、年齡、年份、金額、天數、比例或法條號碼。\n7. 若錯誤選項是數值/期限/比例錯誤，而題面沒有提供正確數值，只說「與正確規定不符」，不要自行補正確數字。\n8. mnemonic 短而可記；extension 只寫相鄰考點名稱/比較方向，不補背景故事。\n9. law 只寫確定的法規名稱/原則；非法律題可空白。\n10. 繁體中文、簡潔。只輸出 JSON array；物件只能有 ${JSON.stringify(FIELDS)}。\n題目：${JSON.stringify(task(q))}`;
}
function auditPrompt(q: any, draft: any) {
  return `你是社會工作師國考題庫最終審稿員。官方可接受答案固定不可改，可能有一個或多個。直接輸出校正後 JSON array。\n1. exp_why 必須支持全部 official_answers；優先使用題面已有的判斷特徵，不新增發展年齡、形成時點或額外背景。\n2. exp_others 只能指出不在 official_answers 裡的選項錯誤；不得把 official_answers 中任何一個判成錯誤，也不可先說錯、後面又把同一敘述當真。\n3. 刪除不必要的人物、機構、年代、英文名稱、背景故事、條號與數值。\n4. 禁止新增題面沒有的人名、機構名、英文專名/縮寫、任何阿拉伯數字、年齡、年份、金額、天數、比例或法條號碼。若草稿有，一律刪除。\n5. 輸出前逐欄掃描 A-Z/a-z；任何沒有逐字出現在官方題面或選項中的英文字，一律改成已有的中文概念或直接刪除，不得附英文翻譯。\n6. 數值型錯誤若題面沒有正確數值，只說與正確規定/概念不符，不補數字。\n7. major 只能從 ${JSON.stringify(MAJORS[q.subject] || [])}；mistake 只能從 ${JSON.stringify([...MISTAKES])}。\n8. extension 只寫考點名稱/比較方向；law 不確定就空白。\n9. 只輸出 JSON array；物件只能有 ${JSON.stringify(FIELDS)}。\n官方題目：${JSON.stringify(task(q))}\n草稿：${JSON.stringify(draft)}`;
}
async function callModel(model: string, prompt: string, reasoning: string, maxTokens: number, internalKey: string) {
  const body: any = { model, temperature: 0, max_tokens: maxTokens, messages: [{ role: "user", content: prompt }] };
  if (reasoning) body.reasoning_effort = reasoning;
  let last = "", formatRetries = 0;
  for (let attempt = 0; attempt < 4; attempt++) {
    const r = await fetch(AI_PROXY_URL, { method: "POST", headers: { "content-type": "application/json", "X-SWSI-Internal-Key": internalKey }, body: JSON.stringify(body) });
    const text = await r.text();
    if (r.status === 429) {
      last = `AI ${model} HTTP 429: ${text.slice(0, 300)}`;
      const hs = Number(r.headers.get("retry-after") || 0), m = text.match(/try again in\s+([0-9.]+)s/i), ms = m ? Number(m[1]) : 0;
      const w = Math.max(5, Math.min(35, hs || ms || 8));
      if (attempt < 3) { await delay((w + 1) * 1000); continue; }
      throw new Error(last);
    }
    if (!r.ok) throw new Error(`AI ${model} HTTP ${r.status}: ${text.slice(0, 300)}`);
    const data: any = JSON.parse(text), content = data?.choices?.[0]?.message?.content;
    if (typeof content !== "string") throw new Error(`AI ${model} response shape invalid`);
    try {
      return JSON.parse(stripJsonFence(content));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      last = `AI ${model} format: ${msg}`;
      if (formatRetries < 1 && attempt < 3) {
        formatRetries += 1;
        await delay(250);
        continue;
      }
      throw new Error(last);
    }
  }
  throw new Error(last || `AI ${model} failed`);
}
function asciiTokens(s: string) { return new Set((s.match(/[A-Za-z][A-Za-z0-9'’-]*/g) || []).map((x) => x.toLowerCase())); }
function numberTokens(s: string) { return new Set(s.match(/\d+(?:[.,]\d+)?/g) || []); }
function setDiff(a: Set<string>, b: Set<string>) { return [...a].filter((x) => !b.has(x)); }
function sourceText(q: any) {
  return `A B C D ${clean(q.question)} ${clean(q.opt_a)} ${clean(q.opt_b)} ${clean(q.opt_c)} ${clean(q.opt_d)} ${officialAnswers(q).join(" ")}`;
}
function removeUnapprovedAscii(value: unknown, allowed: Set<string>) {
  let s = clean(value);
  s = s.replace(/[A-Za-z][A-Za-z0-9'’-]*/g, (m) => {
    const t = m.toLowerCase();
    return allowed.has(t) || FORMAT_ARTIFACT_TOKENS.has(t) ? m : "";
  });
  s = s.replace(/[（(]\s*[\/,+\-–—:;]*\s*[）)]/g, "");
  s = s.replace(/\s*[,，]\s*[,，]+/g, "，");
  s = s.replace(/\s+([，。；：、])/g, "$1").replace(/[ \t]{2,}/g, " ").trim();
  return s;
}
function sanitizeUnapprovedAscii(q: any, row: any) {
  const allowed = asciiTokens(sourceText(q));
  const out: any = { ...row };
  for (const k of TEXT_FIELDS) out[k] = removeUnapprovedAscii(out[k], allowed);
  return out;
}
function validateFinal(q: any, rows: any) {
  if (!Array.isArray(rows) || rows.length !== 1) throw new Error("AI 最終筆數不是 1");
  let row = rows[0];
  if (!row || typeof row !== "object" || Array.isArray(row)) throw new Error("AI 最終格式不是 object");
  const keys = Object.keys(row).sort(), expected = [...FIELDS].sort();
  if (JSON.stringify(keys) !== JSON.stringify(expected)) throw new Error(`AI 欄位不符: ${keys.join(',')}`);
  if (clean(row.id) !== clean(q.id)) throw new Error("AI id 不符");
  row = sanitizeUnapprovedAscii(q, row);
  if (!(MAJORS[q.subject] || []).includes(clean(row.major))) throw new Error(`major 不在既有分類: ${row.major}`);
  if (!MISTAKES.has(clean(row.mistake))) throw new Error(`mistake 不在既有分類: ${row.mistake}`);
  for (const k of FIELDS) if (k !== "law" && !clean(row[k])) throw new Error(`${k} 空白`);
  const source = sourceText(q), output = FIELDS.filter((k) => k !== "id").map((k) => clean(row[k])).join(" ");
  const extraAscii = setDiff(asciiTokens(output), asciiTokens(source)).filter((x) => !FORMAT_ARTIFACT_TOKENS.has(x));
  if (extraAscii.length) throw new Error(`新增題面沒有的英文詞: ${extraAscii.join(',')}`);
  const extraNums = setDiff(numberTokens(output), numberTokens(source));
  if (extraNums.length) throw new Error(`新增題面沒有的數字: ${extraNums.join(',')}`);
  return {
    major: clean(row.major), topic: clean(row.topic), keywords: clean(row.keywords), exp_why: clean(row.exp_why), exp_others: clean(row.exp_others), exp_trap: clean(row.exp_trap), exp_raw: null,
    mnemonic: clean(row.mnemonic), extension: clean(row.extension), law: clean(row.law), mistake: clean(row.mistake), analysis_status: "ready", analysis_attempts: 0, analysis_error: null, analysis_started_at: null
  };
}
function auditRepairPrompt(q: any, draft: any, failure: string) {
  return `${auditPrompt(q, draft)}\n上一版未通過結構驗證：${failure}\n請只修正這個問題與必要連帶欄位，仍須遵守全部原規則，重新輸出完整 JSON array。`;
}
async function analyzeOne(q: any, internalKey: string) {
  const draftRows = await callModel(DRAFT_MODEL, initialPrompt(q), "none", 1400, internalKey);
  if (!Array.isArray(draftRows) || draftRows.length !== 1) throw new Error("草稿格式異常");
  let prompt = auditPrompt(q, draftRows[0]), lastValidation = "";
  for (let auditAttempt = 0; auditAttempt < 2; auditAttempt++) {
    const finalRows = await callModel(AUDIT_MODEL, prompt, "medium", 1500, internalKey);
    try {
      return validateFinal(q, finalRows);
    } catch (e) {
      lastValidation = e instanceof Error ? e.message : String(e);
      if (auditAttempt === 0) {
        prompt = auditRepairPrompt(q, draftRows[0], lastValidation);
        continue;
      }
      throw e;
    }
  }
  throw new Error(lastValidation || "AI 最終驗證失敗");
}
function isTransient(msg: string) { return /HTTP 429|rate limit|fetch failed|network|timed?\s*out|temporar/i.test(msg); }

async function updateClaimedQuestion(sb: any, q: any, patch: Record<string, unknown>) {
  let updateQuery: any = sb.from("questions").update(patch).eq("id", q.id);
  updateQuery = q.source_exam_code == null
    ? updateQuery.is("source_exam_code", null)
    : updateQuery.eq("source_exam_code", q.source_exam_code);
  const { data: updated, error } = await updateQuery.select("id").maybeSingle();
  if (error) throw new Error(`update: ${error.message}`);
  if (!updated?.id) throw new Error("update: target row not found");
}

async function loadCurrentLegalTrust(
  sb: any,
  q: any,
): Promise<{ decision: CurrentLegalTrustDecision | null; queryError: string | null }> {
  const names = canonicalLegalNames(q);
  if (!hasLegalRiskSignal(q) || !names.length) return { decision: null, queryError: null };

  const { data: run, error: runError } = await sb
    .from("legal_watch_run_health")
    .select("schema_version,checked_at,baseline,lookup_error_count,sync_status,source")
    .eq("id", true)
    .maybeSingle();
  if (runError) return { decision: null, queryError: `run_health_query:${runError.message}` };

  const { data: registryRows, error: registryError } = await sb
    .from("legal_reference_registry")
    .select("canonical_name,watch_status,last_checked_at")
    .in("canonical_name", names);
  if (registryError) return { decision: null, queryError: `registry_query:${registryError.message}` };

  return {
    decision: evaluateCurrentLegalTrust(names, run, registryRows || []),
    queryError: null,
  };
}

async function loadHistoricalLegalTrust(
  sb: any,
  q: any,
): Promise<{ decision: HistoricalLawTrustDecision; queryError: string | null }> {
  const names = canonicalLegalNames(q);
  const examCode = canonicalExamCode(q);

  const { data: snapshot, error: snapshotError } = await sb
    .from("historical_law_runtime_evidence_snapshot")
    .select("schema_version,registry_sha256,record_count,historical_version_checked_count,sync_status,source")
    .eq("id", true)
    .maybeSingle();
  if (snapshotError) {
    return {
      decision: evaluateHistoricalLawTrust(String(q.id || ""), examCode, names, null, []),
      queryError: `historical_snapshot_query:${snapshotError.message}`,
    };
  }

  const { data: evidenceRows, error: evidenceError } = await sb
    .from("historical_law_runtime_evidence")
    .select("question_id,law_name,exam_code,historical_version_checked,verification_level,evidence_sha256,source_registry_sha256")
    .eq("question_id", q.id)
    .in("law_name", names);
  if (evidenceError) {
    return {
      decision: evaluateHistoricalLawTrust(String(q.id || ""), examCode, names, snapshot, []),
      queryError: `historical_evidence_query:${evidenceError.message}`,
    };
  }

  return {
    decision: evaluateHistoricalLawTrust(String(q.id || ""), examCode, names, snapshot, evidenceRows || []),
    queryError: null,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const url = Deno.env.get("SUPABASE_URL"), serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return json({ error: "Supabase server env missing" }, 500);
  const sb = createClient(url, serviceRole, { auth: { persistSession: false } });
  const supplied = req.headers.get("x-job-key") || "";
  const { data: cfg, error: cfgErr } = await sb.from("ai_analysis_job_config").select("job_key,enabled").eq("id", true).maybeSingle();
  if (cfgErr || !cfg?.enabled || !supplied || supplied !== cfg.job_key) return json({ error: "unauthorized job" }, 403);
  const internalKey = String(cfg.job_key);
  let body: any = {};
  try { body = await req.json(); } catch {}
  const limit = Math.max(1, Math.min(Number(body?.limit || 1), 3));
  const { data: claimed, error: claimErr } = await sb.rpc("claim_pending_ai_questions", { p_limit: limit });
  if (claimErr) return json({ error: `claim: ${claimErr.message}` }, 500);
  const rows: any[] = claimed || [], results: any[] = [];

  for (const q of rows) {
    try {
      let preflight = preflightQuestion(q, null, false);

      // Special grading, multi-answer, missing answers, and unmapped legal rows
      // fail closed before spending any AI tokens. A mapped legal question needs
      // BOTH a healthy current-law batch and verified exam-time Stage7 evidence.
      if (preflight.action === "review" && preflight.reason === "legal_trust_unavailable") {
        const currentTrust = await loadCurrentLegalTrust(sb, q);
        if (currentTrust.queryError) {
          await updateClaimedQuestion(sb, q, {
            analysis_status: "pending",
            analysis_error: `route_hold:${currentTrust.queryError}`.slice(0, 1000),
            analysis_started_at: null,
          });
          results.push({ id: q.id, status: "pending", route: "hold_retry", reason: currentTrust.queryError, model_called: false });
          continue;
        }

        // First apply the current-law gate. Operational watcher problems are
        // retried; changed/missing/untrusted law evidence is content review.
        preflight = preflightQuestion(q, currentTrust.decision, false);
        if (preflight.action === "hold_retry") {
          await updateClaimedQuestion(sb, q, {
            analysis_status: "pending",
            analysis_error: `route_hold:${preflight.reason}`.slice(0, 1000),
            analysis_started_at: null,
          });
          results.push({ id: q.id, status: "pending", route: "hold_retry", reason: preflight.reason, model_called: false });
          continue;
        }
        if (preflight.action === "review" && preflight.reason !== "historical_law_evidence_required") {
          await updateClaimedQuestion(sb, q, {
            analysis_status: "review",
            analysis_error: `route_review:${preflight.reason}`.slice(0, 1000),
            analysis_started_at: null,
          });
          results.push({ id: q.id, status: "review", route: "preflight_review", reason: preflight.reason, model_called: false });
          continue;
        }

        const historicalTrust = await loadHistoricalLegalTrust(sb, q);
        if (historicalTrust.queryError) {
          await updateClaimedQuestion(sb, q, {
            analysis_status: "pending",
            analysis_error: `route_hold:${historicalTrust.queryError}`.slice(0, 1000),
            analysis_started_at: null,
          });
          results.push({ id: q.id, status: "pending", route: "hold_retry", reason: historicalTrust.queryError, model_called: false });
          continue;
        }
        if (!historicalTrust.decision.trusted) {
          const reason = historicalTrust.decision.reason;
          const operationalRetry = historicalReasonIsOperationalRetry(reason);
          await updateClaimedQuestion(sb, q, {
            analysis_status: operationalRetry ? "pending" : "review",
            analysis_error: `${operationalRetry ? "route_hold" : "route_review"}:historical:${reason}`.slice(0, 1000),
            analysis_started_at: null,
          });
          results.push({
            id: q.id,
            status: operationalRetry ? "pending" : "review",
            route: operationalRetry ? "hold_retry" : "historical_review",
            reason: `historical:${reason}`,
            model_called: false,
          });
          continue;
        }

        preflight = preflightQuestion(q, currentTrust.decision, true);
      }

      if (preflight.action === "hold_retry") {
        await updateClaimedQuestion(sb, q, {
          analysis_status: "pending",
          analysis_error: `route_hold:${preflight.reason}`.slice(0, 1000),
          analysis_started_at: null,
        });
        results.push({ id: q.id, status: "pending", route: "hold_retry", reason: preflight.reason, model_called: false });
        continue;
      }

      if (preflight.action === "review") {
        await updateClaimedQuestion(sb, q, {
          analysis_status: "review",
          analysis_error: `route_review:${preflight.reason}`.slice(0, 1000),
          analysis_started_at: null,
        });
        results.push({ id: q.id, status: "review", route: "preflight_review", reason: preflight.reason, model_called: false });
        continue;
      }

      const candidate = await analyzeOne(q, internalKey);
      const finalRoute = finalizeValidatedCandidate(q, candidate, preflight);
      if (finalRoute.action === "review" || !finalRoute.patch) {
        await updateClaimedQuestion(sb, q, {
          analysis_status: "review",
          analysis_error: `route_review:${finalRoute.reason}`.slice(0, 1000),
          analysis_started_at: null,
        });
        results.push({ id: q.id, status: "review", route: "post_model_review", reason: finalRoute.reason, model_called: true });
        continue;
      }

      await updateClaimedQuestion(sb, q, finalRoute.patch);
      results.push({ id: q.id, status: "ready", route: finalRoute.action, reason: finalRoute.reason, model_called: true });
    } catch (e) {
      const msg = (e instanceof Error ? e.message : String(e)).slice(0, 1000), transient = isTransient(msg);
      const attempts = transient ? Number(q.analysis_attempts || 0) : Number(q.analysis_attempts || 0) + 1;
      const status = transient ? "pending" : attempts >= 3 ? "review" : "pending";
      try {
        await updateClaimedQuestion(sb, q, {
          analysis_status: status,
          analysis_attempts: attempts,
          analysis_error: msg,
          analysis_started_at: null,
        });
      } catch {
        // Preserve the original error in the response if the status write also fails.
      }
      results.push({ id: q.id, status, error: msg, attempts, transient });
    }
  }

  const { count: pending } = await sb.from("questions").select("id", { count: "exact", head: true }).eq("analysis_status", "pending");
  const { count: review } = await sb.from("questions").select("id", { count: "exact", head: true }).eq("analysis_status", "review");
  return json({ ok: true, claimed: rows.length, results, pending, review });
});
