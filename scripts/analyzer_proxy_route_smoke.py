#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "supabase/functions/analyze-pending-questions/index.ts"
WORKER = ROOT / "cloudflare/wandering-wave-4418/worker.js"
WORKER_SMOKE = ROOT / "scripts/cloudflare_worker_smoke.js"
GOLDEN = ROOT / "ai_eval/golden_set.json"
SHARD_WORKFLOW = ROOT / ".github/workflows/question-shards-publish.yml"
RELEASE = ROOT / ".github/workflows/prepare-cloudflare-soft-launch-artifact.yml"
CANDIDATE = ROOT / ".github/workflows/cloudflare-public-candidate.yml"

CANONICAL_ROUTE = 'const AI_PROXY_URL = "https://wandering-wave-4418.c022050333.workers.dev/api/ai";'
LEGACY_ROOT = 'const AI_PROXY_URL = "https://wandering-wave-4418.c022050333.workers.dev";'
CURRENT_MODEL = "qwen/qwen3.8-27b"
DEPRECATED_MODEL = "qwen/qwen3.6-27b"

texts = {
    "analyzer": ANALYZER.read_text(encoding="utf-8"),
    "worker": WORKER.read_text(encoding="utf-8"),
    "worker_smoke": WORKER_SMOKE.read_text(encoding="utf-8"),
    "golden": GOLDEN.read_text(encoding="utf-8"),
    "shard_workflow": SHARD_WORKFLOW.read_text(encoding="utf-8"),
    "release": RELEASE.read_text(encoding="utf-8"),
    "candidate": CANDIDATE.read_text(encoding="utf-8"),
}

assert texts["analyzer"].count(CANONICAL_ROUTE) == 1, "background analyzer must use the canonical /api/ai endpoint exactly once"
assert LEGACY_ROOT not in texts["analyzer"], "background analyzer must not POST to the Worker asset/root route"
assert 'workers.dev/api/ai' in texts["release"], "Cloudflare production release contract must preserve /api/ai"
assert "{origin}/api/ai" in texts["candidate"], "Cloudflare candidate contract must exercise /api/ai"

for name in ("analyzer", "golden", "shard_workflow"):
    assert DEPRECATED_MODEL not in texts[name], f"{name} still references deprecated Groq model {DEPRECATED_MODEL}"
for name in ("analyzer", "worker", "worker_smoke", "golden", "shard_workflow"):
    assert CURRENT_MODEL in texts[name], f"{name} must reference current Groq model {CURRENT_MODEL}"

assert f'const DRAFT_MODEL = "{CURRENT_MODEL}";' in texts["analyzer"], "background analyzer draft model contract drifted"
assert f'const PUBLIC_MODEL = "{CURRENT_MODEL}";' in texts["worker"], "public Worker model contract drifted"
assert texts["worker"].count(f'const LEGACY_PUBLIC_MODEL = "{DEPRECATED_MODEL}";') == 1, "legacy public alias must be explicit and unique"
assert texts["worker_smoke"].count(DEPRECATED_MODEL) == 1, "worker smoke must cover exactly one legacy public compatibility request"
assert 'model: isInternal ? body.model : PUBLIC_MODEL' in texts["worker"], "public requests must always use the current upstream model"

print(f"AI ANALYZER ROUTE + MODEL CONTRACT OK: /api/ai + {CURRENT_MODEL}")
