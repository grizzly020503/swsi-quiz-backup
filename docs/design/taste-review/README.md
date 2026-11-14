# SWSI UI/UX review candidate — not approved for release

This branch is a design review only. No merge or deployment is authorized.

## Design diagnosis and direction

Observed on the hosted homepage and quiz on 2026-11-14: several similar card boundaries compete for attention; serif question text and sans navigation are inconsistent; small labels are difficult to scan; desktop navigation floats separately to the right; legacy V2, V3 and component styles overlap. The student route is accessible without signing in; administrator authentication is a separate boundary and has not been tested with credentials.

Open `directions.html` for **three static homepage + quiz concepts**. These are visual concepts, not functional alternatives, and use an explicitly labelled invented demonstration question.

| Direction | Design | Assessment |
|---|---|---|
| A — 暖白閱讀室 | Warm neutral canvas, deep green actions, unboxed welcome, clear reading rows | Selected for implementation: retains the green identity, reduces surfaces, supports prolonged reading |
| B — 冷灰學習工作台 | Blue-grey canvas, compact panel hierarchy, square controls | Useful for dense work, but feels more administrative |
| C — 深綠書院 | Dark green welcome, serif editorial headings, warm paper | Strong identity, but the heavy welcome and mixed typography compete with study text |

## Shared system

- Canvas `#F7F6F2`; surface white; ink `#25332F`; secondary `#58645F`; action `#214D43`.
- Success/error retain distinct colours and existing answer markers; official answers remain untouched.
- System Traditional Chinese sans font: no external font request required. Reading text 16px default; question text 18.67px; labels 13px. Existing A/A/A controls retained.
- Spacing 8/12/16/24/32/40px; control radius 10px, surface 12px; 48px action targets and 44px font controls.
- 800px reading shell; existing bottom navigation on smaller displays; coherent left-side navigation from 1100px. Quiz retains distraction-free navigation behavior.
- Visible keyboard focus, skip-to-content link, reduced motion, existing form labels and modal focus guards.

## Implementation ownership

The shared stylesheet replaces the former V2 + V3 visual layers, retaining the V2 identifier as a compatibility anchor. No new late `zz` patch or stylesheet is added. Homepage styling stays in `20.product-philosophy.part`; shell geometry in `15.layout-foundation.part`; question rows in `30.focused-quiz-style.part`; font scaling in existing typography owners. The compiled CDN patch is rebuilt byte-for-byte from parts. Live-parity tests are updated to enforce the consolidated system instead of requiring two historical layers.

Changes also remove the homepage's misleading claim of handwriting upload while its OCR candidate remains an unmerged PR. No OCR functionality is removed or introduced.

## Verification at initial submission

Passed locally:
- `cloudflare_release_artifact_smoke.py`: compiled artifact parity, official guide count, stylesheet parity and token contrast.
- `p0_frontend_preflight.js`: 0 blockers, grading/storage/loader/AI boundaries retained.
- `service_worker_update_smoke.js`: cache update, quota and missing-image degradation checks.
- `monthly_patch_build.py` + `monthly_frontend_smoke.py` on a disposable build.
- JavaScript syntax and `git diff --check`.

**Browser acceptance is pending.** Local Chromium cannot start: this execution environment rejects its socket creation. The added PR-only `Taste UI Design Review (NO DEPLOY)` workflow runs against isolated localhost fixtures, blocks external requests in the visual script, captures baseline/candidate at 390/768/1024/1440, and runs existing interaction, grading and offline-integrity tests. Its artifact is evidence only after the workflow actually succeeds and images are visually reviewed. A screenshot is not itself proof of login, AI quality or offline durability.

Remaining before approval:
- Inspect before/after screenshots and fix any visual regressions.
- Verify long text, largest text size, keyboard navigation, error/loading states, simulation results, essay drafts and AI failure paths.
- Real iPhone/Safari and credentialed login have not been accepted. Do not use production student credentials/data for fixtures.
- Existing legacy feature styles still exist outside the consolidated visual owners; this is not a claim of full CSS debt removal.
- SW is network-first for mutable HTML/JS. Cache version was not changed: no cache contract or asset path changed. A real browser upgrade/offline pass is still required.

## Taste Skill provenance and limits

Official source: https://github.com/Leonxlnx/taste-skill at `f6b76575f949707b4e3c37cd86cb44b0b98643e8`, version 2.5.1, MIT. Read README, SKILL.md, plugin manifest and installer behavior. CLI supports plugins, but the actual marketplace install failed because its installation directory is read-only. **Not installed; no new-session automatic loading claimed.** Used the retrieved instructions as design guidance, specifically one system, readable hierarchy, real-browser checks and restrained interaction. Did not copy or run third-party executable scripts or enable hooks. The reviewed plugin manifest declares a skills directory, not a remote MCP service.

Per Owner brief, marketing-only prescriptions (full-screen sections, mandatory moments, WebGL, photograph quotas and randomized palettes) do not apply to this education product. The official marketing-page finish gate was not run; no Taste `GATE: PASS` is claimed.
