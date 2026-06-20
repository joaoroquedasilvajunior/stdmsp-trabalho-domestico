-- =============================================================
-- 004_fact_autonomous.sql — Step 2 of MEI proxy: microdata pipeline
-- =============================================================
-- Adds fact_autonomous for the conta-própria / empregador × CNPJ
-- × CBO-Domiciliar × race × sex cross-tab from PNADC microdata.
-- See etl/mei_proxy_path.md for the full plan.
--
-- This sits OUTSIDE the trabalhador-doméstico filter (VD4009 ∈ 03,04)
-- because V4019 (CNPJ?) is only asked of VD4009 ∈ {08,09}. The
-- cross-tab here covers the autonomous-worker population (conta-própria
-- + empregador), filtered by CBO-Domiciliar buckets that are
-- domestic-adjacent (cleaning 5141/5143, caregiver 5162, domestic 5121
-- which is legally NEVER conta-própria, plus 'other' catch-all).
--
-- Companion view: public.dw_autonomous (security_invoker=true) so
-- PostgREST anon/authenticated can read for the static export.
--
-- Idempotent: re-running is a no-op.
-- =============================================================

create table if not exists domestic_work.fact_autonomous (
  fact_id            bigserial primary key,
  time_id            int  not null references domestic_work.dim_time(time_id),
  geo_id             int  not null references domestic_work.dim_geo(geo_id),
  sex_id             int  not null references domestic_work.dim_sex(sex_id),
  race_id            int  not null references domestic_work.dim_race(race_id),
  cbo_group          text not null check (cbo_group in
                       ('domestic_5121','caregiver_5162','cleaning_5141','other')),
  autonomy_code      text not null check (autonomy_code in
                       ('conta_propria_cnpj','conta_propria_sem_cnpj',
                        'empregador_cnpj','empregador_sem_cnpj')),
  workers_thousands  numeric(12,2),
  pct_with_prev      numeric(5,2),
  mean_wage_brl      numeric(12,2),
  n_unweighted       int not null,
  source_table       text not null,
  loaded_at          timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, cbo_group, autonomy_code, source_table)
);
create index if not exists ix_fact_autonomous_time on domestic_work.fact_autonomous (time_id);
create index if not exists ix_fact_autonomous_cbo  on domestic_work.fact_autonomous (cbo_group);

create or replace view public.dw_autonomous as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code,
       s.code as sex_code, r.code as race_code,
       fa.cbo_group, fa.autonomy_code,
       fa.workers_thousands, fa.pct_with_prev, fa.mean_wage_brl,
       fa.n_unweighted, fa.source_table
from domestic_work.fact_autonomous fa
join domestic_work.dim_time t on t.time_id = fa.time_id
join domestic_work.dim_geo  g on g.geo_id  = fa.geo_id
join domestic_work.dim_sex  s on s.sex_id  = fa.sex_id
join domestic_work.dim_race r on r.race_id = fa.race_id;

alter view public.dw_autonomous set (security_invoker = true);
grant select on public.dw_autonomous to anon, authenticated;
