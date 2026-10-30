#!/usr/bin/env python3
"""Exercise resume, tampering, stale input and interruption with real queue data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import official_pdf_batch_pipeline as pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)/'state'
        raw=json.loads((pipeline.ROOT/'audit/official_mcq_pdf_comparison_20261025.json').read_text())
        rows=[r for r in raw['rows'] if r['status']=='review'][:3]
        self.queue={'rows':[{'id':r['id'],'kind':'mcq','priority':0,'pdf_sha256':r['question_pdf_sha256'],'status':'review','human_approval':False} for r in rows],'unresolved':3}

    def run_pipeline(self,**kwargs):
        return pipeline.execute(self.out,verify=False,reproduce=False,**kwargs)

    def test_real_queue_remains_held(self):
        from official_pdf_review_queue import build
        from official_pdf_text_release_gate import inspect
        q=build();self.assertEqual(q['unresolved'],sum(inspect().values()))
        self.assertTrue(all(r['status']=='review' and not r['human_approval'] for r in q['rows']))

    def test_no_repository_output(self):
        with self.assertRaisesRegex(ValueError,'outside checkout'):pipeline.external_output(pipeline.ROOT/'audit'/'unsafe')

    def test_source_host_and_scheme(self):
        for url in ['http://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx','https://evil.test/exam/wHandExamQandA_File.ashx','https://wwwq.moex.gov.tw@evil.test/exam/wHandExamQandA_File.ashx','https://wwwq.moex.gov.tw/admin']:
            with self.assertRaises(ValueError):pipeline.validate_url(url)

    def test_bad_pdf_rejected(self):
        source={'url':'https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?t=Q','exam_code':'1','c':'1','s':'1','pdf_sha256':'0'*64}
        work=Path(self.temp.name);(work/'1-1-1.pdf').write_bytes(b'%PDF-wrong')
        with self.assertRaisesRegex(ValueError,'hash/content mismatch'):pipeline.source_pdf(source,work,work)

    def test_checkpoint_resume_and_corrupt_packet_recovery(self):
        # Use actual official PDFs when running locally; CI uses deterministic public-shaped bytes.
        real_digest=pipeline.digest; known={}
        def source(source,work,*args):
            raw=('%PDF-test-'+source['pdf_sha256']).encode();known[raw]=source['pdf_sha256']
            path=work/'pdfs'/(source['pdf_sha256']+'.pdf');path.parent.mkdir(exist_ok=True);path.write_bytes(raw);return path,'fixture'
        def hashed(raw):return known.get(raw,real_digest(raw))
        with patch('official_pdf_review_queue.build',return_value=self.queue),patch.object(pipeline,'source_pdf',side_effect=source),patch.object(pipeline,'digest',side_effect=hashed):
            first=self.run_pipeline(batch_size=1,max_batches=1);self.assertEqual(first['prepared_packets'],1)
            second=self.run_pipeline();self.assertEqual(second['reused_packets'],1);self.assertEqual(second['prepared_packets'],3)
            work=Path(second['work_directory']);packet=next((work/'packets').glob('*.json'));packet.write_text('{}')
            third=self.run_pipeline();self.assertEqual(third['new_packets'],1);self.assertEqual(third['prepared_packets'],3)
            self.assertEqual(third['release_status'],'NO-GO');self.assertEqual(third['unresolved_official_reviews'],3)

    def test_abrupt_interruption_preserves_completed_record(self):
        real_digest=pipeline.digest; real_atomic=pipeline.atomic; known={}
        def source(source,work,*args):
            raw=('%PDF-test-'+source['pdf_sha256']).encode();known[raw]=source['pdf_sha256']
            path=work/'pdfs'/(source['pdf_sha256']+'.pdf');path.parent.mkdir(exist_ok=True);path.write_bytes(raw);return path,'fixture'
        def interrupted(path,value):
            real_atomic(path,value)
            if path.name=='checkpoint.json' and len(value['packets'])==1:raise KeyboardInterrupt()
        with patch('official_pdf_review_queue.build',return_value=self.queue),patch.object(pipeline,'source_pdf',side_effect=source),patch.object(pipeline,'digest',side_effect=lambda raw:known.get(raw,real_digest(raw))):
            with patch.object(pipeline,'atomic',side_effect=interrupted):
                with self.assertRaises(KeyboardInterrupt):self.run_pipeline()
            result=self.run_pipeline();self.assertEqual(result['reused_packets'],1);self.assertEqual(result['prepared_packets'],3)

    def test_per_run_source_budget(self):
        with patch('official_pdf_review_queue.build',return_value=self.queue),patch.object(pipeline,'source_pdf',side_effect=ValueError('offline')) as source:
            result=self.run_pipeline(max_sources=1)
            self.assertEqual(source.call_count,1)
            self.assertEqual(result['prepared_packets'],0)
            self.assertEqual(result['not_yet_prepared'],3)

    def test_source_failure_is_not_completion_and_can_retry(self):
        with patch('official_pdf_review_queue.build',return_value=self.queue),patch.object(pipeline,'source_pdf',side_effect=ValueError('source unavailable')):
            result=self.run_pipeline();self.assertEqual(result['prepared_packets'],0);self.assertGreater(result['failed_records_this_run'],0)

    def test_input_change_aborts_publication(self):
        with patch('official_pdf_review_queue.build',return_value={'rows':[],'unresolved':0}),patch.object(pipeline,'inputs',side_effect=[('a',{}),('b',{})]):
            with self.assertRaisesRegex(ValueError,'inputs changed'):self.run_pipeline()
            self.assertFalse((self.out/'latest.json').exists())

    def test_required_checks_cannot_be_skipped_by_checkpoint(self):
        with patch.object(pipeline,'checks',side_effect=RuntimeError('guard failed')):
            with self.assertRaisesRegex(RuntimeError,'guard failed'):pipeline.execute(self.out,reproduce=False)

    def test_process_lock_prevents_overlap(self):
        self.out.mkdir();guard=(self.out/'pipeline.lock').open('a');self.addCleanup(guard.close)
        pipeline.fcntl.flock(guard,pipeline.fcntl.LOCK_EX|pipeline.fcntl.LOCK_NB)
        with self.assertRaises(BlockingIOError):self.run_pipeline()


if __name__=='__main__':unittest.main()
