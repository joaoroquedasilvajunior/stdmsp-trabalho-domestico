-- =============================================================
-- 006_calculator_facts.sql — Static facts for the calculator page
-- =============================================================
-- Adiciona 3 novos fact_codes usados pelo /calculadora:
--
--   dieese_negras_wage_current       R$  rendimento médio negras
--   dieese_nao_negras_wage_current   R$  rendimento médio não-negras
--   cc_sp_floor_domestica_current    R$  piso Faixa 1 CC SP vigente
--
-- Objetivo: substituir constantes hardcoded no JS da calculadora,
-- permitindo atualização por SQL quando o DIEESE lança novo boletim
-- ou o STDMSP pacta nova CC.
--
-- Rodar via Supabase SQL Editor ou MCP `execute_sql`.
-- Idempotente: usa ON CONFLICT UPDATE.
-- =============================================================

insert into domestic_work.static_fact
  (fact_code, value_num, value_unit,
   label_pt, label_en,
   source_short, source_url, source_date,
   note_pt, note_en)
values

  ('dieese_negras_wage_current', 1274, 'BRL',
   'Rendimento médio — trabalhadoras domésticas negras',
   'Mean wage — Black women domestic workers',
   'DIEESE — Trabalhadoras Domésticas no Brasil (Infográfico abr/2026, base 4T 2025)',
   'https://www.dieese.org.br/infografico/2026/2026trabalhadorasDomesticas.pdf',
   '2026-04-01',
   'Rendimento médio (R$) das trabalhadoras domésticas negras (pretas + pardas), DIEESE 4T 2025. Atualizar quando novo Infográfico DIEESE for publicado.',
   'Mean earnings (R$) of Black (pretas + pardas) women domestic workers, DIEESE Q4 2025. Update when new DIEESE infográfico is published.'),

  ('dieese_nao_negras_wage_current', 1463, 'BRL',
   'Rendimento médio — trabalhadoras domésticas não-negras',
   'Mean wage — non-Black women domestic workers',
   'DIEESE — Trabalhadoras Domésticas no Brasil (Infográfico abr/2026, base 4T 2025)',
   'https://www.dieese.org.br/infografico/2026/2026trabalhadorasDomesticas.pdf',
   '2026-04-01',
   'Rendimento médio (R$) das trabalhadoras domésticas não-negras, DIEESE 4T 2025. Atualizar quando novo Infográfico DIEESE for publicado.',
   'Mean earnings (R$) of non-Black women domestic workers, DIEESE Q4 2025. Update when new DIEESE infográfico is published.'),

  ('cc_sp_floor_domestica_current', 1640, 'BRL',
   'Piso da Convenção Coletiva Doméstica SP — Faixa 1 (vigente)',
   'CC floor — Domestic workers in São Paulo (Tier 1, current)',
   'STDMSP — Convenção Coletiva Doméstica São Paulo, vigência atual',
   'https://www.sindomesticastdmsp.com.br/',
   '2025-10-01',
   'Valor de referência do piso salarial da Faixa 1 da CC Doméstica SP vigente em 2026 (estimativa; confirmar com a CC atual pactuada pelo STDMSP). Piso 2024 foi R$ 1.540,59.',
   'Reference floor of Tier 1 in São Paulo Domestic Workers Collective Agreement, valid in 2026 (estimate; confirm with current CC signed by STDMSP). 2024 floor was R$ 1,540.59.')

on conflict (fact_code) do update set
  value_num    = excluded.value_num,
  value_unit   = excluded.value_unit,
  label_pt     = excluded.label_pt,
  label_en     = excluded.label_en,
  source_short = excluded.source_short,
  source_url   = excluded.source_url,
  source_date  = excluded.source_date,
  note_pt      = excluded.note_pt,
  note_en      = excluded.note_en,
  updated_at   = now();

-- Sanity check
do $$
declare n int;
begin
  select count(*) into n from domestic_work.static_fact
   where fact_code in ('dieese_negras_wage_current',
                        'dieese_nao_negras_wage_current',
                        'cc_sp_floor_domestica_current');
  if n < 3 then
    raise exception 'Expected 3 new fact_codes, found %', n;
  end if;
  raise notice 'OK: 3 novos fact_codes inseridos/atualizados';
end$$;
