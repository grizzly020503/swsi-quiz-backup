#!/usr/bin/env python3
from pathlib import Path

src = Path("supabase/functions/analyze-pending-questions/index.ts").read_text(encoding="utf-8")
required = [
    'const DRAFT_MODEL = "qwen/qwen3.8-27b";',
    'const AUDIT_MODEL = "openai/gpt-oss-120b";',
    'formatRetries = 0',
    'if (formatRetries < 1 && attempt < 3)',
    'function auditRepairPrompt(q: any, draft: any, failure: string)',
    'for (let auditAttempt = 0; auditAttempt < 2; auditAttempt++)',
    'prompt = auditRepairPrompt(q, draftRows[0], lastValidation);',
    'return validateFinal(q, finalRows);',
    'if (k !== "law" && !clean(row[k])) throw new Error(`${k} 空白`);',
    'if (extraAscii.length) throw new Error(`新增題面沒有的英文詞: ${extraAscii.join(',')}`);',
    'if (extraNums.length) throw new Error(`新增題面沒有的數字: ${extraNums.join(',')}`);',
    # A retired model or a provider outage must not park questions for review.
    'import { isTransient, MODEL_UNAVAILABLE, PROVIDER_UNAVAILABLE, providerFailure } from "./provider_errors.ts";',
    '[DRAFT_MODEL]: { model: AUDIT_MODEL, reasoning: "low" },',
    '[AUDIT_MODEL]: { model: DRAFT_MODEL, reasoning: "none" },',
    'await callWithFallback(DRAFT_MODEL, initialPrompt(q), "none", 1400, internalKey)',
    'await callWithFallback(AUDIT_MODEL, prompt, "medium", 1500, internalKey)',
    'const attempts = transient ? Number(q.analysis_attempts || 0) : Number(q.analysis_attempts || 0) + 1;',
]
missing = [marker for marker in required if marker not in src]
if missing:
    raise SystemExit("ANALYZER RETRY CONTRACT FAILED missing=" + repr(missing))
if src.count('return validateFinal(q, finalRows);') != 1:
    raise SystemExit('ANALYZER RETRY CONTRACT FAILED unexpected validateFinal call count')
print('ANALYZER RETRY CONTRACT OK strict_validator=unchanged format_retry=1 audit_repair=1 model_fallback=1 provider_errors_free=1')
