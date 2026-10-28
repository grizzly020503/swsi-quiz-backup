# 2026-10-28 Official shared-context integration — Draft / NO-GO

Source candidate #466: 105-2 research (8 question rows), PDF SHA256 `6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836`, printed pages 4-2 and 4-3.
Source candidate #467: 107-2 research (5 question rows), PDF SHA256 `65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d`, printed page 4-1.

The **unchanged Git blobs** from both original PRs are included. Both source evidence JSON files are included unchanged. The common manifest now reflects **both** edited question shard hashes (not the last writer's only), 24 shards, 4,800 questions, **7,639,946 bytes**. All 13 original core lock SHA256s are individually checked against main `464680f8673ea454e2092031a938f5603c1f8d74` and replaced with the proof-anchored new SHA256s.

Run `python scripts/official_shared_context_integration_smoke.py` and `python scripts/official_exam_readonly_guard.py`. In code construction all 13 expected IDs, old/new core locks, both MOEX source hashes, all immutable essay locks and the full 24-shard byte sum were checked. Source proofs remain NO-GO and require independent PDF human acceptance and exact-head CI.

All 4,787 remaining Official Core question locks, 240 essay locks and 22 untouched question shards remain as current main; every answer and grading tuple is explicitly unchanged in both source PRs. No main merge, Supabase UPDATE, production deployment, backup/Netlify changes or AI quality approval was performed.
