"""Offline regressions: only fresh positive evidence resolves an incident."""
import unittest
from ops_independent_heartbeat import COMPONENTS, evaluate, parse_time

NOW = parse_time('2026-10-02T12:00:00Z')

def heartbeat():
    return {'schema_version': 1, 'producer': 'fixture',
            'generated_at': '2026-10-02T11:30:00Z', 'components': {
                n: {'status': 'healthy', 'checked_at': '2026-10-02T11:30:00Z', 'scope': n}
                for n in COMPONENTS}}

def run(hb, prev=None, site_ok=None):
    return evaluate(hb, NOW, 8, 5, prev or {}, False, site_ok)

def previous(report):
    return {i['incident_key']: i for i in report['incidents']}

class RecoveryTests(unittest.TestCase):
    def failed(self):
        hb = heartbeat()
        hb['components']['grading'].update(status='failed', failure_class='grading_contract_failed')
        return hb, run(hb)

    def test_stale_components(self):
        for name in COMPONENTS:
            with self.subTest(component=name):
                hb = heartbeat()
                hb['components'][name]['checked_at'] = '2026-09-01T00:00:00Z'
                self.assertTrue(any(i['component'] == name and i['failure_class'] == 'component_stale'
                                    for i in run(hb)['incidents']))

    def test_freshness_boundary(self):
        hb = heartbeat()
        hb['components']['grading']['checked_at'] = '2026-10-02T04:00:00Z'
        self.assertEqual(run(hb)['overall_status'], 'healthy')
        hb['components']['grading']['checked_at'] = '2026-10-02T03:59:59Z'
        self.assertEqual(run(hb)['overall_status'], 'unavailable')

    def test_failure_unknown_failure_recovery(self):
        hb, first = self.failed()
        lost = run({'schema_version': 9}, previous(first))
        self.assertFalse(lost['resolved_incidents'])
        retained = next(i for i in lost['incidents'] if i['component'] == 'grading')
        self.assertEqual(retained['first_seen_at'], first['incidents'][0]['first_seen_at'])
        self.assertEqual(retained['last_seen_at'], first['incidents'][0]['last_seen_at'])
        failed_again = run(hb, previous(lost))
        self.assertTrue(any(i['component'] == 'grading' and i['transition'] == 'ongoing'
                            for i in failed_again['incidents']))
        healthy = run(heartbeat(), previous(failed_again))
        self.assertFalse(healthy['incidents'])
        self.assertTrue(any(i['component'] == 'grading' for i in healthy['resolved_incidents']))

    def test_stale_or_future_envelope_cannot_resolve(self):
        _, first = self.failed()
        for timestamp in ('2026-09-01T00:00:00Z', '2026-10-03T00:00:00Z'):
            hb = heartbeat(); hb['generated_at'] = timestamp
            self.assertFalse(run(hb, previous(first))['resolved_incidents'])

    def test_missing_or_unknown_component_cannot_resolve(self):
        _, first = self.failed()
        hb = heartbeat(); del hb['components']['grading']
        self.assertFalse(run(hb, previous(first))['resolved_incidents'])
        hb = heartbeat(); hb['components']['grading']['status'] = 'unknown'
        self.assertFalse(run(hb, previous(first))['resolved_incidents'])

    def test_changed_scope_cannot_resolve(self):
        _, first = self.failed()
        hb = heartbeat(); hb['components']['grading']['scope'] = 'different-exam'
        self.assertFalse(run(hb, previous(first))['resolved_incidents'])

    def test_homepage_requires_own_positive_probe(self):
        first = run(heartbeat(), site_ok=False)
        self.assertFalse(run(heartbeat(), previous(first))['resolved_incidents'])
        recovered = run({'schema_version': 9}, previous(first), site_ok=True)
        self.assertTrue(any(i['scope'] == 'homepage' for i in recovered['resolved_incidents']))
        self.assertTrue(any(i['failure_class'] == 'invalid_heartbeat' for i in recovered['incidents']))

if __name__ == '__main__':
    unittest.main()
