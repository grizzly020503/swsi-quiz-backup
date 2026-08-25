#!/usr/bin/env python3
from pathlib import Path

p = Path('supabase/functions/analyze-pending-questions/index.ts')
text = p.read_text(encoding='utf-8')

replacements = [
(
'async function callModel(model: string, prompt: string, reasoning: string, maxTokens: number) {',
'async function callModel(model: string, prompt: string, reasoning: string, maxTokens: number, internalKey: string) {'
),
(
'    const r = await fetch(AI_PROXY_URL, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });',
'    const r = await fetch(AI_PROXY_URL, { method: "POST", headers: { "content-type": "application/json", "x-internal-key": internalKey }, body: JSON.stringify(body) });'
),
(
'async function analyzeOne(q: any) {\n  const draftRows = await callModel(DRAFT_MODEL, initialPrompt(q), "none", 1400);\n  if (!Array.isArray(draftRows) || draftRows.length !== 1) throw new Error("草稿格式異常");\n  const finalRows = await callModel(AUDIT_MODEL, auditPrompt(q, draftRows[0]), "medium", 1500);',
'async function analyzeOne(q: any, internalKey: string) {\n  const draftRows = await callModel(DRAFT_MODEL, initialPrompt(q), "none", 1400, internalKey);\n  if (!Array.isArray(draftRows) || draftRows.length !== 1) throw new Error("草稿格式異常");\n  const finalRows = await callModel(AUDIT_MODEL, auditPrompt(q, draftRows[0]), "medium", 1500, internalKey);'
),
(
'  if (cfgErr || !cfg?.enabled || !supplied || supplied !== cfg.job_key) return json({ error: "unauthorized job" }, 403);\n  let body: any = {};',
'  if (cfgErr || !cfg?.enabled || !supplied || supplied !== cfg.job_key) return json({ error: "unauthorized job" }, 403);\n  const internalKey = String(cfg.job_key);\n  let body: any = {};'
),
(
'      const patch = await analyzeOne(q);',
'      const patch = await analyzeOne(q, internalKey);'
),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit('missing expected patch marker: ' + old[:100])
    text = text.replace(old, new, 1)

# Guards
for required in [
    '"x-internal-key": internalKey',
    'async function analyzeOne(q: any, internalKey: string)',
    'const internalKey = String(cfg.job_key);',
    'await analyzeOne(q, internalKey)',
]:
    if required not in text:
        raise SystemExit('patch guard failed: ' + required)

p.write_text(text, encoding='utf-8')
print('Patched analyze-pending-questions to forward internal AI proxy key.')
