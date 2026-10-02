#!/usr/bin/env python3
from pathlib import Path
from textwrap import dedent

ANALYZER = Path('supabase/functions/analyze-pending-questions/index.ts')
ROUTE_WF = Path('.github/workflows/ai-analyzer-route-qa.yml')
TEST = Path('scripts/analyzer_retry_contract_smoke.py')

s = ANALYZER.read_text(encoding='utf-8')

old_call = dedent('''\
async function callModel(model: string, prompt: string, reasoning: string, maxTokens: number, internalKey: string) {
  const body: any = { model, temperature: 0, max_tokens: maxTokens, messages: [{ role: "user", content: prompt }] };
  if (reasoning) body.reasoning_effort = reasoning;
  let last = "";
  for (let attempt = 0; attempt < 4; attempt++) {
    const r = await fetch(AI_PROXY_URL, { method: "POST", headers: { "content-type": "application/json", "X-SWSI-Internal-Key": internalKey }, body: JSON.stringify(body) });
    const text = await r.text();
    if (r.status === 429) {
      last = `AI ${model} HTTP 429: ${text.slice(0, 300)}`;
      const hs = Number(r.headers.get("retry-after") || 0), m = text.match(/try again in\\s+([0-9.]+)s/i), ms = m ? Number(m[1]) : 0;
      const w = Math.max(5, Math.min(35, hs || ms || 8));
      if (attempt < 3) { await delay((w + 1) * 1000); continue; }
      throw new Error(last);
    }
    if (!r.ok) throw new Error(`AI ${model} HTTP ${r.status}: ${text.slice(0, 300)}`);
    const data: any = JSON.parse(text), content = data?.choices?.[0]?.message?.content;
    if (typeof content !== "string") throw new Error(`AI ${model} response shape invalid`);
    return JSON.parse(stripJsonFence(content));
  }
  throw new Error(last || `AI ${model} failed`);
}
''')

new_call = dedent('''\
async function callModel(model: string, prompt: string, reasoning: string, maxTokens: number, internalKey: string) {
  const body: any = { model, temperature: 0, max_tokens: maxTokens, messages: [{ role: "user", content: prompt }] };
  if (reasoning) body.reasoning_effort = reasoning;
  let last = "", formatRetries = 0;
  for (let attempt = 0; attempt < 4; attempt++) {
    const r = await fetch(AI_PROXY_URL, { method: "POST", headers: { "content-type": "application/json", "X-SWSI-Internal-Key": internalKey }, body: JSON.stringify(body) });
    const text = await r.text();
    if (r.status === 429) {
      last = `AI ${model} HTTP 429: ${text.slice(0, 300)}`;
      const hs = Number(r.headers.get("retry-after") || 0), m = text.match(/try again in\\s+([0-9.]+)s/i), ms = m ? Number(m[1]) : 0;
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
''')

if s.count(old_call) != 1:
    raise SystemExit(f'callModel source shape changed; count={s.count(old_call)}')
s = s.replace(old_call, new_call, 1)

old_analyze = dedent('''\
async function analyzeOne(q: any, internalKey: string) {
  const draftRows = await callModel(DRAFT_MODEL, initialPrompt(q), "none", 1400, internalKey);
  if (!Array.isArray(draftRows) || draftRows.length !== 1) throw new Error("草稿格式異常");
  const finalRows = await callModel(AUDIT_MODEL, auditPrompt(q, draftRows[0]), "medium", 1500, internalKey);
  return validateFinal(q, finalRows);
}
''')

new_analyze = dedent('''\
function auditRepairPrompt(q: any, draft: any, failure: string) {
  return `${auditPrompt(q, draft)}\\n上一版未通過結構驗證：${failure}\\n請只修正這個問題與必要連帶欄位，仍須遵守全部原規則，重新輸出完整 JSON array。`;
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
''')

if s.count(old_analyze) != 1:
    raise SystemExit(f'analyzeOne source shape changed; count={s.count(old_analyze)}')
s = s.replace(old_analyze, new_analyze, 1)
ANALYZER.write_text(s, encoding='utf-8')

TEST.write_text(dedent('''\
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
    'if (extraAscii.length) throw new Error(`新增題面沒有的英文詞: ${extraAscii.join(\',\')}`);',
    'if (extraNums.length) throw new Error(`新增題面沒有的數字: ${extraNums.join(\',\')}`);',
]
missing = [marker for marker in required if marker not in src]
if missing:
    raise SystemExit("ANALYZER RETRY CONTRACT FAILED missing=" + repr(missing))
if src.count('return validateFinal(q, finalRows);') != 1:
    raise SystemExit('ANALYZER RETRY CONTRACT FAILED unexpected validateFinal call count')
print('ANALYZER RETRY CONTRACT OK strict_validator=unchanged format_retry=1 audit_repair=1')
'''), encoding='utf-8')

y = ROUTE_WF.read_text(encoding='utf-8')
path_marker = "      - 'scripts/analyzer_proxy_route_smoke.py'\n"
if y.count(path_marker) != 2:
    raise SystemExit(f'route workflow path marker count={y.count(path_marker)}')
y = y.replace(path_marker, path_marker + "      - 'scripts/analyzer_retry_contract_smoke.py'\n")
run_old = "          python -m py_compile scripts/analyzer_proxy_route_smoke.py\n          python scripts/analyzer_proxy_route_smoke.py\n"
run_new = "          python -m py_compile scripts/analyzer_proxy_route_smoke.py scripts/analyzer_retry_contract_smoke.py\n          python scripts/analyzer_proxy_route_smoke.py\n          python scripts/analyzer_retry_contract_smoke.py\n"
if y.count(run_old) != 1:
    raise SystemExit(f'route workflow run marker count={y.count(run_old)}')
y = y.replace(run_old, run_new, 1)
ROUTE_WF.write_text(y, encoding='utf-8')

print('temporary patch helper completed')
