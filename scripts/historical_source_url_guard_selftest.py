#!/usr/bin/env python3
"""Offline positive/negative checks of exact official PDF source provenance."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from historical_source_url_guard import REGISTRY, load_registry, url_identity, validate_historical_source_urls

ROOT = Path(__file__).resolve().parents[1]


class HistoricalSourceUrlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for year in range(104, 116):
            for rd in (1, 2):
                payload = json.loads((ROOT / f"cdn/question-shards/{year}-{rd}.json").read_text(encoding="utf-8"))
                cls.rows.extend(payload["questions"])

    def test_all_4800_shard_sources_match_verified_pdfs(self):
        self.assertEqual(len(self.rows), 4800)
        self.assertEqual(validate_historical_source_urls(self.rows), 4800)

    def rejects(self, key, mutated_url=None, mutated_code=None):
        rows = [dict(x) for x in self.rows]
        victim = next(x for x in rows if str(x.get("year")) == key[0] and x.get("subject") == key[1])
        if mutated_url is not None:
            victim["source_url"] = mutated_url
        if mutated_code is not None:
            victim["source_exam_code"] = mutated_code
        with self.assertRaisesRegex(RuntimeError, "BLOCKED: historic Supabase MOEX source URLs"):
            validate_historical_source_urls(rows)

    def test_old_exam_category_alias_rejected(self):
        item = next(x for x in self.rows if x["year"] == "104" and x["subject"] == "社會工作")
        self.rejects(("104", "社會工作"), item["source_url"].replace("c=110", "c=103"))

    def test_pre115_wrong_subject_rejected(self):
        item = next(x for x in self.rows if x["year"] == "112" and x["round"] == "第一次" and x["subject"] == "社會政策與社會立法")
        self.rejects(("112", "社會政策與社會立法"), item["source_url"].replace("s=0304", "s=0303"))

    def test_new115_scheme_must_not_receive_old_s_mapping(self):
        item = next(x for x in self.rows if x["year"] == "115" and x["round"] == "第一次" and x["subject"] == "社會政策與社會立法")
        self.rejects(("115", "社會政策與社會立法"), item["source_url"].replace("s=0303", "s=0304"))

    def test_exam_code_and_host_tampering_rejected(self):
        self.rejects(("112", "社會工作"), mutated_code="000000")
        self.rejects(("112", "社會工作"), mutated_url="https://elsewhere.invalid/exam/123")

    def test_duplicate_parameters_and_fragment_rejected(self):
        with self.assertRaises(ValueError):
            url_identity("https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&c=104&code=115030&q=1&s=0301&t=Q")
        with self.assertRaises(ValueError):
            url_identity("https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=115030&q=1&s=0301&t=Q#bad")

    def test_falsely_verified_registry_rejected(self):
        source = json.loads(REGISTRY.read_text(encoding="utf-8"))
        source["records"][0]["pdf_header"] = source["records"][0]["pdf_header"].replace("科  目：", "INVALID")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "wrong PDF header subject"):
                load_registry(path)

    def test_future_exam_not_blocked_by_legacy_registry(self):
        future = copy.deepcopy(self.rows[0])
        future.update(year="116", round="第一次", id="FUTURE-NOT-OFFICIAL", source_exam_code="116030", source_url="https://example.invalid/future")
        self.assertEqual(validate_historical_source_urls(self.rows + [future]), 4800)


if __name__ == "__main__":
    unittest.main()
