#!/usr/bin/env python3
"""Trace eight source-backed P0 candidates to original PDF-review evidence.

This is a non-clearing regression. It NEVER asserts that official PDF text
review, independent human signoff, production writes or deployment completed.
The large historical 4,800-row comparison remains pinned in PR #447 and is
NOT copied or silently rewritten by this focused crosswalk.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'audit/official_eight_p0_pdf_review_crosswalk_20261031.json'
PROOF_TWO = ROOT / 'audit/official_two_row_p0_candidate_20261031.json'
PROOF_SIX = ROOT / 'audit/official_111_2_shared_context_six_20261031.json'
ID_SET = {
    'DS-108-2-23','R-114-1-17',
    'R-111-2-14','R-111-2-15','R-111-2-17',
    'R-111-2-18','R-111-2-29','R-111-2-30',
}
SOURCE_SHA = {
    'DS-108-2-23':'78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b',
    'R-114-1-17':'e2103e4eb154b5ac0c8de24026a7b35fe3a8370678f606356c919540c87646e2',
}
SOURCE_SHA.update({ident:'14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153'
                   for ident in ID_SET if ident.startswith('R-111-2-')})
GRADING = ('answer','accepted_answers','grading_mode','source_exam_code','source_url')
ENRICH = ('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw',
          'mnemonic','extension','law','mistake')

def validate(cross, full_rows, proofs, manifest):
    assert cross['schema_version'] == 1
    assert cross['status'] == 'HOLD_NO_AUTO_CLEAR'
    assert cross['source_baseline']['ref'] == '7cd99a23f98ecc62fa18f104f154084650bef9c8'
    assert cross['source_baseline']['mcq_comparison_blob_sha'] == 'f1821813830aff4ce811583c142c4a29f35dddf9'
    assert cross['source_baseline']['mcq_held'] == 441
    assert cross['source_baseline']['essay_held'] == 18
    cleared = cross['source_baseline']['cleared_legacy_ids']
    assert len(cleared) == len(set(cleared)) == cross['source_baseline']['legacy_evidence_dispositioned'] == 31
    assert cross['source_baseline']['legacy_remaining_mcq'] == 410
    assert cross['source_baseline']['legacy_remaining_combined'] == 428
    assert cross['unresolved_release_count_unchanged'] == 428
    assert cross['candidate']['affected_rows'] == 8
    assert cross['candidate']['source_prs'] == [496,498]
    # This crosswalk belongs to the verified eight-row parent revision.
    # The child three-row correction stages a separate source-bound overlay;
    # never rewrite the old crosswalk identity to pretend a new sign-off.
    child=json.loads((ROOT/'audit/official_next_three_p0_source_candidate_20261031.json').read_text())
    parent=json.loads(child['old_manifest_raw'])
    assert cross['candidate']['dataset_revision'] == parent['dataset_revision']
    assert child['dataset_revision_after'] == manifest['dataset_revision']
    assert cross['candidate']['staged_not_published'] is True
    assert cross['candidate']['production_write'] is False
    assert cross['candidate']['backup_site_changed'] is False
    assert len(full_rows) == len({r['id'] for r in full_rows})
    index = {r['id']:r for r in full_rows}
    assert len(proofs) == 8 and {p['id'] for p in proofs} == ID_SET
    targets = cross['targets']
    assert len(targets) == 8 and {t['id'] for t in targets} == ID_SET
    assert not ID_SET.intersection(cleared)
    proof_by_id = {p['id']:p for p in proofs}
    for row in targets:
        ident = row['id']
        original = proof_by_id[ident]['published_before']
        new = proof_by_id[ident]['published_after']
        assert index[ident] == new
        assert row['staged_question'] == new['question']
        assert row['staged_options'] == {k[4:]:new[k] for k in ('opt_a','opt_b','opt_c','opt_d')}
        assert row['staged_answer'] == new['answer']
        assert row['source_pdf_sha256'] == SOURCE_SHA[ident]
        assert row['original_comparison_status'] == 'review'
        assert row['official_answer_difference'] is None
        assert row['counted_as_cleared'] is False
        assert row['human_approval'] is False and row['release_approved'] is False
        assert row['staged_analysis_status'] == new['analysis_status'] == 'review'
        assert row['source_proof'].startswith('audit/official_')
        assert set(row['original_difference_fields']) == set(row['baseline_official_extraction_differences'])
        assert row['original_difference_fields']
        for field,change in row['baseline_official_extraction_differences'].items():
            # Source comparator's original stored text must match pinned
            # exact preimage; the extraction itself may be a PDF font artifact.
            assert change['stored'] == original[field]
            assert isinstance(change['official_extraction'],str)
        actually_changed = [k for k in new if new[k] != original[k]]
        assert set(row['staged_changed_fields']) == set(actually_changed)
        assert 'question' in actually_changed
        assert all(original[k] == new[k] for k in GRADING)
        assert all(new[k] is None for k in ENRICH)
        if ident.startswith('R-111-2-'):
            assert all(original[k] == new[k] for k in ('opt_a','opt_b','opt_c','opt_d'))
            assert row['origin_pr'] == 498
        else:
            assert row['origin_pr'] == 496

def main():
    cross = json.loads(AUDIT.read_text())
    proof_two=json.loads(PROOF_TWO.read_text())
    proof_six=json.loads(PROOF_SIX.read_text())
    proofs=proof_two['rows']+proof_six['changes']
    manifest=json.loads((ROOT/'cdn/question-shards/manifest.json').read_text())
    rows=[]
    for name in ('108-2.json','111-2.json','114-1.json'):
        payload=json.loads((ROOT/'cdn/question-shards'/name).read_text())
        assert payload['question_count']==len(payload['questions'])==200
        rows.extend(payload['questions'])
    validate(cross,rows,proofs,manifest)
    for kind in ('baseline','source','field','answer','approval','status','legacy-counter','unrelated-choice'):
        bogus=copy.deepcopy(cross)
        t=bogus['targets'][0]
        if kind=='baseline':t['baseline_official_extraction_differences']['question']['stored']+='X'
        elif kind=='source':t['source_pdf_sha256']='0'*64
        elif kind=='field':t['staged_question']+='X'
        elif kind=='answer':t['staged_answer']='D'
        elif kind=='approval':t['human_approval']=True
        elif kind=='status':t['counted_as_cleared']=True
        elif kind=='legacy-counter':bogus['unresolved_release_count_unchanged']=420
        elif kind=='unrelated-choice':bogus['targets'][2]['staged_options']['d']='fabricated'
        try:validate(bogus,rows,proofs,manifest)
        except (AssertionError,KeyError):pass
        else:raise AssertionError('Unauthorised official review mutation passed: '+kind)
    print('MOEX 8-ROW BASELINE CROSSWALK PASS: 8/8 verified candidate-to-original flagged IDs, 31 distinct old disposition identities, held 410 MCQ + 18 essay = 428, 8 tamper cases rejected; no auto-clear or production write')

if __name__=='__main__':
    main()
