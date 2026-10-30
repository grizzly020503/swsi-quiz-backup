#!/usr/bin/env python3
"""Regression tests for known legacy wrong-subject links and evidence tampering."""
import copy
import unittest

from audit_moex_source_subjects import (
    header_errors, index_matches, load_registry, require_source, url_identity, validate_record,
)


class SourceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry()

    def test_historical_class_code_and_changed_subject_order(self):
        for exam, subject, c, s in [
            ("104030", "社會政策與社會立法", "110", "0604"),
            ("111110", "社會工作研究方法", "105", "0406"),
            ("112030", "社會政策與社會立法", "103", "0304"),
            ("115030", "社會政策與社會立法", "103", "0303"),
        ]:
            row = self.registry[exam, subject]
            self.assertEqual((row["c"], row["s"]), (c, s))
            self.assertIs(require_source(self.registry, exam, subject, row["url"]), row)

    def test_wrong_but_downloadable_management_url_rejected(self):
        for exam in ("112030", "112110", "113030", "114030"):
            row = self.registry[exam, "社會政策與社會立法"]
            with self.assertRaises(ValueError):
                require_source(self.registry, exam, row["subject"], row["url"].replace("s=0304", "s=0303"))

    def test_url_syntax_does_not_promote_unobserved_exam(self):
        row = self.registry["115030", "社會工作"]
        with self.assertRaises(ValueError):
            require_source(self.registry, "116030", row["subject"], row["url"].replace("115030", "116030"))

    def test_no_cross_exam_or_subject_reuse(self):
        row = self.registry["115030", "社會政策與社會立法"]
        for exam, subject in (("112030", row["subject"]), ("115030", "社會工作管理")):
            with self.assertRaises(ValueError):
                require_source(self.registry, exam, subject, row["url"])

    def test_reordered_query_is_same_source(self):
        row = self.registry["115030", "社會政策與社會立法"]
        url = "https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=115030&q=1&s=0303&t=Q"
        self.assertIs(require_source(self.registry, row["exam_code"], row["subject"], url), row)

    def test_duplicate_credentials_fragments_and_answer_urls_rejected(self):
        url = self.registry["112030", "社會工作"]["url"]
        for bad in (url + "&s=0303", url + "#ignored", url.replace("t=Q", "t=A"),
                    url.replace("wwwq.moex.gov.tw", "wwwq.moex.gov.tw.evil.invalid"),
                    url.replace("https://", "https://name@")):
            with self.assertRaises(ValueError):
                url_identity(bad)

    def test_header_identity_must_match_exact_subject_session_and_paper(self):
        row = self.registry["112030", "社會工作"]
        self.assertFalse(header_errors(row, row["pdf_header"]))
        for old, new in (("社會工作\n", "社會工作管理\n"), ("112年", "113年"),
                         ("10310", "10320"), ("類  科：社會工作師", "類  科：護理師")):
            changed = row["pdf_header"].replace(old, new)
            self.assertNotEqual(changed, row["pdf_header"])
            self.assertTrue(header_errors(row, changed))

    def test_review_status_http_mime_and_hash_fail_closed(self):
        row = self.registry["112030", "社會工作"]
        for field, value in (("status", "review"), ("pdf_sha256", "0" * 64),
                             ("exam_code", "113030"), ("errors", ["unverified"])):
            changed = copy.deepcopy(row)
            changed[field] = value
            with self.assertRaises(ValueError):
                validate_record(changed)
        for key, value in (("mime", "text/html"), ("http_status", 403), ("fetch_status", "unverified_live")):
            changed = copy.deepcopy(row)
            changed["http"][key] = value
            with self.assertRaises(ValueError):
                validate_record(changed)

    def test_directory_title_and_url_must_both_match(self):
        row = self.registry["112030", "社會政策與社會立法"]
        good = f'<a title="另開視窗，開啓{row["subject"]}試題(Pdf檔)" href="{row["url"]}">試題</a>'
        self.assertTrue(index_matches(row, good))
        self.assertFalse(index_matches(row, good.replace(row["subject"], "社會工作管理")))
        self.assertFalse(index_matches(row, good.replace("s=0304", "s=0303")))


if __name__ == "__main__":
    unittest.main()
