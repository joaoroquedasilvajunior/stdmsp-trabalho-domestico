-- ============================================================
-- domestic_work — schema for Brazilian domestic workers data
-- Already applied to Supabase project sceneqc (vqwhzzaqddqeurrspcdz)
-- on 2026-04-28 via the apply_migration MCP tool.
-- Kept here for version control + reproducibility.
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
  source_table text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, formality_id, age_id, source_table)
);
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
  source_table text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, formality_id, source_table)
);

create table if not exists domestic_work.fact_hours (
  fact_id      bigserial primary key,
  time_id      int  not null references domestic_work.dim_time(time_id),
  geo_id       int  not null references domestic_work.dim_geo(geo_id),
  sex_id       int  not null references domestic_work.dim_sex(sex_id),
  formality_id int  not null references domestic_work.dim_formality(formality_id),
  mean_hours_per_week numeric(5,2),
  pct_over_44h numeric(5,2),
  source_table text not null,
  loaded_at    timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, formality_id, source_table)
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

-- ============ PUBLIC READ VIEWS (PostgREST contract) ============
-- security_invoker = true so RLS/permissions of the *caller* apply,
-- not the view-owner. Required for safe public exposure via anon key.

create or replace view public.dw_workers as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code, g.name_pt as geo_name_pt, g.name_en as geo_name_en,
       s.code as sex_code, s.label_pt as sex_pt, s.label_en as sex_en,
       r.code as race_code, r.label_pt as race_pt, r.label_en as race_en,
       f.code as formality_code, f.label_pt as formality_pt, f.label_en as formality_en,
       a.code as age_code,
       fw.workers_thousands, fw.source_table
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
       fw.mean_wage_brl_real, fw.median_wage_brl_real, fw.source_table
from domestic_work.fact_wages fw
join domestic_work.dim_time      t on t.time_id = fw.time_id
join domestic_work.dim_geo       g on g.geo_id  = fw.geo_id
join domestic_work.dim_sex       s on s.sex_id  = fw.sex_id
join domestic_work.dim_race      r on r.race_id = fw.race_id
join domestic_work.dim_formality f on f.formality_id = fw.formality_id;

create or replace view public.dw_hours as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code, g.name_pt as geo_name_pt, g.name_en as geo_name_en,
       s.code as sex_code, f.code as formality_code,
       fh.mean_hours_per_week, fh.pct_over_44h, fh.source_table
from domestic_work.fact_hours fh
join domestic_work.dim_time      t on t.time_id = fh.time_id
join domestic_work.dim_geo       g on g.geo_id  = fh.geo_id
join domestic_work.dim_sex       s on s.sex_id  = fh.sex_id
join domestic_work.dim_formality f on f.formality_id = fh.formality_id;

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

alter view public.dw_workers set (security_invoker = true);
alter view public.dw_wages   set (security_invoker = true);
alter view public.dw_hours   set (security_invoker = true);
alter view public.dw_intl    set (security_invoker = true);
alter view public.dw_sources set (security_invoker = true);

grant usage on schema public, domestic_work to anon, authenticated;
grant select on public.dw_workers, public.dw_wages, public.dw_hours,
                public.dw_intl,    public.dw_sources to anon, authenticated;
grant select on all tables in schema domestic_work to anon, authenticated;
alter default privileges in schema domestic_work
  grant select on tables to anon, authenticated;
