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

  ('cc_sp_floor_domestica_current', 1874.36, 'BRL',
   'Piso salarial vigente para doméstica em SP (estadual)',
   'Current wage floor for domestic workers in São Paulo (state)',
   'Piso Salarial Estadual SP (Salário Mínimo Paulista), vigência 1º/06/2026',
   'https://www.sindomesticastdmsp.com.br/',
   '2026-06-01',
   'Piso efetivamente exigível: R$ 1.874,36 (piso salarial estadual paulista, vigência 1º/06/2026, jornada 44h/semana). A CCT da categoria fixou piso base de R$ 1.804,00, mas pela regra de prevalência do maior valor o empregador deve pagar o piso estadual, que é superior. Piso 2024 foi R$ 1.540,59.',
   'Effective wage floor: R$ 1,874.36 (São Paulo state minimum wage, effective 2026-06-01, 44h/week). The category''s collective agreement (CCT) set a base floor of R$ 1,804.00, but under the higher-value rule employers must pay the state floor, which is higher. 2024 floor was R$ 1,540.59.')

on conflict (fact_code) do update set
  value_num    = excluded.value_num,
  value_unit   = excluded.value_unit,
  label_pt     = excluded.label_pt,
  label_en     = excluded.label_en,
  source_short = excluded.source_short,
  source_url   = excluded.source_url,
  source_date  = excluded.source_date,
  note_pt      = excluded.note_pt,
  note_en      = excluded.note_en;
-- NB: a tabela live static_fact NÃO tem coluna updated_at (só fact_id, fact_code
-- único, value_num, value_unit, label_*, source_*, note_*). Aplicado via MCP
-- em 2026-07-17.

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
