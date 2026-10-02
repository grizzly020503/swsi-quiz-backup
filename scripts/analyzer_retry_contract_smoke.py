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
]
missing = [marker for marker in required if marker not in src]
if missing:
    raise SystemExit("ANALYZER RETRY CONTRACT FAILED missing=" + repr(missing))
if src.count('return validateFinal(q, finalRows);') != 1:
    raise SystemExit('ANALYZER RETRY CONTRACT FAILED unexpected validateFinal call count')
print('ANALYZER RETRY CONTRACT OK strict_validator=unchanged format_retry=1 audit_repair=1')
