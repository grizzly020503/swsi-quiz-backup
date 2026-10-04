# Public history scan disposition — 2026-10-04

Issue: [#330](https://github.com/grizzly020503/swsi-quiz-backup/issues/330). The repository must remain Private until the updated scanner passes against a freshly fetched, complete all-refs clone and the final visibility checklist is reviewed.

## Baseline and classification

The owner's complete local scan at `main` `db20ada02a9d086cd9bd4c7534880b2e0cc4a52d` examined 2,952 text blobs and reported 113 credential/security blockers, 5 inline-email review findings, 4,451 already accepted commit-email metadata entries, and `FAIL`.

| Original findings | Count | Disposition |
| --- | ---: | --- |
| JWT pattern in frontend HTML | 87 | One repeated legacy Supabase public `anon` JWT. All decoded payloads have `role=anon`, `iss=supabase`, the SWSI project reference, and only `exp/iat/iss/ref/role` claims. Scanner accepts this narrow shape only in the matching public frontend configuration; `service_role` and unknown JWTs block. |
| Literal assignment in isolated QA | 16 | Ten exact disposable `POSTGRES_PASSWORD=postgres` assignments in three DR/candidate database workflows; six exact `SWSI_INTERNAL_KEY=internal-secret` assignments in the Worker smoke test. Path and literal must both match. |
| Archive path | 4 | The four historical ZIP blobs listed below were individually opened, CRC checked, and inventoried. Scanner accepts only their exact SHA-256 digests and rechecks their entries and inner text. |
| Checksum sidecar path | 2 | `.zip.sha256` text files were matched by the previous archive suffix regex. They are not containers; the tightened path pattern no longer treats them as ZIPs. |
| Opaque container | 4 | Duplicate findings for the same four ZIP blobs above. Unknown ZIPs and all other opaque containers still block. |

The four ZIPs have 13 or 14 files each, no encryption, no nested archive, no unsafe path, and valid CRC. Three contain deployable frontend assets; the fourth includes an exam-question CSV with 22 question/content columns. Inner text produced only the same public `anon` JWT; no credential pattern, sensitive literal assignment, or inline email was found after its classification. The SHA-256 digests are pinned in the scanner for blobs `97307bc25c2d`, `ef0fef0096df`, `0bb1ae1187f4`, and `ade1f9e80db9`. A byte change requires renewed review.

Seven binary blobs were previously labelled skipped: these four ZIPs and three PNG icons. The icons contain only `IHDR`, `IDAT`, and `IEND` PNG chunks, with no text metadata or secret/email pattern. Their exact digests are also pinned; unknown binary blobs block.

## Identity review

Four of the five original email findings are selftest/smoke fixtures under the reserved `.invalid` domain. The scanner now treats this domain as a placeholder. The fifth is the previously documented historical admin-email prefill in one immutable `cdn/preview/admin/index.html` blob. Issue #330 records that the replacement admin successfully accessed production and the old personal UUID was removed from `swsi_admin_users`. The owner path recorded there accepts this residual historical linkage without a history rewrite. The scanner accepts only that exact blob ID, path, and SHA-256; any changed/new inline email or external identity-pattern match still requires review.

This does not erase historical personal-name attribution. Its residual exposure and the choice to avoid a history rewrite remain the owner's documented privacy decision in #330. Optional private identity regexes can still be supplied from outside the working tree for additional review.

## Verification and remaining gate

Run `python scripts/public_repo_history_secret_scan_selftest.py` and `python scripts/public_repo_history_secret_scan.py` after fetching all refs and confirming the clone is not shallow. The regression test includes `service_role`, wrong project, wrong context, non-fixture literals, and an unknown ZIP as blocking cases. Record the final counts and exit code in #330. Do not infer `PASS` from an Actions job with zero steps.

Even after a scanner `PASS`, keep the repo Private until the current refs, open PRs, retained Actions/artifacts, releases/deployment links, license decision, and visibility cutover protections are checked. No history rewrite is justified by these classified findings.
