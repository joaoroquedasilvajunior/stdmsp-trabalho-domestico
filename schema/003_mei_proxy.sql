-- =============================================================
-- 003_mei_proxy.sql — Step 1 of the MEI-as-proxy pipeline
-- =============================================================
-- Adds three new dim_formality codes that fact_workers will use
-- when the new SIDRA Tabela 6320 conta-própria × CNPJ feed lands:
--   conta_propria_total     — total self-employed (BR)
--   conta_propria_cnpj      — self-employed with CNPJ (MEI-proxy positive)
--   conta_propria_sem_cnpj  — self-employed without CNPJ (informal)
--
-- These codes share dim_formality with the existing 'com_carteira',
-- 'sem_carteira', 'total' codes used by the trabalhador-doméstico
-- rows. They are NEVER aggregated together at the dashboard layer:
-- the manifest entry uses source_code='PNADC-6320-CP' (distinct from
-- 'PNADC-6320') so the two populations stay cleanly partitioned.
--
-- Idempotent: re-running the migration is a no-op.
-- =============================================================

insert into domestic_work.dim_formality (code, label_pt, label_en)
values
  ('conta_propria_total',
   'Conta-própria (total)',
   'Self-employed (total)'),
  ('conta_propria_cnpj',
   'Conta-própria com CNPJ',
   'Self-employed with CNPJ'),
  ('conta_propria_sem_cnpj',
   'Conta-própria sem CNPJ',
   'Self-employed without CNPJ')
on conflict (code) do nothing;

-- Sanity: confirm all three rows exist
do $$
declare
  n int;
begin
  select count(*) into n
  from domestic_work.dim_formality
  where code in ('conta_propria_total', 'conta_propria_cnpj', 'conta_propria_sem_cnpj');
  if n <> 3 then
    raise exception 'Expected 3 conta-própria formality codes after migration, found %', n;
  end if;
  raise notice 'OK: 3 conta-própria formality codes present in dim_formality';
end$$;
