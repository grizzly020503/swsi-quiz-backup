# MOEX 108-2 Q23 correction candidate (2026-10-25)

- Exam / subject: 108110, 社會工作直接服務, Q23; official paper 10720, p. 3.
- Exact official PDF SHA256: 78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b.
- The baseline duplicated ④ where the official question has ⑥ for 「發展溝通、地位、角色與規範的彈性結構」.
- Option A on paper is ②④⑥⑧, not the baseline ②④④⑧.
- Official answer stays B; all grading tuples untouched. Prior explanation is quarantined because it incorrectly assigned the flexible structure to ⑦.
- This Draft updates exactly the question row, one Official Core lock, the shard/manifest, and controlled correction proof/smoke. No production writes.

**Required before integration / release:** rerun the official PDF extraction comparator using the retained 120 exact original PDFs, refresh comparison and review-queue evidence to the new manifest SHA, then run latest-head CI and require human approval. The existing historical PDF comparison is deliberately left stale; do not claim its old pass/fail counts are a new-head verification or relax the release gate. Other unresolved items and AI human review remain HOLD.
