> Historical integration snapshot. Superseded for Official Core corrections and full PDF comparison status by [`../essay-text-20261025/README.md`](../essay-text-20261025/README.md). The later candidate changes 13 MCQ stems/options and one essay; unresolved reviews remain NO-GO.

# Final integration candidate — 2026-10-25 snapshot

**Release: NO-GO.** This is a review candidate, not a production release or an approval of every question, explanation, rubric, or model response.

## Baseline and reuse

Latest observed main: `3ea6d8859ca7b07211db19a470785fcd277d481e` (advanced from the request's historical `0ccebc2` checkpoint).

| Existing candidate | Integrated source | Decision |
| --- | --- | --- |
| #441 | `4e7763e3536db1192951787d171dedc6a893078e` | Reuse joint stack: #436 handwriting, #438/#423 calm UI, #435 Netlify, #439 watchdog, #440 bounded source retry |
| #446 | `a442360991bc40d4d92855d70ed8c1605d3077bc` | Select one 112-1 correction; do not also stack duplicate #442/#443/#444 corrections |
| #410 | `ae1cfbea96796aee07aabc71276cf23425d241b5` | Integrate trust-v3 prompt, stale-answer cache fix, Netlify redirect refusal, transport regressions and earlier answer-audit evidence; **human/model gate remains HOLD** |
| #437 | Competing handwriting implementation | Not stacked; #436 already owns this flow |
| #370 | Analyzer activation | Not activated/refreshed; live queue has no natural pending case |

The UI/handwriting source and #410 had an artifact conflict: preserve #441 calm UI, rebuild the canonical patch from its 32 parts, and update the CDN cache tag. The combined browser test now verifies OCR-only transport separately from post-confirmation text-diagnosis rules. It no longer expects premature photo grading.

## Actual source correction

- Retrieved **24 live MOEX directories + 120 live official question PDFs** with HTTP status, MIME, retrieval timestamps and SHA256.
- Re-extracted all 120 first pages, checking exact subject, exam year/session, professional class and observed paper code, and matching each URL to the subject link in that exam's official directory.
- Visual spot checks: 104-1 research (URL `s=0606` but printed code **11070**), 112-1 policy (10340), 115-2 policy (10330). Printed paper codes are observed, never inferred from URL sequence.
- Corrected **3,920 `source_url` fields versus main**: 120 from the chosen #446 candidate plus 3,800 additional independently supported historical corrections. All other question fields remain equal to main, including grading and analysis metadata. No Official Core lock was regenerated.
- Replayed the existing Git-pinned `source_url_promotion_config.json` candidate against main before-images, independently matched its URLs to all 120 new PDF identities, then reused its **exact reviewed output bytes**. See `prior-source-candidate-replay.json`. Every changed shard's SHA256/bytes and the canonical manifest aggregate/revision were checked. Dataset revision: `ceda1d399abaecec5ff6`.
- `data/moex_source_subjects.v1.json` holds the per-exam evidence. No current five-subject fallback is applied to legacy years. Unknown exams, wrong subjects, ambiguous query parameters, review status, missing HTTP/MIME/hash proof and mismatched headers fail closed.
- `official_essay_source_review_candidates.py` now requires that registry: **230 historical essay references remain review-only**, 10 already attributed; none is automatically approved by the source-link check.

Raw public evidence retained as [official PDF identity evidence](https://chatgpt.com/library?file_id=libfile_b79d61b1e80081919a0570d00dbd73c4&account_id=personal). This contains official PDFs/directories, retrieval metadata and file checksums, without browser screenshots, credentials or private data.

## Verification and its limits

| Area | Evidence/result |
| --- | --- |
| Source identity | `source-identity.json`: 120/120 identities, 4,800/4,800 links; re-extraction from downloaded bytes passed; nine negative/positive regression tests passed |
| Official Core preservation | `official_exam_readonly_guard.py`: 4,800 MCQs + 240 essays unchanged |
| Full corpus structural QA | `full-corpus.json`: all 24 sessions, 5,040 items, 0 blocked; **798 unique items still in the manual review queue**. This is not full semantic accuracy approval |
| Existing answer audit | `../official_answer_source_verification_20261023.json`: prior 4,800 answer/accepted-answer/grading comparisons and 115-2 correction evidence. Retained as prior evidence, not falsely reported as a new full-wording audit |
| Chromium UI | **14/14 final browser checks passed**. Launch readiness mobile/desktop, interaction, grading, OCR confirmation, axe, touch/max-font, storage denied, dead ends, error states, weak network, PWA, SW update, shard integrity and feedback checks passed after the documented integration-test fixes |
| Accessibility | Axe reported 0 violations on tested surfaces; some automated checks remain incomplete and require human judgment. This is not WCAG certification |
| WebKit / actual iPhone | New combined candidate not locally verified: environment lacks WebKit system libraries and package installation was denied. Prior PR CI is separate evidence; same-candidate CI remains required |
| Handwriting quality | Synthetic image/transport tests passed, including 1–3 images, expandable local JPEG page previews without persistent photo storage, bounded payload, unreadable markers, truncation, confirmation and typed fallback. Real handwriting accuracy remains unverified; independent readability/timed-writing assessment is not implemented in this candidate and is explicitly labeled as not evaluated |
| AI feedback | Golden Set and fail-closed evaluator selftests passed. Actual trust-v3 handler generated **20 exact synthetic request payloads** in `ai-requests-for-review.json`. **0 successful model outputs / 0 independent human ratings**. A bounded live request returned Cloudflare 403 / error 1010; no quota-evasion/retry loop. Required quality gate fails because reviewed candidate evidence is absent |
| Rubrics | Runtime builder reports 68 historical + 10 overlay guides with verified metadata. Those labels alone do not prove independent human review; complete per-question human rubric sign-off remains unverified |
| Operations | Exact Netlify-runtime negative fixtures, watchdog contract and bounded current-affairs recovery tests passed. Main Public Monitoring Feed run `40131025608` succeeded; newer main watchdog `40133080988` still failed. Local contracts do not clear live alerts |
| Security | Supabase read-only evidence below; Worker and importer/OIDC tests passed. Netlify redirect refusal regression passed. No production schema/data changes |
| Recovery | Backup policy, restore-target preflight and destination-guard selftests passed. Real encrypted private backup + isolated restore not performed or approved; no recovery claim |
| Production | `production-http.json`: this execution environment received 403 for Cloudflare assets and AI. Netlify returned an older UI/patch without handwriting/calm markers; backup parity not established. A Netlify-local shard 404 alone is not a failure of its external-CDN architecture |

Exact-head CI initially caught a source-candidate comparison bug: the reused byte-pinned source candidate contains both c-first and t-first URL query order. Source identity comparison now strictly parses every URL before comparing query values; wrong codes/hosts/duplicate parameters still fail closed. A regression covers mixed query order and pre-attributed essay URLs.

Initial failure statuses and retests are retained in the JSON files; `test-transcripts.json` contains the final local attempt transcripts (the transient .log files are not repository artifacts). The initially invoked nonexistent `private_backup_secret_redaction_selftest.py` is a test-selection error, not a product failure and not a pass. No CI was manually dispatched or rerun.

## Supabase read-only snapshot

- `questions=4800`, `pending=0`, `review=106`; hosted `essays=10` is the synced overlay, while the complete 240-essay corpus also includes static historical data.
- Public ordinary tables without RLS: **0**.
- Client table privileges: only SELECT on `questions` and `essays`; their SELECT policies permit public official-content reads. Feedback client policy is deny-all.
- Public security-definer functions executable by anon/authenticated: **0**.
- Security advisor: 13 deny-all/no-policy INFO findings and leaked-password-protection WARN; no permissive policy or paid upgrade was added to suppress them.
- Live legacy default grants still exist at inspection time. Existing migrations explicitly grant their intended service-role access. The October 30 platform transition and future migrations must preserve explicit GRANT + RLS; future post-transition behavior is not yet production-tested.

## Remaining release blockers / minimum next actions

1. Complete outstanding official essay/stem/content and subsequent-correction review with official evidence; do not relabel the 798 queue items as passed because structure is valid.
2. Obtain actual trust-v3 Golden Set responses through an authorized reachable model path, then **100 genuinely independent human dimension ratings**. Keep the candidate evidence gate unchanged. Use `ai-human-review-template.json`; do not fill it with AI scores.
3. Validate real legible/ordinary/partly illegible handwriting, image readability and the separation of content/readability/timed-writing assessment. OCR transport success is not this approval.
4. Same-candidate CI, including WebKit and AI quality gate. Preserve failed/missing evidence rather than manually rerunning unchanged checks.
5. Under separate explicit Owner release authorization: review/merge the selected candidate; apply reviewed source metadata to the hosted data only through its controlled workflow; publish the matching Cloudflare and Netlify artifacts; verify actual mobile/desktop/PWA/weak-network behavior and runtime/dataset parity.
6. Obtain separate authorization and a suitable isolated environment for real encrypted private-data backup/restore; independently verify heartbeat/monitoring recovery.

No main merge, production deployment, production-data update, analyzer canary, private-backup operation or new paid service was performed. Engineering implementation is advanced, but no auditable single completion percentage exists for this mixed code/content/human/production scope. The exact coverage counts above are the reliable completion measures.

## Reproduce

```bash
python scripts/audit_moex_source_subjects.py
python scripts/audit_moex_source_subjects_selftest.py
python scripts/audit_moex_source_subjects.py --evidence-dir /path/to/unpacked/official-evidence
python scripts/official_exam_readonly_guard.py
python scripts/full_corpus_qa.py --out /tmp/swsi-full-corpus.json --fail-on blocked
python scripts/official_essay_source_review_candidates.py --selftest
node scripts/ai_feedback_capture_requests.js /tmp/swsi-requests.json
python scripts/ai_feedback_eval.py
python scripts/ai_feedback_candidate_gate.py --force  # expected HOLD until genuine reviewed evidence exists
```

The joint candidate workflow builds the production-shaped UI and runs the browser, source and operations suite without provider calls or production writes. Raw request captures and blank review templates are deliberately not `ai_eval/captured/candidate.json` and cannot unlock the quality gate.
