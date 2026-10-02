#!/usr/bin/env python3
import importlib.util, json, tempfile
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('msc',ROOT/'scripts/maintainer_survival_contract.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def registry():
    return {
        'schema_version':1,'credential_policy':'external_secret_only','services':[{
            'service_id':'test_service','purpose':'fixture','owner_role':'maintainer_role','criticality':'high',
            'core_or_enhancement':'core','recovery_reference':['docs/recover.md'],'renewal_type':'human_only',
            'fallback':'last_verified','credential_policy':'external_secret_only'
        }]
    }

def survival():
    return {
        'schema_version':1,'mode':'last_verified_updates_paused','purpose':'fixture',
        'core_capabilities':['official_question_bank'],'core_condition':'fixture',
        'paused_or_degraded_enhancements':['ai_generation'],
        'freshness_disclosure':{'required':True,'required_fields':['last_verified_revision','content_last_verified_at','updates_paused_since','pause_reason_class'],'must_not_claim_active_updates_when_paused':True},
        'human_only_decisions':sorted(m.REQUIRED_HUMAN_ONLY),
        'allowed_automation':['read_only_health_checks'],
        'forbidden_automation':sorted(m.REQUIRED_FORBIDDEN),
        'invariants':{
            'official_core_must_not_be_silently_changed':True,
            'review_queue_must_be_preserved':True,
            'unresolved_content_must_not_be_promoted_to_verified':True,
            'enhancement_failure_must_not_be_reported_as_core_failure_when_core_remains_usable':True,
            'freshness_must_be_disclosed':True
        },
        'scenario_expectations':{k:'safe' for k in m.REQUIRED_SCENARIOS}
    }

def write(p,obj): p.write_text(json.dumps(obj),encoding='utf-8')

def expect_fail(root,r,s,needle):
    rp=root/'registry.json'; sp=root/'survival.json'; write(rp,r); write(sp,s)
    try: m.validate(root,rp,sp); raise AssertionError('expected failure')
    except ValueError as e: assert needle in str(e), (needle,str(e))

with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'docs').mkdir(); (root/'docs/recover.md').write_text('recovery',encoding='utf-8')
    rp=root/'registry.json'; sp=root/'survival.json'; write(rp,registry()); write(sp,survival())
    result=m.validate(root,rp,sp)
    assert result['status']=='pass' and result['mode']=='last_verified_updates_paused'

    r=registry(); r['services'][0]['email']='person@example.invalid'
    expect_fail(root,r,survival(),'sensitive field key forbidden')

    r=registry(); del r['services'][0]['owner_role']
    expect_fail(root,r,survival(),'missing fields')

    r=registry(); r['services'][0]['recovery_reference']=['docs/missing.md']
    expect_fail(root,r,survival(),'recovery reference missing')

    r=registry(); r['services'][0]['fallback']=''
    expect_fail(root,r,survival(),'owner_role and fallback')

    s=survival(); s['forbidden_automation'].remove('auto_payment')
    expect_fail(root,registry(),s,'forbidden_automation missing')

    s=survival(); del s['scenario_expectations']['ai_unavailable']
    expect_fail(root,registry(),s,'scenario expectations incomplete')

    s=survival(); s['freshness_disclosure']['must_not_claim_active_updates_when_paused']=False
    expect_fail(root,registry(),s,'must not claim active updates')

print('MAINTAINER SURVIVAL CONTRACT SELFTEST OK')
