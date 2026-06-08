-- ============================================================
-- 002_recovery.sql — schema recovery after 2026-06-08 data loss
-- ============================================================
-- The free-tier Supabase pause window expired and the project was
-- effectively reset (domestic_work schema dropped, public emptied).
-- This file consolidates everything that 001_init.sql covered PLUS the
-- additions made via apply_migration through April–May 2026 that were
-- never folded back into a versioned SQL file:
--
--   * n_unweighted column on fact_workers / fact_wages / fact_hours
--   * race_id on fact_hours (Phase A pipeline extension)
--   * fact_prev table (V4032 previdência)
--   * static_fact table (DIEESE headline figures)
--   * dw_prev and dw_static_facts views
--   * RLS + permissive public_read policies on every domestic_work table
--
-- Idempotent: every CREATE uses IF NOT EXISTS / OR REPLACE; every ALTER
-- guards with IF NOT EXISTS. Safe to re-run.
--
-- After applying this file, run etl/repopulate_from_json.py to reload
-- data from the committed dashboard/data/*.json exports.
-- ============================================================

create schema if not exists domestic_work;
comment on schema domestic_work is
  'Brazilian domestic workers data for STDMSP / JF Mayer (Concordia). Sourced from PNADC, Censo 2022, ILOSTAT.';

-- ============ DIMENSIONS ============

create table if not exists domestic_work.dim_time (
  time_id      serial primary key,
  year         int  not null,
  quarter      int,
  period_code  text not null unique,
  is_annual    boolean generated always as (quarter is null) stored,
  unique (year, quarter)
);

create table if not exists domestic_work.dim_geo (
  geo_id     serial primary key,
  level      text not null check (level in ('country','region','uf','metro','municipality')),
  code       text not null,
  name_pt    text not null,
  name_en    text not null,
  parent_id  int references domestic_work.dim_geo(geo_id),
  unique (level, code)
);

create table if not exists domestic_work.dim_sex (
  sex_id   serial primary key,
  code     text not null unique,
  label_pt text not null,
  label_en text not null
);

create table if not exists domestic_work.dim_race (
  race_id   serial primary key,
  code      text not null unique,
  label_pt  text not null,
  label_en  text not null
);

create table if not exists domestic_work.dim_formality (
  formality_id serial primary key,
  code         text not null unique,
  label_pt     text not null,
  label_en     text not null
);

create table if not exists domestic_work.dim_age_group (
  age_id    serial primary key,
  code      text not null unique,
  label_pt  text not null,
  label_en  text not null,
  sort_order int not null
);

-- ============ FACTS ============

create table if not exists domestic_work.fact_workers (
  fact_id      bigserial primary key,
  time_id      int  not null references domestic_work.dim_time(time_id),
  geo_id       int  not null references domestic_work.dim_geo(geo_id),
  sex_id       int  not null references domestic_work.dim_sex(sex_id),
  race_id      int  not null references domestic_work.dim_race(race_id),
  formality_id int  not null references domestic_work.dim_formality(formality_id),
  age_id       int  not null references domestic_work.dim_age_group(age_id),
  workers_thousands numeric(12,2),
  n_unweighted int,
  source_table text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, formality_id, age_id, source_table)
);
alter table domestic_work.fact_workers
  add column if not exists n_unweighted int;
create index if not exists ix_fact_workers_time on domestic_work.fact_workers (time_id);
create index if not exists ix_fact_workers_geo  on domestic_work.fact_workers (geo_id);

create table if not exists domestic_work.fact_wages (
  fact_id      bigserial primary key,
  time_id      int  not null references domestic_work.dim_time(time_id),
  geo_id       int  not null references domestic_work.dim_geo(geo_id),
  sex_id       int  not null references domestic_work.dim_sex(sex_id),
  race_id      int  not null references domestic_work.dim_race(race_id),
  formality_id int  not null references domestic_work.dim_formality(formality_id),
  mean_wage_brl_real numeric(12,2),
  median_wage_brl_real numeric(12,2),
  n_unweighted int,
  source_table text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, formality_id, source_table)
);
alter table domestic_work.fact_wages
  add column if not exists n_unweighted int;

create table if not exists domestic_work.fact_hours (
  fact_id      bigserial primary key,
  time_id      int  not null references domestic_work.dim_time(time_id),
  geo_id       int  not null references domestic_work.dim_geo(geo_id),
  sex_id       int  not null references domestic_work.dim_sex(sex_id),
  race_id      int  not null references domestic_work.dim_race(race_id),
  formality_id int  not null references domestic_work.dim_formality(formality_id),
  mean_hours_per_week numeric(5,2),
  pct_over_44h numeric(5,2),
  n_unweighted int,
  source_table text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, formality_id, source_table)
);
-- In case the older 001 shape (without race_id, without n_unweighted) was applied:
alter table domestic_work.fact_hours
  add column if not exists race_id int references domestic_work.dim_race(race_id);
alter table domestic_work.fact_hours
  add column if not exists n_unweighted int;

create table if not exists domestic_work.fact_prev (
  fact_id      bigserial primary key,
  time_id      int  not null references domestic_work.dim_time(time_id),
  geo_id       int  not null references domestic_work.dim_geo(geo_id),
  sex_id       int  not null references domestic_work.dim_sex(sex_id),
  race_id      int  not null references domestic_work.dim_race(race_id),
  formality_id int  not null references domestic_work.dim_formality(formality_id),
  pct_with_prev numeric(5,2),
  n_with_prev   int,
  n_unweighted  int,
  source_table  text not null,
  loaded_at     timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, formality_id, source_table)
);

create table if not exists domestic_work.fact_intl (
  fact_id      bigserial primary key,
  time_id      int  not null references domestic_work.dim_time(time_id),
  country_iso3 text not null,
  country_pt   text not null,
  country_en   text not null,
  domestic_workers_thousands numeric(12,2),
  pct_of_employed_women numeric(5,2),
  pct_informal numeric(5,2),
  source       text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, country_iso3, source)
);

create table if not exists domestic_work.data_source (
  source_id    serial primary key,
  short_code   text not null unique,
  long_name_pt text not null,
  long_name_en text not null,
  url          text not null,
  notes_pt     text,
  notes_en     text
);

-- ============ STATIC FACTS (DIEESE headline figures) ============

create table if not exists domestic_work.static_fact (
  fact_code    text primary key,
  value_num    numeric,
  value_unit   text,
  label_pt     text,
  label_en     text,
  source_short text,
  source_url   text,
  source_date  date,
  note_pt      text,
  note_en      text,
  updated_at   timestamptz not null default now()
);

-- ============ PUBLIC READ VIEWS (PostgREST contract) ============
-- security_invoker = true so RLS/permissions of the *caller* apply.

create or replace view public.dw_workers as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code, g.name_pt as geo_name_pt, g.name_en as geo_name_en,
       s.code as sex_code, s.label_pt as sex_pt, s.label_en as sex_en,
       r.code as race_code, r.label_pt as race_pt, r.label_en as race_en,
       f.code as formality_code, f.label_pt as formality_pt, f.label_en as formality_en,
       a.code as age_code,
       fw.workers_thousands, fw.n_unweighted, fw.source_table
from domestic_work.fact_workers fw
join domestic_work.dim_time      t on t.time_id = fw.time_id
join domestic_work.dim_geo       g on g.geo_id  = fw.geo_id
join domestic_work.dim_sex       s on s.sex_id  = fw.sex_id
join domestic_work.dim_race      r on r.race_id = fw.race_id
join domestic_work.dim_formality f on f.formality_id = fw.formality_id
join domestic_work.dim_age_group a on a.age_id = fw.age_id;

create or replace view public.dw_wages as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code, g.name_pt as geo_name_pt, g.name_en as geo_name_en,
       s.code as sex_code, r.code as race_code, f.code as formality_code,
       fw.mean_wage_brl_real, fw.median_wage_brl_real, fw.n_unweighted, fw.source_table
from domestic_work.fact_wages fw
join domestic_work.dim_time      t on t.time_id = fw.time_id
join domestic_work.dim_geo       g on g.geo_id  = fw.geo_id
join domestic_work.dim_sex       s on s.sex_id  = fw.sex_id
join domestic_work.dim_race      r on r.race_id = fw.race_id
join domestic_work.dim_formality f on f.formality_id = fw.formality_id;

create or replace view public.dw_hours as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code, g.name_pt as geo_name_pt, g.name_en as geo_name_en,
       s.code as sex_code, r.code as race_code, f.code as formality_code,
       fh.mean_hours_per_week, fh.pct_over_44h, fh.n_unweighted, fh.source_table
from domestic_work.fact_hours fh
join domestic_work.dim_time      t on t.time_id = fh.time_id
join domestic_work.dim_geo       g on g.geo_id  = fh.geo_id
join domestic_work.dim_sex       s on s.sex_id  = fh.sex_id
join domestic_work.dim_race      r on r.race_id = fh.race_id
join domestic_work.dim_formality f on f.formality_id = fh.formality_id;

create or replace view public.dw_prev as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code, g.name_pt as geo_name_pt, g.name_en as geo_name_en,
       s.code as sex_code, r.code as race_code, f.code as formality_code,
       fp.pct_with_prev, fp.n_with_prev, fp.n_unweighted, fp.source_table
from domestic_work.fact_prev fp
join domestic_work.dim_time      t on t.time_id = fp.time_id
join domestic_work.dim_geo       g on g.geo_id  = fp.geo_id
join domestic_work.dim_sex       s on s.sex_id  = fp.sex_id
join domestic_work.dim_race      r on r.race_id = fp.race_id
join domestic_work.dim_formality f on f.formality_id = fp.formality_id;

create or replace view public.dw_intl as
select t.period_code, t.year,
       fi.country_iso3, fi.country_pt, fi.country_en,
       fi.domestic_workers_thousands, fi.pct_of_employed_women, fi.pct_informal,
       fi.source
from domestic_work.fact_intl fi
join domestic_work.dim_time t on t.time_id = fi.time_id;

create or replace view public.dw_sources as
select short_code, long_name_pt, long_name_en, url, notes_pt, notes_en
from domestic_work.data_source;

create or replace view public.dw_static_facts as
select fact_code, value_num, value_unit, label_pt, label_en,
       source_short, source_url, source_date, note_pt, note_en
from domestic_work.static_fact;

alter view public.dw_workers      set (security_invoker = true);
alter view public.dw_wages        set (security_invoker = true);
alter view public.dw_hours        set (security_invoker = true);
alter view public.dw_prev         set (security_invoker = true);
alter view public.dw_intl         set (security_invoker = true);
alter view public.dw_sources      set (security_invoker = true);
alter view public.dw_static_facts set (security_invoker = true);

-- ============ RLS + policies ============
-- Re-applies the 2026-05-06 security pass. Read-only public access via
-- anon JWT; service_role bypasses RLS for ETL writes.

do $$
declare
  t text;
begin
  for t in
    select tablename from pg_tables where schemaname = 'domestic_work'
  loop
    execute format('alter table domestic_work.%I enable row level security', t);
    execute format(
      $f$drop policy if exists "public_read" on domestic_work.%I$f$, t
    );
    execute format(
      $f$create policy "public_read" on domestic_work.%I for select to anon, authenticated using (true)$f$, t
    );
  end loop;
end$$;

-- ============ Grants ============

grant usage on schema public, domestic_work to anon, authenticated;
grant select on
  public.dw_workers, public.dw_wages, public.dw_hours, public.dw_prev,
  public.dw_intl, public.dw_sources, public.dw_static_facts
  to anon, authenticated;
grant select on all tables in schema domestic_work to anon, authenticated;
alter default privileges in schema domestic_work
  grant select on tables to anon, authenticated;
