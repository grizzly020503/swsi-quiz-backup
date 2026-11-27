#!/usr/bin/env python3
"""Behavioural check of the registry-driven law-name extractor on a disposable Postgres.

Builds the production state first (the hard-coded 52-name extractor, its
question trigger, a registry holding the same 52 names and tagged questions),
applies supabase/migrations/20261128090000_legal_names_from_registry.sql
verbatim, then checks, in one rolled-back transaction:

* for every question and every baseline name and alias, the new extractor
  returns exactly what the production one did, and applying the migration
  changes no stored legal_canonical_names;
* registering a new law tags the questions whose text names it, appends it
  after the existing names, and rewrites no other row and no other column;
* re-registering a known law, or registering a law no question names, changes
  nothing;
* a question inserted or edited later is tagged with the new law by the
  existing trigger;
* the refresh function is not executable by anon or authenticated.

Refuses to run unless SWSI_DISPOSABLE_PG=I_CONFIRM_DISPOSABLE_FIXTURE and the
database has no public.questions table. Connection: the usual PG* variables.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'supabase/migrations'
MIGRATION = MIGRATIONS / '20261128090000_legal_names_from_registry.sql'
PRODUCTION_EXTRACTOR = MIGRATIONS / '20261003184700_normalize_legal_canonical_input_nfkc.sql'
PASS = 'LEGAL_NAMES_REGISTRY_PG_SELFTEST_PASS'


def psql(sql):
    done = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                          input=sql, capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout, done.stderr


def production_extractor_sql():
    """The extractor production runs before this migration: the repository
    copy without its NFKC step (production never applied 20261003184700)."""
    text = PRODUCTION_EXTRACTOR.read_text(encoding='utf-8')
    m = re.search(r'create or replace function public\.extract_legal_canonical_names\(raw_law text\).*?\n\$function\$;',
                  text, re.S)
    if not m:
        raise SystemExit('extractor not found in ' + PRODUCTION_EXTRACTOR.name)
    nfkc = "normalize(coalesce(raw_law, ''), NFKC)"
    if m.group(0).count(nfkc) != 1:
        raise SystemExit('extractor NFKC step not found; update the production-equivalent copy')
    return m.group(0).replace(nfkc, "coalesce(raw_law, '')")


def baseline_names():
    m = re.search(r"names text\[\] := array\[\s*(.*?)\s*\];", MIGRATION.read_text(encoding='utf-8'), re.S)
    names = re.findall(r"'([^']+)'", m.group(1))
    if len(names) != 52 or len(set(names)) != 52:
        raise SystemExit('baseline list must hold 52 distinct names')
    return names


def build_sql():
    q = lambda s: "'" + s.replace("'", "''") + "'"
    names = baseline_names()
    rows = [
        ('Q-TWO', '依社會救助法及民法規定，下列何者正確？', '社會救助法第4條'),
        ('Q-ALIAS', '依性別工作平等法，下列何者正確？', ''),
        ('Q-COVENANT', '依兩公約施行法，下列何者正確？', ''),
        ('Q-SW-RULE', '依社會工作師執業登記及繼續教育辦法規定', ''),
        ('Q-NEW', '依勞動基準法及社會救助法，下列何者正確？', '勞動基準法第21條'),
        ('Q-NEW-ONLY-LAW', '下列有關基本工資的敘述，何者正確？', '勞動基準法第21條'),
        ('Q-THEORY', '依皮亞傑的認知發展理論，下列何者正確？', ''),
        ('Q-OTHER', '依政府採購法規定，下列何者正確？', ''),
    ]
    rows += [(f'Q-BASE-{i:02d}', f'依{n}規定，下列何者正確？', '') for i, n in enumerate(names)]
    values = ',\n  '.join(f'({q(i)}, {q(t)}, {q(l) if l else "null"})' for i, t, l in rows)
    probes = [n for n in names] + ['性別工作平等法', '兩公約施行法', '人權公約施行法', '社會工作師執業登記及繼續教育辦法',
                                   '依社會救助法及民法規定', '性別工作平等法與性別平等工作法']
    probe_values = ', '.join(q(p) for p in probes)
    core = "md5(concat_ws('|', question, opt_a, opt_b, opt_c, opt_d, answer, law, exp_why, analysis_status, legal_status, legal_note))"
    return '\n'.join([
        'begin;',
        '''do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;''',
        '''create table public.questions (
  id text primary key, question text, opt_a text, opt_b text, opt_c text, opt_d text, answer text,
  law text, legal_canonical_names text[], exp_why text, analysis_status text,
  legal_status text not null default 'unreviewed', legal_note text);
create table public.legal_reference_registry (
  canonical_name text primary key, official_modified_date text, official_url text,
  last_checked_at timestamptz, watch_status text, question_count integer);''',
        production_extractor_sql(),
        '''create function public.sync_question_legal_canonical_names() returns trigger
language plpgsql set search_path to 'public' as $$
begin
  new.legal_canonical_names := public.extract_legal_canonical_names(
    concat_ws(' ', new.question, new.opt_a, new.opt_b, new.opt_c, new.opt_d, new.law));
  return new;
end $$;
create trigger questions_sync_legal_canonical_names
before insert or update of question, opt_a, opt_b, opt_c, opt_d, law on public.questions
for each row execute function public.sync_question_legal_canonical_names();''',
        'insert into public.legal_reference_registry (canonical_name, watch_status) values\n  '
        + ',\n  '.join(f"({q(n)}, 'unchanged')" for n in names) + ';',
        'insert into public.questions (id, question, law) values\n  ' + values + ';',
        "update public.questions set opt_a = 'A', opt_b = 'B', opt_c = 'C', opt_d = 'D', answer = 'A', "
        "exp_why = '解析', analysis_status = 'ready', legal_note = null;",
        # Keep the production extractor for the parity checks.
        production_extractor_sql().replace('public.extract_legal_canonical_names', 'public.selftest_old_extract'),
        f'''create table public.selftest_before as
  select id, legal_canonical_names, {core} as core from public.questions;
create function public.selftest_expect(p_label text, p_actual text, p_expected text) returns void
language plpgsql as $$
begin
  if p_actual is distinct from p_expected then
    raise exception 'SELFTEST FAIL %: expected %, got %', p_label, p_expected, p_actual;
  end if;
end $$;
create function public.selftest_names(p_id text) returns text language sql as
  $$ select array_to_string(legal_canonical_names, ',') from public.questions where id = p_id $$;''',
        MIGRATION.read_text(encoding='utf-8'),
        f'''select public.selftest_expect('extractor is stable now',
  (select provolatile::text from pg_proc where proname = 'extract_legal_canonical_names'), 's');
select public.selftest_expect('same output for every question text',
  (select count(*)::text from public.questions q
    where public.extract_legal_canonical_names(concat_ws(' ', q.question, q.opt_a, q.opt_b, q.opt_c, q.opt_d, q.law))
          is distinct from public.selftest_old_extract(concat_ws(' ', q.question, q.opt_a, q.opt_b, q.opt_c, q.opt_d, q.law))), '0');
select public.selftest_expect('same output for every baseline name and alias',
  (select count(*)::text from unnest(array[{probe_values}]) p
    where public.extract_legal_canonical_names(p) is distinct from public.selftest_old_extract(p)), '0');
select public.selftest_expect('applying the migration changes no stored names',
  (select count(*)::text from public.questions q join public.selftest_before b using (id)
    where q.legal_canonical_names is distinct from b.legal_canonical_names), '0');
select public.selftest_expect('baseline tags', public.selftest_names('Q-TWO'), '社會救助法,民法');
select public.selftest_expect('alias tag', public.selftest_names('Q-ALIAS'), '性別平等工作法');
select public.selftest_expect('unwatched law not tagged yet', public.selftest_names('Q-NEW'), '社會救助法');

create table public.selftest_tid as select id, ctid::text as tid from public.questions;
insert into public.legal_reference_registry (canonical_name, watch_status) values ('勞動基準法', 'baseline');
select public.selftest_expect('only the questions naming the new law were rewritten',
  (select string_agg(q.id, ',' order by q.id) from public.questions q join public.selftest_tid t using (id)
    where q.ctid::text <> t.tid), 'Q-NEW,Q-NEW-ONLY-LAW');
select public.selftest_expect('new law appended after the existing names', public.selftest_names('Q-NEW'), '社會救助法,勞動基準法');
select public.selftest_expect('new law found through the law field', public.selftest_names('Q-NEW-ONLY-LAW'), '勞動基準法');
select public.selftest_expect('only the questions naming the new law changed',
  (select string_agg(q.id, ',' order by q.id) from public.questions q join public.selftest_before b using (id)
    where q.legal_canonical_names is distinct from b.legal_canonical_names), 'Q-NEW,Q-NEW-ONLY-LAW');
select public.selftest_expect('no other column changed',
  (select count(*)::text from public.questions q join public.selftest_before b using (id)
    where {core} is distinct from b.core), '0');

create table public.selftest_after_new as select id, legal_canonical_names from public.questions;
insert into public.legal_reference_registry (canonical_name, watch_status) values ('社會救助法', 'unchanged')
  on conflict (canonical_name) do update set watch_status = excluded.watch_status;
insert into public.legal_reference_registry (canonical_name, watch_status) values ('某不存在之測試法', 'baseline');
select public.selftest_expect('re-registering or registering an uncited law changes nothing',
  (select count(*)::text from public.questions q join public.selftest_after_new a using (id)
    where q.legal_canonical_names is distinct from a.legal_canonical_names), '0');

insert into public.legal_reference_registry (canonical_name, watch_status) values ('政府採購法', 'baseline');
select public.selftest_expect('second new law', public.selftest_names('Q-OTHER'), '政府採購法');
insert into public.questions (id, question, law) values ('Q-LATER', '依勞動基準法規定，下列何者正確？', null);
select public.selftest_expect('later question tagged by the trigger', public.selftest_names('Q-LATER'), '勞動基準法');
update public.questions set question = '依政府採購法及民法規定' where id = 'Q-THEORY';
select public.selftest_expect('edited question tagged by the trigger', public.selftest_names('Q-THEORY'), '民法,政府採購法');
select public.selftest_expect('refresh not executable by anon',
  has_function_privilege('anon', 'public.refresh_legal_canonical_names_for_new_law()', 'EXECUTE')::text, 'false');
select public.selftest_expect('refresh not executable by authenticated',
  has_function_privilege('authenticated', 'public.refresh_legal_canonical_names_for_new_law()', 'EXECUTE')::text, 'false');
select '{PASS}';''',
        'rollback;',
    ])


def main():
    if os.environ.get('SWSI_DISPOSABLE_PG') != 'I_CONFIRM_DISPOSABLE_FIXTURE':
        raise SystemExit('refusing: set SWSI_DISPOSABLE_PG=I_CONFIRM_DISPOSABLE_FIXTURE '
                         'and point PG* at a disposable database')
    code, out, err = psql("select to_regclass('public.questions') is null;\n")
    if code != 0 or out.strip() != 't':
        raise SystemExit('refusing: public.questions already exists or the database is unreachable\n' + err)
    code, out, err = psql(build_sql())
    print(out.strip())
    if code != 0 or PASS not in out.split():
        print(err.strip(), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
