# Official text correction candidate and release holds

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
- Local WebKit cannot launch without missing system libraries. The pinned GitHub Playwright container runs Chromium and WebKit against the same commit; final CI results are recorded in PR #447.
- Genuine Golden Set model outputs remain 0/20 and independent human dimension ratings 0/100. The AI quality HOLD is unchanged. Photograph OCR/readability quality and timed writing ability are not certified by synthetic transport tests.
- Production parity, independent monitoring and private encrypted-backup restore remain unverified. Earlier Supabase read-only observations are in `audit/final-20261025`; this continuation did not mutate the database or access private backups.

Raw question evidence archive (120 PDFs + 24 directories): [retained archive](https://chatgpt.com/library?file_id=libfile_b79d61b1e80081919a0570d00dbd73c4&account_id=personal).
Raw answer evidence archive (153 PDFs + HTTP manifest): [retained archive](https://chatgpt.com/library?file_id=libfile_73b59ab931fc8191a147f776b0992070&account_id=personal), SHA256 `7bc831740c8622e91a28974ab69a313511fb96137f852be2d5d61db09155f389`.

Merge/deploy is not requested while these P0 and human-quality holds remain. No main merge, production deploy, production data mutation, private backup operation, Analyzer activation or paid service was performed.
