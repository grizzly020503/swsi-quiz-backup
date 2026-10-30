#!/usr/bin/env python3
"""Five exact source-backed segmentation/font dispositions; no human approval.

This module never rewrites questions, raw PDF comparison rows or source answers.
All other review identities remain held. It requires the verified combined bytes.
"""
import hashlib
import json
from pathlib import Path
from official_essay_pdf_audit import normalize

ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = 'audit/official_pdf_review_dispositions_20261029.json'
PROOF_SHA256 = '5a14af11b474b0eed85e2a607e4b921473f83f0dedae75e17d5f210181e125dd'
DISPOSITION_IDS = {'DS-113-2-13', 'R-105-2-12', 'R-105-2-16', 'R-105-2-20', 'R-107-2-08'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_item(observed, item, current, registry):
    ident = item['id']
    require(ident in DISPOSITION_IDS and observed['id'] == current['id'] == ident, 'disposition identity')
    require(observed['status'] == 'review' and observed.get('answer_difference') is None and observed.get('answer_comparison_completed') is True, 'unresolved answer difference')
    require(observed['exam_code'] == current['source_exam_code'] and observed['subject'] == current['subject'], 'source identity drift')
    require(digest(observed) == item['baseline_comparison_row_sha256'] and observed['text_differences'] == item['baseline_differences'], 'baseline comparison drift')
    require(digest(current) == item['current_full_row_sha256'], 'current row drift')
    from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS
    require(row_hash(canonical_row(current, MCQ_FIELDS)) == item['current_core_lock_sha256'], 'current core drift')
    require(all(current.get(k) == item[v] for k,v in [('answer','official_answer'), ('accepted_answers','accepted_answers'), ('grading_mode','grading_mode')]), 'disposition grading drift')
    require(item['human_approval'] is False, 'false human approval')
    from audit_moex_source_subjects import require_source
    source = require_source(registry, current['source_exam_code'], current['subject'], item['source_url'])
    require(source['pdf_sha256'] == item['pdf_sha256'] == observed['question_pdf_sha256'] and item['source_url'] == observed['question_source_url'], 'disposition PDF source mismatch')
    expected_pages = {'DS-113-2-13':('6-3',3), 'R-105-2-12':('4-2',2), 'R-105-2-16':('4-2 / 4-3',2), 'R-105-2-20':('4-3',3), 'R-107-2-08':('4-2',2)}
    require((item['printed_page'], item['pdf_page_number']) == expected_pages[ident], 'wrong official page')
    diffs = observed['text_differences']
    require(item['official_field_transcription'] == {f:current[f] for f in diffs}, 'transcription drift')
    if ident == 'R-107-2-08':
        require(item['classification'] == 'circled_glyph_extraction', 'wrong glyph disposition')
        printed = {'opt_a':'僅①④','opt_b':'僅②③','opt_c':'①②④','opt_d':'②③④'}
        parsed = {'opt_a':'僅11','opt_b':'僅22','opt_c':'121','opt_d':'221'}
        require(set(diffs) == set(printed) and all(current[f] == printed[f] and diffs[f]['official_extraction'] == parsed[f] for f in printed), 'unverified circled glyph mapping')
    elif ident == 'DS-113-2-13':
        require(item['classification'] == 'original_figure_text_segmentation' and set(diffs) == {'question'}, 'wrong figure disposition')
        require(current['question'] == '有關下圖案母與案主之間的關係狀況，下列何者正確？', 'unverified figure stem')
        require(normalize(diffs['question']['official_extraction']) == normalize(current['question'] + '1970結婚寵物:狗'), 'unverified figure text segmentation')
    else:
        require(item['classification'] == 'shared_context_segmentation', 'wrong context disposition')
        require(set(diffs) == ({'question','opt_d'} if ident == 'R-105-2-20' else {'opt_d'}), 'unreviewed context field')
        official = diffs['opt_d']['official_extraction']
        prefix, sep, context = official.partition('情況:')
        require(sep and normalize(prefix) == normalize(current['opt_d']), 'unverified option boundary')
        bounds = {'R-105-2-12':('13','16'), 'R-105-2-16':('17','19'), 'R-105-2-20':('21','22')}
        first,last = bounds[ident]
        require(normalize('回答下列第'+first+'題至第'+last+'題') in normalize(context), 'wrong dependent context range')
        if 'question' in diffs:
            require(normalize(current['question']) == normalize(diffs['question']['official_extraction']), 'unverified corrected wording')


def validated_ids(report, root=ROOT):
    root = Path(root)
    raw = (root / PROOF_PATH).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PROOF_SHA256, 'disposition proof drift')
    proof = json.loads(raw)
    require(proof['count'] == len(proof['rows']) == 5 and {r['id'] for r in proof['rows']} == DISPOSITION_IDS, 'disposition scope drift')
    require(all(proof[k] is False for k in ('human_approval','release_approved','official_core_modified')), 'disposition approval drift')
    # Bind the raw report independently; a future re-audit needs a new review.
    require(proof['comparison_sha256'] == hashlib.sha256((root / 'audit/official_mcq_pdf_comparison_20261025.json').read_bytes()).hexdigest(), 'raw comparison fingerprint drift')
    from official_combined_candidate_guard import view
    view(root)  # Verify current 41-row artifacts before reading actual rows.
    manifest = json.loads((root / 'cdn/question-shards/manifest.json').read_text())
    current = {q['id']:q for e in manifest['shards'] for q in json.loads((root / 'cdn/question-shards' / e['file']).read_text())['questions']}
    from audit_moex_source_subjects import load_registry
    registry = load_registry()
    observed = {r['id']:r for r in report['rows']}
    for item in proof['rows']:
        validate_item(observed[item['id']], item, current[item['id']], registry)
    # Context removed from options must remain attached to dependent questions.
    for proof_name, groups in [('audit/official_105_2_shared_context_20261028.json', [('13-16',[13,14,15,16]), ('21-22',[21,22])])]:
        source = json.loads((root / proof_name).read_text())
        for group, numbers in groups:
            for number in numbers:
                require(current['R-105-2-'+str(number).zfill(2)]['question'].startswith(source['shared_contexts'][group]+'\n\n'), 'lost dependent shared context')
    return set(DISPOSITION_IDS)
