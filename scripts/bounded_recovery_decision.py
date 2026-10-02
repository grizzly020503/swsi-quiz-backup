#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

POLICY_PATH=Path('data/bounded_recovery_policy.v1.json')
REQUIRED_FAILURE_FIELDS={'retryable','max_attempts','backoff_class','scope','cost_class','exhausted_action','core_status','enhancement_status'}
ALLOWED_ACTIONS={'retry','preserve_last_known_good','quarantine','rollback_required','manual_required','degrade_enhancement'}
ALLOWED_COST={'low','medium','high'}
REQUIRED_FAILURES={
    'transient_timeout','rate_limited_429','upstream_5xx','source_unavailable','stale_job',
    'candidate_validation_failed','preview_failed','post_deploy_smoke_failed','quota_exhausted','ai_unavailable',
    'official_core_change','auth_rls_secret_change','destructive_schema_change','paid_service_change','unknown_migration_state'
}
OWNER_REQUIRED={'official_core_change','auth_rls_secret_change','destructive_schema_change','paid_service_change','unknown_migration_state'}

def load_policy(root: Path) -> dict:
    data=json.loads((root/POLICY_PATH).read_text(encoding='utf-8'))
    validate_policy(data)
    return data

def validate_policy(data: dict):
    if data.get('schema_version')!=1: raise ValueError('schema_version must be 1')
    g=data.get('global',{})
    must_true={'preserve_last_known_good','production_publish_requires_external_authorization'}
    must_false={'contract_may_self_authorize_publish','automatic_blind_database_rollback','automatic_paid_service_activation','automatic_qa_lowering','automatic_official_core_mutation'}
    for k in must_true:
        if g.get(k) is not True: raise ValueError(f'global {k} must be true')
    for k in must_false:
        if g.get(k) is not False: raise ValueError(f'global {k} must be false')
    fc=data.get('failure_classes',{})
    missing=REQUIRED_FAILURES-set(fc)
    if missing: raise ValueError(f'missing failure classes: {sorted(missing)}')
    for name,row in fc.items():
        if not isinstance(row,dict): raise ValueError(f'{name}: rule must be object')
        miss=REQUIRED_FAILURE_FIELDS-set(row)
        if miss: raise ValueError(f'{name}: missing fields {sorted(miss)}')
        ma=row['max_attempts']
        if not isinstance(ma,int) or isinstance(ma,bool) or ma<0 or ma>5:
            raise ValueError(f'{name}: max_attempts must be bounded 0..5')
        if row['retryable'] is False and ma!=0: raise ValueError(f'{name}: non-retryable must have max_attempts=0')
        if row['retryable'] is True and ma<1: raise ValueError(f'{name}: retryable must have max_attempts>=1')
        if row['cost_class'] not in ALLOWED_COST: raise ValueError(f'{name}: invalid cost_class')
        if row['exhausted_action'] not in ALLOWED_ACTIONS-{'retry'}:
            raise ValueError(f'{name}: invalid exhausted_action')
    for name in OWNER_REQUIRED:
        if fc[name].get('owner_required') is not True: raise ValueError(f'{name}: owner_required must be true')
    sm=data.get('release_state_machine',{})
    normal=sm.get('normal_path',[])
    expected=['candidate','isolated_verified','preview_verified','publish_authorized','published','postcheck_verified']
    if normal!=expected: raise ValueError('normal release path changed')
    pa=sm.get('publish_authorization_transition',{})
    if pa.get('from')!='preview_verified' or pa.get('to')!='publish_authorized' or pa.get('requires_external_authorization') is not True:
        raise ValueError('publish authorization transition must require external authorization')
    terminals=set(sm.get('failure_terminals',[]))
    if terminals!={'quarantine','preserve_last_known_good','rollback_required','manual_required'}:
        raise ValueError('failure terminal set changed')
    rb=data.get('rollback_boundaries',{})
    if 'no_blind_automatic_downgrade' not in rb.get('database',''):
        raise ValueError('database rollback boundary must forbid blind automatic downgrade')
    if 'official_evidence' not in rb.get('official_answer_correction',''):
        raise ValueError('official answer correction must require official evidence')

def decide_failure(policy: dict, failure_class: str, attempts_used: int=0) -> dict:
    if attempts_used<0: raise ValueError('attempts_used must be >=0')
    try: row=policy['failure_classes'][failure_class]
    except KeyError: raise ValueError(f'unknown failure_class: {failure_class}')
    max_attempts=row['max_attempts']
    retry=row['retryable'] and attempts_used<max_attempts
    action='retry' if retry else row['exhausted_action']
    return {
        'failure_class':failure_class,
        'attempts_used':attempts_used,
        'max_attempts':max_attempts,
        'remaining_attempts':max(0,max_attempts-attempts_used),
        'retry_allowed':bool(retry),
        'backoff_class':row['backoff_class'] if retry else 'none',
        'action':action,
        'core_status':row['core_status'],
        'enhancement_status':row['enhancement_status'],
        'owner_required':bool(row.get('owner_required',False)),
        'production_publish_authorized':False,
        'preserve_last_known_good':action in {'preserve_last_known_good','quarantine','rollback_required','manual_required','degrade_enhancement'} or policy['global']['preserve_last_known_good'],
        'cost_class':row['cost_class'],
        'scope':row['scope']
    }

def can_transition(policy: dict, current: str, target: str, external_publish_authorization: bool=False) -> dict:
    normal=policy['release_state_machine']['normal_path']
    allowed=False; reason='transition_not_allowed'
    if current in normal and target in normal:
        i=normal.index(current)
        if i+1<len(normal) and normal[i+1]==target:
            if current=='preview_verified' and target=='publish_authorized':
                allowed=bool(external_publish_authorization)
                reason='external_authorization_present' if allowed else 'external_authorization_required'
            else:
                allowed=True; reason='normal_verified_transition'
    if target in policy['release_state_machine']['failure_terminals']:
        allowed=True; reason='failure_terminal_transition'
    return {
        'from':current,'to':target,'allowed':allowed,'reason':reason,
        'external_publish_authorization_consumed':bool(allowed and current=='preview_verified' and target=='publish_authorized' and external_publish_authorization),
        'contract_generated_authorization':False
    }

def main():
    ap=argparse.ArgumentParser(description='SWSI bounded recovery/degradation decision evaluator')
    ap.add_argument('--root',default='.')
    ap.add_argument('--failure-class')
    ap.add_argument('--attempts-used',type=int,default=0)
    ap.add_argument('--transition',nargs=2,metavar=('FROM','TO'))
    ap.add_argument('--external-publish-authorization',action='store_true')
    ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); root=Path(a.root).resolve()
    try:
        policy=load_policy(root)
        if a.failure_class: result=decide_failure(policy,a.failure_class,a.attempts_used)
        elif a.transition: result=can_transition(policy,a.transition[0],a.transition[1],a.external_publish_authorization)
        else: result={'status':'pass','failure_class_count':len(policy['failure_classes']),'schema_version':1}
    except (OSError,ValueError,json.JSONDecodeError) as e:
        print(f'FAIL: {e}',file=sys.stderr); return 2
    if a.json: print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    else: print(result)
    return 0
if __name__=='__main__': raise SystemExit(main())
