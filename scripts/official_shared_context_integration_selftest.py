#!/usr/bin/env python3
"""Negative regression cases for source integration; never edit the real corpus."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash
from official_shared_context_integration_smoke import (
    INTEGRATION, LOCK, ROOT, SHARDS, SOURCE_PROOFS, baseline_reader,
    dataset_revision, sha, verify,
)


class IntegrationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = baseline_reader(ROOT, json.loads((ROOT / INTEGRATION).read_bytes())["baseline_commit"])
        # Load once, before the temporary tests; unavailable Git history fails closed.
        manifest = json.loads(cls.before(SHARDS + "manifest.json"))
        cls.preimages = {p: cls.before(p) for p in [
            SHARDS + "manifest.json", LOCK, "index.html", "auto/essays_auto.json",
            *(SHARDS + e["file"] for e in manifest["shards"]),
        ]}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths = [*self.preimages, INTEGRATION, *(p for _, p, _, _ in SOURCE_PROOFS)]
        for path in paths:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)

    def read_before(self, path):
        return self.preimages[path]

    def write_json(self, path, value):
        (self.root / path).write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")

    def check(self):
        return verify(self.root, self.read_before)

    def mutate_ordinary_row(self, field, value):
        path = SHARDS + "104-1.json"
        shard = json.loads((self.root / path).read_bytes())
        row = shard["questions"][0]
        row[field] = value
        self.write_json(path, shard)
        # Refresh local checksum/lock metadata so a test cannot pass merely
        # because the first SHA check caught an unrelated serialization change.
        lock = json.loads((self.root / LOCK).read_bytes())
        lock["mcq"][row["id"]] = row_hash(canonical_row(row, MCQ_FIELDS))
        self.write_json(LOCK, lock)
        manifest = json.loads((self.root / (SHARDS + "manifest.json")).read_bytes())
        raw = (self.root / path).read_bytes()
        entry = next(e for e in manifest["shards"] if e["file"] == "104-1.json")
        entry.update(bytes=len(raw), sha256=sha(raw))
        manifest["total_uncompressed_bytes"] = sum(e["bytes"] for e in manifest["shards"])
        manifest["dataset_revision"] = dataset_revision(manifest["shards"])
        self.write_json(SHARDS + "manifest.json", manifest)
        proof = json.loads((self.root / INTEGRATION).read_bytes())
        proof.update(dataset_revision=manifest["dataset_revision"],
                     manifest_total_bytes=manifest["total_uncompressed_bytes"])
        self.write_json(INTEGRATION, proof)

    def test_candidate(self):
        self.assertEqual(self.check()["unchanged"], 4787)

    def test_unrelated_answer_with_rehashed_manifest(self):
        self.mutate_ordinary_row("answer", "unauthorized")
        with self.assertRaisesRegex(ValueError, "unapproved row/answer/enrichment"):
            self.check()

    def test_unrelated_accepted_set(self):
        self.mutate_ordinary_row("accepted_answers", ["A", "B", "C", "D"])
        with self.assertRaisesRegex(ValueError, "unapproved row/answer/enrichment"):
            self.check()

    def test_unrelated_grading_mode(self):
        self.mutate_ordinary_row("grading_mode", "all_credit")
        with self.assertRaisesRegex(ValueError, "unapproved row/answer/enrichment"):
            self.check()

    def test_unrelated_core_with_refreshed_lock(self):
        self.mutate_ordinary_row("question", "unauthorized official wording")
        with self.assertRaisesRegex(ValueError, "unapproved row/answer/enrichment"):
            self.check()

    def test_unrelated_enrichment(self):
        self.mutate_ordinary_row("analysis", "unauthorized explanation")
        with self.assertRaisesRegex(ValueError, "unapproved row/answer/enrichment"):
            self.check()

    def test_essay_lock(self):
        lock = json.loads((self.root / LOCK).read_bytes())
        lock["essays"][next(iter(lock["essays"]))] = "0" * 64
        self.write_json(LOCK, lock)
        with self.assertRaisesRegex(ValueError, "essay lock"):
            self.check()

    def test_essay_source(self):
        with (self.root / "index.html").open("ab") as handle:
            handle.write(b"<!-- unexpected source change -->")
        with self.assertRaisesRegex(ValueError, "essay source changed"):
            self.check()

    def test_revision(self):
        manifest = json.loads((self.root / (SHARDS + "manifest.json")).read_bytes())
        manifest["dataset_revision"] = "invented"
        self.write_json(SHARDS + "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "builder identity"):
            self.check()

    def test_incorrect_before_proof(self):
        path = SOURCE_PROOFS[0][1]
        source = json.loads((self.root / path).read_bytes())
        source["changes"][0]["fields"]["opt_d"]["before"] = "incorrect preimage"
        self.write_json(path, source)
        with self.assertRaisesRegex(ValueError, "field preimage"):
            self.check()

    def test_missing_baseline(self):
        with self.assertRaisesRegex(ValueError, "baseline unavailable"):
            baseline_reader(ROOT, "0" * 40)(LOCK)

    def test_duplicate_shard(self):
        manifest = json.loads((self.root / (SHARDS + "manifest.json")).read_bytes())
        manifest["shards"][1] = deepcopy(manifest["shards"][0])
        manifest["dataset_revision"] = dataset_revision(manifest["shards"])
        self.write_json(SHARDS + "manifest.json", manifest)
        proof = json.loads((self.root / INTEGRATION).read_bytes())
        proof["dataset_revision"] = manifest["dataset_revision"]
        self.write_json(INTEGRATION, proof)
        with self.assertRaisesRegex(ValueError, "shard identity"):
            self.check()


if __name__ == "__main__":
    unittest.main()
