-- SWSI disaster-recovery bootstrap: original questions table only.
--
-- Recovery-only source. This file is intentionally outside supabase/migrations/
-- so adding it to GitHub can never be mistaken for a production migration.
-- It reconstructs the pre-automation questions table that later repo-owned
-- migrations expect to already exist.

create table public.questions (
  id text primary key,
  subject text,
  year text,
  round text,
  qno text,
  major text,
  topic text,
  keywords text,
  question text,
  opt_a text,
  opt_b text,
  opt_c text,
  opt_d text,
  answer text,
  exp_why text,
  exp_others text,
  exp_trap text,
  exp_raw text,
  mnemonic text,
  extension text,
  law text,
  mistake text
);
