# Official text correction candidate and release holds

## Follow-up preserving concurrent corrections (2026-10-25)

Based on candidate `1a94608`, retain its three additional official corrections and add two independently visually checked repairs: `R-113-2-30` (113100/103/0306 p3) had four shifted/truncated options, and `R-106-2-01` (106110/107/0606 p1) lacked the opening stem. The overlapping `DS-110-2-14` repair already submitted by the other worker is preserved exactly. Additional proof grows 3→5, for 20 cumulative MCQ corrections; 4,780 other complete rows and all 4,800 answer/grading tuples remain baseline-guarded. Old enrichment is quarantined. Browser correction coverage now includes both proof files, all 20 items.

Fresh real-PDF comparison is **4,364 MCQ matches / 436 review**, plus **222 essay matches / 18 review**, yielding **454 holds**. The release-gate source is unchanged and still refuses publication. Source/lock boundaries, essay immutability, full corpus, gate tamper and freshness checks pass locally. Same-head browser/CI and independent AI evidence are still required. This isolated branch avoids overwriting concurrent candidate updates; no main merge or deployment.

## Latest two negation corrections (2026-10-25)

This follow-up corrects `SW-106-1-40` option B to 「不同住之前夫」 (official 106030/107/0601 page 4), and `R-105-1-24` options B/D to 「更可能發生歷史效應」 / 「更可能發生統計迴歸效應」 (official 105030/107/0606 page 3). Both original PDFs were visually inspected. Exact before/after values, raw PDF and answer hashes, page numbers and the two additional lock deltas are appended to the existing controlled correction proof. Stale enrichment on these two rows is quarantined. No answer or grading tuple changed. The cumulative correction boundary is now 15 MCQs; 4,785 other complete rows and the original baseline lock map remain fingerprint-guarded.

Current PDF results: **4,359 MCQ matches / 441 MCQ review**, plus **222 essay matches / 18 essay review**, for **459 unresolved**. Both negation defects are repaired; the social-work question still has another textual difference, so its review status is retained. The refreshed triage queue has 58 priority-0, 362 priority-1 and 39 priority-2 rows. No release gate was changed. Local controlled-correction, essay-boundary, immutable-core, full-corpus, evidence-freshness and gate-tamper checks pass. Prior CI evidence below applies to its recorded commit only; the new candidate still needs same-head CI and independent AI evidence. No production write or deployment.

### Earlier extraction snapshot

## Current extraction follow-up (2026-10-25)

**Draft / NO-GO.** The same Official Core remains untouched by this follow-up. The current reproducible reports supersede the older comparison counts below:

| Scope | Current result |
| --- | --- |
| MCQ normalized text + final grading | 4,358 matches / **442 review** |
| MCQ review reasons | **1** image-only full-option question / **441** textual or layout differences |
| Essay text | 222 matches / **18 review** |
| All PDF text release holds | **460**, previously 871 |
| Real AI model evidence / independent human ratings | Still missing; no new AI approval |

The audit now uses one fixed Poppler `pdftotext -layout` extraction, a horizontal-whitespace question-number parser, and per-question failure isolation. It does not choose the extractor that happens to match the stored corpus. Exactly one previously matching question, `R-113-2-33`, now stays in review because a raised chi-square exponent crosses option boundaries in layout extraction. That difference is retained rather than hidden.

Three exact official PDF hashes contain A-D labels as soft-mask images. Seventeen visually inspected exact mask hashes recover **476 label occurrences**, with every PDF/page/bounding box/mask hash/label recorded in `image_marker_decodings`. The white 2x2 base image is NOT a label identity: distinct soft masks carry the real glyphs. Only the known source PDF bytes and known masks can be decoded. Unknown masks and full-option images are not inferred. This clears 65 more mechanical comparisons; 55 now expose actual text/layout differences for review. This is traceable machine extraction, not independent human approval.

