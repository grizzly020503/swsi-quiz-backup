#!/usr/bin/env python3
"""Exercise the pinned integration and its preimage/answer/overwrite boundaries."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import build_official_combined_candidate as candidate


class CombinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.change = candidate.doc(candidate.REFS["shared"],
            "audit/official_105_2_shared_context_20261028.json")["changes"][0]
        shard = candidate.doc(candidate.REFS["base"], "cdn/question-shards/105-2.json")
        cls.row = next(q for q in shard["questions"] if q["id"] == cls.change["id"])

    def test_two_reproducible_builds_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            first = candidate.build(Path(temp) / "first")
            second = candidate.build(Path(temp) / "second")
            self.assertEqual(first, second)
            self.assertEqual(first["cumulative_core_changes"], 41)
            self.assertEqual(first["grading_preserved"], 4800)
            self.assertFalse(first["release_approved"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                candidate.build(Path(temp) / "first")

    def test_stale_preimage(self):
        row = dict(self.row, question="unexpected prior edit")
        with self.assertRaisesRegex(ValueError, "stale core preimage"):
            candidate.apply_fields(row, self.change)

    def test_answer_drift(self):
        row = dict(self.row, answer="unauthorized")
        with self.assertRaisesRegex(ValueError, "grading drift"):
            candidate.apply_fields(row, self.change)

    def test_unapproved_field(self):
        change = deepcopy(self.change)
        change["fields"]["answer"] = {"before": self.row["answer"], "after": "A"}
        with self.assertRaisesRegex(ValueError, "unapproved field"):
            candidate.apply_fields(self.row, change)

    def test_incorrect_postimage(self):
        change = deepcopy(self.change)
        change["fields"]["opt_d"]["after"] += "unexpected"
        with self.assertRaisesRegex(ValueError, "source postimage"):
            candidate.apply_fields(self.row, change)

    def test_repository_output_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            candidate.build(candidate.ROOT / "unsafe-output")


if __name__ == "__main__":
    unittest.main()
