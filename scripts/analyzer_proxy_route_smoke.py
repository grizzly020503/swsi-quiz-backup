#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "supabase/functions/analyze-pending-questions/index.ts"
RELEASE = ROOT / ".github/workflows/prepare-cloudflare-soft-launch-artifact.yml"
CANDIDATE = ROOT / ".github/workflows/cloudflare-public-candidate.yml"

CANONICAL = 'const AI_PROXY_URL = "https://wandering-wave-4418.c022050333.workers.dev/api/ai";'
LEGACY_ROOT = 'const AI_PROXY_URL = "https://wandering-wave-4418.c022050333.workers.dev";'

analyzer = ANALYZER.read_text(encoding="utf-8")
release = RELEASE.read_text(encoding="utf-8")
candidate = CANDIDATE.read_text(encoding="utf-8")

assert analyzer.count(CANONICAL) == 1, "background analyzer must use the canonical /api/ai endpoint exactly once"
assert LEGACY_ROOT not in analyzer, "background analyzer must not POST to the Worker asset/root route"
assert 'workers.dev/api/ai' in release, "Cloudflare production release contract must preserve /api/ai"
assert "{origin}/api/ai" in candidate, "Cloudflare candidate contract must exercise /api/ai"

print("AI ANALYZER PROXY ROUTE CONTRACT OK: /api/ai")
