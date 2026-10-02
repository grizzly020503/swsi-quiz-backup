-- Rollback-only behavior fixture for #269 review queue RPCs.
begin;

select public.swsi_ops_upsert_review_item(
  'historical-law:human_review:LawA:q1',
  'semantic_conflict',
  'historical-law-guardian-queue',
  'LawA|q1',
  '2026-10-02T00:00:00Z',
  '{"lane":"human_review"}'::jsonb
);

do $$
declare r public.swsi_ops_review_items%rowtype;
begin
  select * into r from public.swsi_ops_review_items
   where item_id='historical-law:human_review:LawA:q1';
  if r.state <> 'open' or r.attempt <> 0
     or r.first_seen_at <> '2026-10-02T00:00:00Z'::timestamptz then
    raise exception 'initial review upsert mismatch';
  end if;
end $$;

select public.swsi_ops_upsert_review_item(
  'historical-law:human_review:LawA:q1',
  'semantic_conflict_updated',
  'historical-law-guardian-queue',
  null,
  '2026-10-02T01:00:00Z',
  '{"severity":"high"}'::jsonb
);

do $$
declare r public.swsi_ops_review_items%rowtype;
begin
  select * into r from public.swsi_ops_review_items
   where item_id='historical-law:human_review:LawA:q1';
  if r.first_seen_at <> '2026-10-02T00:00:00Z'::timestamptz
     or r.reason <> 'semantic_conflict_updated'
     or r.metadata->>'lane' <> 'human_review'
     or r.metadata->>'severity' <> 'high' then
    raise exception 'repeat upsert did not preserve first_seen/merge metadata';
  end if;
end $$;

select public.swsi_ops_touch_review_item(
  'historical-law:human_review:LawA:q1',
  '2026-10-02T02:00:00Z',
  'source temporarily unavailable',
  '2026-10-02T08:00:00Z'
);

do $$
declare r public.swsi_ops_review_items%rowtype;
begin
  select * into r from public.swsi_ops_review_items
   where item_id='historical-law:human_review:LawA:q1';
  if r.attempt <> 1
     or r.last_attempt_at <> '2026-10-02T02:00:00Z'::timestamptz
     or r.next_check_at <> '2026-10-02T08:00:00Z'::timestamptz then
    raise exception 'review touch mismatch';
  end if;
end $$;

select public.swsi_ops_resolve_review_item(
  'historical-law:human_review:LawA:q1',
  'resolved',
  'evidence confirmed',
  '2026-10-02T04:00:00Z'
);

select public.swsi_ops_resolve_review_item(
  'historical-law:human_review:LawA:q1',
  'resolved',
  'evidence confirmed',
  '2026-10-02T05:00:00Z'
);

select public.swsi_ops_upsert_review_item(
  'historical-law:human_review:LawA:q1',
  'new_reason_should_not_reopen',
  'historical-law-guardian-queue',
  'LawA|q1',
  '2026-10-02T06:00:00Z',
  '{"ignored_for_terminal":true}'::jsonb
);

do $$
declare r public.swsi_ops_review_items%rowtype;
begin
  select * into r from public.swsi_ops_review_items
   where item_id='historical-law:human_review:LawA:q1';
  if r.state <> 'resolved'
     or r.resolved_at <> '2026-10-02T04:00:00Z'::timestamptz
     or r.resolution <> 'evidence confirmed'
     or r.first_seen_at <> '2026-10-02T00:00:00Z'::timestamptz then
    raise exception 'terminal review history was mutated/reopened';
  end if;
end $$;

do $$
begin
  begin
    perform public.swsi_ops_resolve_review_item(
      'historical-law:human_review:LawA:q1',
      'invalid',
      'conflicting terminal rewrite',
      '2026-10-02T07:00:00Z'
    );
    raise exception 'expected terminal conflict was not rejected';
  exception when others then
    if position('already terminal with different resolution' in sqlerrm) = 0 then
      raise;
    end if;
  end;
end $$;

rollback;
