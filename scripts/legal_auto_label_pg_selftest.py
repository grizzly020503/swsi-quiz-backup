#!/usr/bin/env python3
"""Behavioural check of the automatic legal-status labels on a disposable Postgres.

Loads the repository's law-name extractor and the auto-label migration verbatim
into an empty database (one transaction, rolled back), then checks every branch:

* theory question -> not_applicable; 社會政策與社會立法 policy wording -> left alone;
* cited watched law amended at least a year before the exam -> verified_current
  with the batch-1 "自動規則" note; two laws -> "均" and the newer law's URL;
* amended within a year, no MOJ date, MOJ check older than the exam, an
  unwatched law-like name, non-standard grading -> left alone;
* a CJK compatibility glyph must not hide a law name (NFKC);
* a sitting missing from moex_exam_dates uses its earliest possible date;
* explanation not ready / already reviewed -> untouched; dry run writes nothing;
  a second run is a no-op; only the four legal columns ever change; every
  applied label is logged; the replay reports a reviewed row the rule disagrees with.

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
MIGRATION = MIGRATIONS / '20261127100000_legal_auto_label.sql'
EXTRACTOR = MIGRATIONS / '20261128090000_legal_names_from_registry.sql'
PASS = 'LEGAL_AUTO_LABEL_PG_SELFTEST_PASS'
COMPAT_NIAN = '年'  # CJK COMPATIBILITY IDEOGRAPH-F98E, NFKC -> 年


def psql(sql):
    done = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                          input=sql, capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout, done.stderr


def extractor_sql():
    """The production extractor (20261128090000: the 52 baseline names plus the
    registry). It has no NFKC step: production never applied 20261003184700
    (checked 2026-11-27), so the auto-label rule must normalise its own input.
    Using the production-equivalent extractor proves that."""
    text = EXTRACTOR.read_text(encoding='utf-8')
    m = re.search(r'create or replace function public\.extract_legal_canonical_names\(raw_law text\).*?\n\$function\$;',
                  text, re.S)
    if not m:
        raise SystemExit('extractor not found in ' + EXTRACTOR.name)
    if 'normalize(' in m.group(0):
        raise SystemExit('extractor normalises its input; update the production-equivalent copy and this test')
    return m.group(0)


def build_sql():
    q = lambda s: "'" + s.replace("'", "''") + "'"
    rows = [
        # id, subject, year, round, exam code, question, law, grading, analysis, legal
        ('Q-NA', '人類行為與社會環境', '113', '第一次', '113030', '依皮亞傑的認知發展理論，下列何者正確？', '', 'standard', 'ready', 'unreviewed'),
        ('Q-NA-SP', '社會政策與社會立法', '113', '第一次', '113030', '下列何者屬於艾斯平－安德森提出的福利體制類型？', '', 'standard', 'ready', 'unreviewed'),
        ('Q-SP-POLICY', '社會政策與社會立法', '113', '第一次', '113030', '下列何者屬於社會保險的特性？', '', 'standard', 'ready', 'unreviewed'),
        ('Q-LAW-OLD', '社會政策與社會立法', '113', '第一次', '113030', '依社會救助法規定，下列敘述何者正確？', '社會救助法第4條', 'standard', 'ready', 'unreviewed'),
        ('Q-LAW-TWO', '社會政策與社會立法', '113', '第二次', '113100', '依社會救助法與長期照顧服務法，下列何者正確？', '社會救助法第5條；長期照顧服務法第8條', 'standard', 'ready', 'unreviewed'),
        ('Q-LAW-RECENT', '社會政策與社會立法', '115', '第一次', '115030', '依社會工作師法規定，下列何者正確？', '社會工作師法第17條', 'standard', 'ready', 'unreviewed'),
        ('Q-LAW-NODATE', '社會政策與社會立法', '113', '第一次', '113030', '依身心障礙者權益保障法規定，下列何者正確？', '身心障礙者權益保障法第5條', 'standard', 'ready', 'unreviewed'),
        ('Q-LAW-STALE', '社會政策與社會立法', '113', '第一次', '113030', '依老人福利法規定，下列何者正確？', '老人福利法第2條', 'standard', 'ready', 'unreviewed'),
        ('Q-LAW-UNKNOWN', '社會政策與社會立法', '113', '第一次', '113030', '依社會救助法及心理師法，下列何者正確？', '社會救助法第4條、心理師法第5條', 'standard', 'ready', 'unreviewed'),
        ('Q-ALLCREDIT', '人類行為與社會環境', '113', '第一次', '113030', '下列何者正確？', '', 'all_credit', 'ready', 'unreviewed'),
        ('Q-GLYPH', '社會工作', '113', '第一次', '113030', '下列關於兒童及少' + COMPAT_NIAN + '福利與權益保障法的敘述何者正確？', '', 'standard', 'ready', 'unreviewed'),
        ('Q-NEW-SITTING', '社會政策與社會立法', '116', '第一次', '116030', '依社會救助法規定，下列敘述何者正確？', '社會救助法第4條', 'standard', 'ready', 'unreviewed'),
        ('Q-PENDING', '人類行為與社會環境', '113', '第一次', '113030', '依艾瑞克森的理論，下列何者正確？', '', 'standard', 'pending', 'unreviewed'),
        ('Q-REVIEWED', '社會政策與社會立法', '113', '第一次', '113030', '依社會救助法規定，下列何者錯誤？', '社會救助法第9條', 'standard', 'ready', 'changed'),
    ]
    values = ',\n  '.join('(%s)' % ', '.join(q(v) for v in r) for r in rows)
    return '\n'.join([
        'begin;',
        '''do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin; end if;
end $$;''',
        '''create table public.questions (
  id text primary key, subject text, year text, round text, qno text, source_exam_code text,
  question text, opt_a text, opt_b text, opt_c text, opt_d text, answer text,
  accepted_answers text[], grading_mode text, law text, legal_canonical_names text[],
  exp_why text, analysis_status text, legal_status text not null default 'unreviewed',
  legal_checked_at timestamptz, legal_note text, legal_source_url text);
create table public.legal_reference_registry (
  canonical_name text primary key, official_modified_date text, official_url text,
  last_checked_at timestamptz, watch_status text);''',
        extractor_sql(),
        MIGRATION.read_text(encoding='utf-8'),
        '''insert into public.legal_reference_registry values
  ('社會救助法', '2015-12-30', 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050078', '2027-03-02 11:12:03+00', 'unchanged'),
  ('長期照顧服務法', '2021-06-09', 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070040', '2027-03-02 11:12:03+00', 'unchanged'),
  ('社會工作師法', '2025-06-01', 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0090001', '2027-03-02 11:12:03+00', 'unchanged'),
  ('身心障礙者權益保障法', null, null, '2027-03-02 11:12:03+00', 'unchanged'),
  ('老人福利法', '2010-01-01', 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050037', '2020-01-01 00:00:00+00', 'unchanged');''',
        '''insert into public.questions (id, subject, year, round, source_exam_code, question, law,
  grading_mode, analysis_status, legal_status) values
  ''' + values + ';',
        "update public.questions set opt_a = 'A', opt_b = 'B', opt_c = 'C', opt_d = 'D', answer = 'A', exp_why = '解析';",
        '''update public.questions set legal_canonical_names = public.extract_legal_canonical_names(law);
create table public.selftest_core as
  select id, md5(concat_ws('|', subject, year, round, source_exam_code, question, opt_a, opt_b, opt_c, opt_d,
                 answer, grading_mode, law, exp_why, analysis_status)) as core from public.questions;
create function public.selftest_expect(p_label text, p_actual text, p_expected text) returns void
language plpgsql as $$
begin
  if p_actual is distinct from p_expected then
    raise exception 'SELFTEST FAIL %: expected %, got %', p_label, p_expected, p_actual;
  end if;
end $$;
create function public.selftest_status(p_id text) returns text language sql as
  $$ select legal_status from public.questions where id = p_id $$;''',
        # Dry run decides but writes nothing.
        '''create temporary table dry as select public.legal_auto_label_apply(true, 500) as r;
select public.selftest_expect('dry run checks every ready unreviewed row', (select r->>'checked' from dry), '12');
select public.selftest_expect('dry run writes nothing',
  (select count(*)::text from public.questions where legal_status <> 'unreviewed' and id <> 'Q-REVIEWED'), '0');
select public.selftest_expect('dry run logs nothing', (select count(*)::text from public.legal_auto_label_log), '0');
select public.selftest_expect('dry run not_applicable list',
  (select r->>'not_applicable' from dry), '["Q-NA", "Q-NA-SP"]');
select public.selftest_expect('dry run verified list',
  (select r->>'verified_current' from dry), '["Q-LAW-OLD", "Q-LAW-TWO", "Q-NEW-SITTING"]');''',
        # Real run.
        '''create temporary table run1 as select public.legal_auto_label_apply(false, 500) as r;
select public.selftest_expect('theory question', public.selftest_status('Q-NA'), 'not_applicable');
select public.selftest_expect('policy theory without benefit wording', public.selftest_status('Q-NA-SP'), 'not_applicable');
select public.selftest_expect('policy question with benefit wording is left alone', public.selftest_status('Q-SP-POLICY'), 'unreviewed');
select public.selftest_expect('old law verified', public.selftest_status('Q-LAW-OLD'), 'verified_current');
select public.selftest_expect('batch-1 note format',
  (select legal_note from public.questions where id = 'Q-LAW-OLD'),
  '考試時點法規核對（自動規則）：社會救助法最後修正公布日 2015-12-30，早於本題考試日 2024-02-04 一年以上，考試時適用條文與現行條文相同。依據：法務部全國法規資料庫（2027-03-02 查核）。');
select public.selftest_expect('MOJ source url',
  (select legal_source_url from public.questions where id = 'Q-LAW-OLD'),
  'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050078');
select public.selftest_expect('checked time set', (select (legal_checked_at is not null)::text from public.questions where id = 'Q-LAW-OLD'), 'true');
select public.selftest_expect('two laws',
  (select legal_note from public.questions where id = 'Q-LAW-TWO'),
  '考試時點法規核對（自動規則）：社會救助法最後修正公布日 2015-12-30、長期照顧服務法最後修正公布日 2021-06-09，均早於本題考試日 2024-07-27 一年以上，考試時適用條文與現行條文相同。依據：法務部全國法規資料庫（2027-03-02 查核）。');
select public.selftest_expect('two laws: newer law url',
  (select legal_source_url from public.questions where id = 'Q-LAW-TWO'),
  'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070040');
select public.selftest_expect('amended within a year', public.selftest_status('Q-LAW-RECENT'), 'unreviewed');
select public.selftest_expect('no MOJ date', public.selftest_status('Q-LAW-NODATE'), 'unreviewed');
select public.selftest_expect('MOJ check older than exam', public.selftest_status('Q-LAW-STALE'), 'unreviewed');
select public.selftest_expect('unwatched law-like name', public.selftest_status('Q-LAW-UNKNOWN'), 'unreviewed');
select public.selftest_expect('non-standard grading', public.selftest_status('Q-ALLCREDIT'), 'unreviewed');
select public.selftest_expect('compatibility glyph does not hide the law', public.selftest_status('Q-GLYPH'), 'unreviewed');
select public.selftest_expect('sitting without a pinned date uses its earliest day',
  (select legal_note from public.questions where id = 'Q-NEW-SITTING'),
  '考試時點法規核對（自動規則）：社會救助法最後修正公布日 2015-12-30，早於本題考試（116 年第一次，不早於 2027-01-01）一年以上，考試時適用條文與現行條文相同。依據：法務部全國法規資料庫（2027-03-02 查核）。');
select public.selftest_expect('explanation not ready is untouched', public.selftest_status('Q-PENDING'), 'unreviewed');
select public.selftest_expect('reviewed row is untouched', public.selftest_status('Q-REVIEWED'), 'changed');
select public.selftest_expect('not_applicable keeps the other legal fields empty',
  (select (legal_checked_at is null and legal_note is null and legal_source_url is null)::text
     from public.questions where id = 'Q-NA'), 'true');
select public.selftest_expect('left-for-review reasons',
  (select string_agg((e->>'id') || '=' || (e->>'reason'), ' | ' order by e->>'id' collate "C")
     from run1, jsonb_array_elements(r->'left_for_review') e),
  'Q-ALLCREDIT=non-standard official grading | Q-GLYPH=mentions a law-like name outside the watched laws | '
  || 'Q-LAW-NODATE=no MOJ amendment date for 身心障礙者權益保障法 | Q-LAW-RECENT=社會工作師法 amended within a year before the exam or later | '
  || 'Q-LAW-STALE=MOJ check older than the exam for 老人福利法 | Q-LAW-UNKNOWN=mentions a law-like name outside the watched laws | '
  || 'Q-SP-POLICY=law or benefit wording but no recognised law');
select public.selftest_expect('every applied label is logged',
  (select string_agg(question_id || ':' || legal_status, ',' order by question_id collate "C") from public.legal_auto_label_log),
  'Q-LAW-OLD:verified_current,Q-LAW-TWO:verified_current,Q-NA:not_applicable,Q-NA-SP:not_applicable,Q-NEW-SITTING:verified_current');
select public.selftest_expect('only legal columns changed',
  (select count(*)::text from public.questions q join public.selftest_core c using (id)
     where md5(concat_ws('|', q.subject, q.year, q.round, q.source_exam_code, q.question, q.opt_a, q.opt_b, q.opt_c,
                         q.opt_d, q.answer, q.grading_mode, q.law, q.exp_why, q.analysis_status)) <> c.core), '0');''',
        # Second run: nothing left to label, nothing logged twice.
        '''create temporary table run2 as select public.legal_auto_label_apply(false, 500) as r;
select public.selftest_expect('second run labels nothing',
  (select (r->>'not_applicable') || (r->>'verified_current') from run2), '[][]');
select public.selftest_expect('second run logs nothing new', (select count(*)::text from public.legal_auto_label_log), '5');''',
        # Replay against reviewed rows.
        '''select public.selftest_expect('replay flags the reviewed row the rule disagrees with',
  (select public.legal_auto_label_replay()->>'disagreement_ids'), '["Q-REVIEWED"]');
select public.selftest_expect('replay counts',
  (select (r->>'reviewed') || '/' || (r->>'predicted_not_applicable') || '/' || (r->>'predicted_verified_current')
     from (select public.legal_auto_label_replay() as r) x), '6/2/4');''',
        "select '%s';" % PASS,
        'rollback;',
        '',
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
        raise SystemExit('legal auto-label selftest FAILED')
    print('legal auto-label rules behave as intended (%s)' % MIGRATION.name)


if __name__ == '__main__':
    main()
