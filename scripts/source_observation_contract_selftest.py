"""Offline regressions for transport and correction trust boundaries."""
import unittest
from source_observation_contract import fixture

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.trusted = fixture()['observation']['last_trusted_hash']

    def test_redirects_and_304_never_replace(self):
        for status in (301, 302, 303, 304, 307, 308):
            with self.subTest(status=status):
                row = fixture(http_status=status, previous_trusted_hash=self.trusted)['observation']
                self.assertEqual(row['outcome'], 'invalid_content')
                self.assertFalse(row['replacement_allowed'])
                self.assertEqual(row['last_trusted_hash'], self.trusted)

    def test_unverified_predecessors_never_replace(self):
        for predecessor, trusted in [('not-a-hash', self.trusted), ('f'*64, None),
                                     ('f'*64, self.trusted), (self.trusted, self.trusted)]:
            with self.subTest(predecessor=predecessor, trusted=trusted):
                row = fixture(correction_from_hash=predecessor,
                              previous_trusted_hash=trusted)['observation']
                self.assertEqual(row['outcome'], 'invalid_content')
                self.assertFalse(row['replacement_allowed'])
                self.assertEqual(row['last_trusted_hash'], trusted)

    def test_valid_correction_retains_chain(self):
        result = fixture(body=b'beta', decoded_text='beta', correction_from_hash=self.trusted,
                         previous_trusted_hash=self.trusted)
        self.assertEqual(result['observation']['outcome'], 'correction_detected')
        self.assertTrue(result['observation']['replacement_allowed'])
        self.assertEqual(result['provenance']['supersedes_hash'], self.trusted)
        self.assertNotEqual(result['observation']['last_trusted_hash'], self.trusted)

    def test_failure_cannot_promote_even_linked_correction(self):
        row = fixture(transport='timeout', http_status=None, body=None, decoded_text=None,
                      previous_trusted_hash=self.trusted, correction_from_hash=self.trusted)['observation']
        self.assertEqual(row['outcome'], 'source_unavailable')
        self.assertFalse(row['replacement_allowed'])
        self.assertEqual(row['last_trusted_hash'], self.trusted)

if __name__ == '__main__':
    unittest.main()
