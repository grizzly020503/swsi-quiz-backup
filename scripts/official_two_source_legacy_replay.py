#!/usr/bin/env python3
"""Prove historic source-evidence tests against their *immutable predecessor*.

Two owner-approved official option fixes intentionally change the current 111-2
and 107-2 shard/manifest/Official Core hashes. Tests pinned to the historical
predecessor must not be weakened, skipped, or falsely run against new content.
First validate the entire NEW 4,800-row release, then replay the original tests
on an EXACT, SHA-pinned predecessor in an isolated git worktree (read-only).
This never touches main, Supabase, Cloudflare, backups or live student data.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED_PRE_RELEASE = "c51f5dff3af0563944c8ba790caa1208c98885ac"
CASES = {
    "ten": ("scripts/official_ten_source_integration_smoke.py",),
    "five": ("scripts/official_five_source_mcq_smoke.py",),
    "1041": ("scripts/official_1041_ds_ocr_candidate_selftest.py",),
    "context": ("scripts/official_shared_context_13row_integration_smoke.py",),
}


def git(*args: str) -> None:
    subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                   timeout=90)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), action="append",
                        required=True)
    args = parser.parse_args()

    # Verify the actual CURRENT post-release corpus, grading locks,
    # source proof, 22 unchanged shards and three remaining holds *before*
    # using any archived historical test. Historical tests cannot sign off
    # the current official core by themselves.
    from official_two_source_owner_release_guard import verify
    verify()

    # Do not use an editable branch or "origin/main" for historic evidence.
    # A SHA is pinned and will not move when another PR merges.
    try:
        git("cat-file", "-e", PINNED_PRE_RELEASE + "^{commit}")
    except subprocess.CalledProcessError:
        git("fetch", "--no-tags", "--depth=1", "origin",
            PINNED_PRE_RELEASE)
        git("cat-file", "-e", PINNED_PRE_RELEASE + "^{commit}")

    with tempfile.TemporaryDirectory(prefix="swsi-legacy-proofs-") as temp:
        ancestor = Path(temp) / "repo"
        git("worktree", "add", "--detach", str(ancestor), PINNED_PRE_RELEASE)
        try:
            # All historic tests execute their *own* unmodified code and
            # pinned original source files; none accepts modified expected
            # SHA, row counts, answer keys, or a synthetic side-loaded patch.
            for case in dict.fromkeys(args.case):
                for path in CASES[case]:
                    subprocess.run(
                        [sys.executable, str(ancestor / path)],
                        cwd=str(ancestor), check=True, timeout=120,
                    )
                print("HISTORIC IMMUTABLE SOURCE QA PASS:", case,
                      "base", PINNED_PRE_RELEASE[:12], flush=True)
        finally:
            git("worktree", "remove", "--force", str(ancestor))

    print("TWO-RELEASE ANCESTRY PASS: 2 approved source options in CURRENT "
          "exact-locked corpus + untouched full historic source evidence "
          "(no changed historical expectations; 3 holds remain)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
