#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

REGISTRY=Path('data/service_responsibility_registry.v1.json')
SURVIVAL=Path('data/minimum_survival_contract.v1.json')
SENSITIVE_KEYS={
    'name','email','account_id','account_identifier','password','token','secret','api_key',
    'service_role_key','mfa','mfa_secret','recovery_code','credential','credential_value',
    'username','user_id','phone','phone_number'
}
REQUIRED_SERVICE_FIELDS={
    'service_id','purpose','owner_role','criticality','core_or_enhancement',
    'recovery_reference','renewal_type','fallback','credential_policy'
}
ALLOWED_CREDENTIAL_POLICIES={'external_secret_only','none_expected_for_public_source'}
REQUIRED_HUMAN_ONLY={
    'account_succession','provider_new_terms_acceptance','major_security_incident_response',
    'new_paid_obligation','disputed_official_content','destructive_migration','credential_scope_expansion'
}
REQUIRED_FORBIDDEN={
    'auto_payment','auto_account_takeover','accept_provider_terms','delete_review_queue_to_clear_backlog',
    'lower_qa_thresholds','mark_unresolved_content_verified','publish_disputed_official_content',
    'destructive_schema_migration','expand_credential_scope'
}
REQUIRED_SCENARIOS={
    'maintainer_absent','account_recovery_pending','ai_unavailable','paid_decision_pending','disputed_update'
}
EMAILISH=re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')

def load(path: Path) -> dict:
    obj=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj,dict): raise ValueError(f'{path}: root must be object')
    return obj

def walk_sensitive(obj, path='$'):
    if isinstance(obj,dict):
        for k,v in obj.items():
            nk=str(k).strip().lower()
            if nk in SENSITIVE_KEYS:
                raise ValueError(f'sensitive field key forbidden: {path}.{k}')
            walk_sensitive(v,f'{path}.{k}')
    elif isinstance(obj,list):
        for i,v in enumerate(obj): walk_sensitive(v,f'{path}[{i}]')
    elif isinstance(obj,str) and EMAILISH.search(obj):
        raise ValueError(f'email-like value forbidden: {path}')

def validate_registry(root: Path, registry: dict):
    if registry.get('schema_version')!=1: raise ValueError('registry schema_version must be 1')
    if registry.get('credential_policy')!='external_secret_only':
        raise ValueError('registry credential_policy must be external_secret_only')
    services=registry.get('services')
    if not isinstance(services,list) or not services: raise ValueError('services must be non-empty list')
    ids=set()
    for i,row in enumerate(services):
        if not isinstance(row,dict): raise ValueError(f'service[{i}] must be object')
        missing=REQUIRED_SERVICE_FIELDS-set(row)
        if missing: raise ValueError(f'service[{i}] missing fields: {sorted(missing)}')
        sid=row['service_id']
        if not isinstance(sid,str) or not sid: raise ValueError(f'service[{i}] invalid service_id')
        if sid in ids: raise ValueError(f'duplicate service_id: {sid}')
        ids.add(sid)
        if row['core_or_enhancement'] not in {'core','enhancement'}:
            raise ValueError(f'{sid}: invalid core_or_enhancement')
        if row['criticality'] not in {'critical','high','medium','low'}:
            raise ValueError(f'{sid}: invalid criticality')
        if row['credential_policy'] not in ALLOWED_CREDENTIAL_POLICIES:
            raise ValueError(f'{sid}: invalid credential_policy')
        refs=row['recovery_reference']
        if not isinstance(refs,list) or not refs: raise ValueError(f'{sid}: recovery_reference required')
        for ref in refs:
            if not isinstance(ref,str) or not ref: raise ValueError(f'{sid}: invalid recovery reference')
            if not (root/ref).is_file(): raise ValueError(f'{sid}: recovery reference missing: {ref}')
        if not row['owner_role'] or not row['fallback']:
            raise ValueError(f'{sid}: owner_role and fallback must be non-empty')
    return ids

def validate_survival(survival: dict):
    if survival.get('schema_version')!=1: raise ValueError('survival schema_version must be 1')
    if survival.get('mode')!='last_verified_updates_paused':
        raise ValueError('survival mode must be last_verified_updates_paused')
    if not survival.get('core_capabilities'): raise ValueError('core_capabilities required')
    disclosure=survival.get('freshness_disclosure')
    if not isinstance(disclosure,dict) or disclosure.get('required') is not True:
        raise ValueError('freshness disclosure must be required')
    fields=set(disclosure.get('required_fields',[]))
    for need in {'last_verified_revision','content_last_verified_at','updates_paused_since','pause_reason_class'}:
        if need not in fields: raise ValueError(f'freshness disclosure missing {need}')
    if disclosure.get('must_not_claim_active_updates_when_paused') is not True:
        raise ValueError('paused mode must not claim active updates')
    if not REQUIRED_HUMAN_ONLY.issubset(set(survival.get('human_only_decisions',[]))):
        raise ValueError('human_only_decisions missing required boundary')
    if not REQUIRED_FORBIDDEN.issubset(set(survival.get('forbidden_automation',[]))):
        raise ValueError('forbidden_automation missing required boundary')
    scenarios=survival.get('scenario_expectations',{})
    if not REQUIRED_SCENARIOS.issubset(set(scenarios)):
        raise ValueError('scenario expectations incomplete')
    inv=survival.get('invariants',{})
    required_true={
        'official_core_must_not_be_silently_changed','review_queue_must_be_preserved',
        'unresolved_content_must_not_be_promoted_to_verified',
        'enhancement_failure_must_not_be_reported_as_core_failure_when_core_remains_usable',
        'freshness_must_be_disclosed'
    }
    for key in required_true:
        if inv.get(key) is not True: raise ValueError(f'invariant must be true: {key}')

def validate(root: Path, registry_path: Path|None=None, survival_path: Path|None=None):
    rp=registry_path or root/REGISTRY; sp=survival_path or root/SURVIVAL
    registry=load(rp); survival=load(sp)
    walk_sensitive(registry,'registry'); walk_sensitive(survival,'survival')
    service_ids=validate_registry(root,registry); validate_survival(survival)
    return {
        'schema_version':1,
        'mode':survival['mode'],
        'service_count':len(service_ids),
        'core_capability_count':len(survival['core_capabilities']),
        'human_only_decision_count':len(survival['human_only_decisions']),
        'forbidden_automation_count':len(survival['forbidden_automation']),
        'scenario_count':len(survival['scenario_expectations']),
        'status':'pass'
    }

def main():
    ap=argparse.ArgumentParser(description='Validate SWSI non-sensitive succession and minimum-survival contracts')
    ap.add_argument('--root',default='.')
    ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); root=Path(a.root).resolve()
    try: result=validate(root)
    except (OSError,ValueError,json.JSONDecodeError) as e:
        print(f'FAIL: {e}',file=sys.stderr); return 2
    if a.json: print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    else: print('MAINTAINER SURVIVAL CONTRACT OK',result)
    return 0
if __name__=='__main__': raise SystemExit(main())
