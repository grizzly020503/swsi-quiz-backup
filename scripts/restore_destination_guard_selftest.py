#!/usr/bin/env python3
"""No network or DB calls. Run only inside the approved isolated QA runtime."""
import unittest
from restore_destination_guard import DestinationError, validate_connection, validate_identity

class DestinationGuardTests(unittest.TestCase):
    def setUp(self):
        self.env = {'SWSI_RESTORE_TARGET_KIND':'local',
                    'SWSI_RESTORE_TARGET_ID':'isolated-'+'a'*32,
                    'SWSI_RESTORE_TARGET_DB_URL':'postgresql://tester:synthetic@127.0.0.1:5432/disposable?connect_timeout=5&sslmode=disable'}

    def test_valid_local_identity(self):
        expected = validate_connection(self.env)
        validate_identity({'database':'disposable','target_id':self.env['SWSI_RESTORE_TARGET_ID'],'server_addr':'127.0.0.1'},expected)

    def test_ipv6_local(self):
        self.env['SWSI_RESTORE_TARGET_DB_URL']='postgresql://tester:synthetic@[::1]:5432/disposable'
        expected=validate_connection(self.env)
        validate_identity({'database':'disposable','target_id':expected['target_id'],'server_addr':'::1'},expected)

    def test_ambiguous_routing_rejected(self):
        base='postgresql://tester:synthetic@127.0.0.1:5432/disposable'
        bad=[base+'?host=example.invalid',base+'?hostaddr=192.0.2.1',base+'?service=other',
             base+'?options=-csearch_path=public',base+'?sslmode=disable&sslmode=require',
             base+'?connect_timeout=0',base+'?connect_timeout=31',base+'?connect_timeout',
             base+'#ignored',base.replace('127.0.0.1','localhost'),base.replace('127.0.0.1','example.invalid'),
             base.replace(':5432',''),base.replace('/disposable','/'),base.replace('tester:synthetic@',''),
             base.replace('/disposable','/database%0a'),base+'?%68ost=example.invalid']
        for uri in bad:
            with self.subTest(uri=uri), self.assertRaises(DestinationError):
                validate_connection({**self.env,'SWSI_RESTORE_TARGET_DB_URL':uri})

    def test_inherited_libpq_parameters_rejected(self):
        for key in ('PGHOST','PGHOSTADDR','PGSERVICE','PGSERVICEFILE','PGDATABASE','PGOPTIONS','PGPASSFILE','PGPORT'):
            with self.subTest(key=key),self.assertRaises(DestinationError):
                validate_connection({**self.env,key:''})

    def test_hosted_and_unmarked_targets_rejected(self):
        for values in ({'SWSI_RESTORE_TARGET_KIND':'hosted-isolated'}, {'SWSI_RESTORE_TARGET_ID':''}):
            with self.assertRaises(DestinationError):validate_connection({**self.env,**values})

    def test_identity_failure_rejected(self):
        expected=validate_connection(self.env)
        good={'database':'disposable','target_id':expected['target_id'],'server_addr':'127.0.0.1'}
        for payload in (None,{},[],{**good,'database':'other'},{**good,'target_id':'different'},
                        {**good,'server_addr':'192.0.2.1'},{**good,'server_addr':None},{**good,'extra':True}):
            with self.subTest(payload=payload),self.assertRaises(DestinationError):validate_identity(payload,expected)

if __name__=='__main__':unittest.main()