The original question ZIP was truncated in its last directory page. All 120 complete PDF entries were recovered using local-header lengths and CRC, then independently matched to their registered SHA256. Seven complete directory pages also matched. Seventeen current official directories were fetched again; their five subject Q links and exact observed S/M answer-kind sets were checked before refreshing directory HTTP fingerprints for 85 source records and corresponding answer-manifest rows. Original PDF hashes/URLs, questions, answers, grading and Official Core locks were unchanged. Prior directory hashes are retained as `previous_index_sha256`.

The complete replacement raw evidence archive is [retained here](https://chatgpt.com/library?file_id=libfile_97e4ad821a248191b00f22ac0f2a926b&account_id=personal), SHA256 `6e1258de9890efc85714a3e4b0fefcdbd552cae3dd5f6c5dc14735f068de428f`. It contains all 120 unchanged question PDFs, 24 current matching directories, `directory-refresh.json`, and `refreshed-answer-http.json`. The old `http.json` is historical transport evidence; the refresh manifest and repository registry describe current directory bytes. For reproduction, extract the existing 153-answer archive linked below, replace its `http.json` with `refreshed-answer-http.json`, and run the original audit commands. PDF byte hashes must still match. Test-only extraction dependencies used: requests 2.32.5, pypdf 6.1.3, pdfplumber 0.11.7, PyMuPDF 1.26.5 and Poppler 24.02.0. Selftests remain no-network and do not import those extraction dependencies.

The newer main monitoring snapshot `5e249075` was then merged into this candidate branch. Six generated signal/event/trend conflicts were resolved by retaining main news and event observation history and rebuilding the three outputs, mirrored to CDN. The exact monitoring PR rebuild contract and three monitoring smokes pass without a new feed scan or production write.

The release-gate implementation is unchanged. Evidence validation passes; the default gate still exits 2 on 460 unresolved comparisons. No merge, production deploy or database write was performed. Existing browser/CI results below belong to earlier commits and are not new-head evidence.

## Prior correction snapshot (historical counts retained)

This extends PR #447 from `fda6bd6aa149b400d1bd00d1c4221e28e9ba53df`. It supersedes the older `audit/final-20261025` snapshot's statement that all Official Core fields were unchanged. **Draft / NO-GO; no production writes or deployment.**

## Controlled corrections

- **1 essay:** `社會工作-112-2-申論2` was an unrelated resource-allocation question. Official paper 10310, page 1, asks for Cowger's matrix applied to economically disadvantaged women's employment and a service plan. Corrected only this official stem; its identity and 25 points remain unchanged. Removed stale tags and quarantined the unrelated ethics guide in the runtime asset and both inline fallbacks.
- **13 MCQs:** `SW-109-1-05`; `SP113-1-30/31/32/33/34/35/37/38/39/40`; `DS-115-1-18/22`. Replaced demonstrably substituted/truncated stems/options with the official PDF text. Restored the numbered statements and combination choices in the two 115-1 questions. All 4,800 answer/accepted-answer/grading tuples are unchanged. Cleared stale platform explanations for these 13 questions.
- Updated exactly 13 MCQ locks and one essay lock, three shard hashes and the canonical manifest revision (`ee9b3070af49baa14acb`). The unchanged 4,787 complete MCQ rows and 239 other essay locks are fingerprinted against the baseline. This is a controlled branch candidate, not a blanket lock regeneration or maintainer approval.
- AI feedback cache v2 binds the answer to the current official question, verified reference, model and trust prompt version. Legacy or mismatched feedback is ignored.

Evidence: `audit/official_essay_112_2_sw2_correction.json` and `audit/official_mcq_corrections_20261025.json` include exact before/after records, official question/answer URLs, raw PDF SHA256, page references and lock deltas. Visual inspection and a second PDF text extractor were used; neither is represented as independent human approval.

## Full comparison coverage

| Scope | Result | Limitation |
| --- | --- | --- |
| Official source identities | 120/120 papers; 24 observed directories | Identity is not full text approval |
| Answer evidence | 120 standard + 33 directory-linked correction PDFs downloaded, HTTP/MIME/hash recorded | Does not prove that every separate historical announcement has been discovered |
| MCQ grading semantics | 4,800/4,800 compared; zero differences | 10 different representative answers have the same accepted-answer set; preserved, not rewritten |
| MCQ stems/options | 3,947 normalized matches; **853 review** | 520 affected by existing parser/layout limitations, 333 textual/layout differences; not 853 proven wrong questions |
| Essays | 222 normalized matches; **18 review** | Includes wording/punctuation differences and parser/font limitations |
| Structural full-corpus QA | 5,040 items; blocked=0; manual queue=796 | Structural QA and PDF review queues differ and overlap; do not add their counts |

`official_mcq_pdf_comparison_20261025.json` and `official_essay_pdf_comparison_20261025.json` are bound to their exact source/parser/input fingerprints. Matches normalize only font/layout forms, not negations, law numbers or answer semantics. They do not approve platform explanations or essay rubrics.

**871 unresolved PDF text comparisons remain release blockers.** The new separate `official-pdf-text-release-gate` CI job validates input hashes and deliberately fails with exit 2 while these reviews remain. Code/browser acceptance can succeed independently; a green structural test does not clear this gate.

## Reproduction and local tests

```sh
python scripts/official_essay_correction_smoke.py
python scripts/official_mcq_corrections_smoke.py
python scripts/official_pdf_text_release_gate.py --selftest
python scripts/official_pdf_text_release_gate.py --check-evidence-only
python scripts/official_pdf_text_release_gate.py  # expected exit 2 / NO-GO

# With retained official files; uses existing MOEX parser, no downloads/writes:
python scripts/official_essay_pdf_audit.py --evidence-dir /path/to/moex-evidence --out /tmp/essays.json
python scripts/official_mcq_pdf_audit.py --evidence-dir /path/to/moex-evidence --answer-evidence-dir /path/to/moex-answer-evidence --out /tmp/mcq.json
```

- `deterministic-checks.json`: 9/9 local checks, including the actual Netlify build command, source identities, Official Core boundaries, manifest integrity and full-corpus QA.
- `browser-checks.json` / `browser-transcripts.json`: 7/7 Chromium suites: official essay and 13 MCQ corrections, stale cache/guide/analysis rejection, phone/desktop, handwriting OCR confirmation, navigation, grading and axe. Transport fixtures are explicitly synthetic and are not AI quality evidence.
- Same-head CI on `0ad5de62` completed `exact-head-acceptance` successfully, including the new essay and MCQ correction tests on Chromium and WebKit. Its independent PDF release job correctly failed on 871 unresolved comparisons.
- That CI also found stale derived current-affairs links after the question corrections. Regenerated the three existing signals/events/trends snapshots in both `auto/` and `cdn/auto/`; the exact deterministic monitoring workflow was replayed locally. No new feed scan or production mutation. Evidence: `monitoring-rebuild.json`.
- Local WebKit cannot launch without missing system libraries. The pinned GitHub Playwright container runs Chromium and WebKit against the same commit; final CI results are recorded in PR #447.
- Genuine Golden Set model outputs remain 0/20 and independent human dimension ratings 0/100. The AI quality HOLD is unchanged. Photograph OCR/readability quality and timed writing ability are not certified by synthetic transport tests.
- Production parity, independent monitoring and private encrypted-backup restore remain unverified. Earlier Supabase read-only observations are in `audit/final-20261025`; this continuation did not mutate the database or access private backups.

Raw question evidence archive (120 PDFs + 24 directories): [retained archive](https://chatgpt.com/library?file_id=libfile_b79d61b1e80081919a0570d00dbd73c4&account_id=personal).
Raw answer evidence archive (153 PDFs + HTTP manifest): [retained archive](https://chatgpt.com/library?file_id=libfile_73b59ab931fc8191a147f776b0992070&account_id=personal), SHA256 `7bc831740c8622e91a28974ab69a313511fb96137f852be2d5d61db09155f389`.

Merge/deploy is not requested while these P0 and human-quality holds remain. No main merge, production deploy, production data mutation, private backup operation, Analyzer activation or paid service was performed.
