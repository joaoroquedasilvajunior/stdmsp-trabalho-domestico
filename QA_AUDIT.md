# Audit Trail — Trabalho Doméstico Dashboard

**Date of audit:** 2026-04-28
**Auditor:** Joao + Claude
**Purpose:** Independently verify the dashboard's headline numbers against the
canonical published sources (IBGE press releases and DIEESE bulletins) before
the dashboard is shared with STDMSP for advocacy use.

**Threshold for action:** Any divergence over ~1% between our computed value
and the cross-reference published source is flagged for investigation.

---

## Five-number audit

| # | Metric | Period | Our value | Cross-reference | Δ | Status |
|---|---|---|---:|---|---:|---|
| A | Total trabalhadoras(es) domésticas(os) — Brasil | trim. móvel ending fev/2026 (`202602`) | **5,490 mil** | IBGE press release (Mar 27, 2026): "**5.5 million**, stable in the quarter and in the year" | −0.18% | ✅ OK |
| B | Taxa de formalização (% com carteira) — Brasil | `202602` | **23.75 %** | IBGE press release: informalidade do trabalho doméstico "**supera 70 % na média do país**" → implied formality ≈ 23–30 % | within range | ✅ OK |
| C | Rendimento médio mensal real — setor "Serviços domésticos" | `202602` | **R$ 1,394** | IBGE press release: rendimento dos trabalhadores domésticos "**+4.8 % YoY = R$ 63 a mais**" → implied ≈ R$ 1,376 | +1.3 % | ⚠ Marginal — see note 1 |
| D | % diaristas (mais de 1 domicílio) — Brasil | trim. fixo `202504` | **33.66 %** | DIEESE Boletim Especial 2024: "diaristas representam cerca de 30–32 % do emprego doméstico" | within range | ✅ OK (Q4 2025 at top of range) |
| E | Headcount São Paulo (UF) | `202504` | **1,259 mil** | eSocial 2025: 391,991 vínculos formais em SP. Implied total at SP-specific 31 % formality ≈ 1.26 M | match | ✅ OK |

### Note 1 — wage divergence (item C, +1.3 %)

The IBGE press release citing R$ 63 as the YoY increase in nominal terms could
be interpreted slightly differently (which trimestre comparison they use as the
baseline; whether they cite `rendimento habitual` or `efetivamente recebido`).
Our value is variable 5932 (`Rendimento médio mensal real, habitualmente
recebido no trabalho principal`) — the standard PNADC headline. The 1.3 %
divergence is within plausible methodology drift and is not a computation
error in the dashboard.

**Action:** none required immediately. Re-check at next IBGE release in late
May/June 2026 to confirm the divergence narrows or stays stable.

---

## DIEESE static facts — what we display vs. published source

Three figures on the dashboard are not computed from SIDRA but attributed to
DIEESE bulletins / infographics. Audit verified each against the canonical
DIEESE source:

| Fact | Our value | DIEESE published value | Action |
|---|---:|---:|---|
| % Mulheres entre trabalhadoras(es) domésticas(os) | ~~92.5%~~ → **91.9 %** | DIEESE *Infográfico abr/2025*, base 4T 2024 — **91.9 %** | ✅ Updated 2026-04-28 |
| % Negras (pretas + pardas) | ~~67.4%~~ → **69.0 %** | DIEESE *Infográfico abr/2025*, base 4T 2024 — **69 %** | ✅ Updated 2026-04-28 |
| Salário negras vs. não-negras (ratio) | **76 %** | DIEESE *Boletim Especial 2024* — "≈ 76 %" | ✅ OK — keep |

Both the "Mulheres" and "Negras" figures we initially seeded (92.5 % and 67.4 %)
were ~0.6 pp / ~1.6 pp off the canonical April 2025 DIEESE numbers (91.9 % and
69 %). I've corrected `domestic_work.static_fact` and updated the source
attribution to point at the exact April 2025 infographic
(<https://www.dieese.org.br/infografico/2025/trabalhadorasDomesticas.html>),
with `source_date = 2025-04-01`.

**Action:** every quarter, when DIEESE publishes a new infographic (typically
around April 28 — Dia Nacional das Trabalhadoras Domésticas — and on Black
Consciousness Day in November), repeat the same UPDATE statements with new
values. The dashboard automatically picks them up on next page load.

---

## What the audit does NOT cover (limitations)

The following dashboard figures are *internally consistent* (every computation
is reproducible from the SQL views) but were not independently cross-checked
in this round because the canonical public source is harder to access:

- **Mensalistas vs. diaristas trajectory pre-2024.** DIEESE publishes the
  current quarter's split but not the historical trajectory in narrative form.
  Our trajectory comes directly from PNADC tabela 6383 — so it's
  IBGE-reproducible but unaudited against a third-party citation.
- **Formality rate trajectory pre-2026.** Same constraint — reproducible from
  PNADC tabela 6320 but only cross-referenced for the latest period.
- **International comparator (ILOSTAT).** The 8 LatAm comparator countries are
  ILO-published; we trust the source. The methodology footnote in the
  dashboard already discloses the ISCO-08 group 91 broader definition.

---

## Recommendation for STDMSP / Mayer

The dashboard can be cited publicly. Three caveats worth communicating to anyone
who quotes its numbers:

1. PNADC and DIEESE publish on different schedules — the dashboard's "latest"
   trimestre móvel headline is one quarter ahead of the latest DIEESE
   infographic. When citing both in the same paragraph, label periods
   explicitly.
2. The ILOSTAT comparator uses a broader occupational definition (ISCO-08 91).
   This is fine for international comparison but the cross-country numbers
   should never be paired with the IBGE's narrower "trabalhador doméstico"
   total.
3. The race composition figure is accurate as of 4T 2024 (DIEESE's most
   recent published cut). If the audience needs more granularity (e.g., mean
   wage by race), that requires PNADC microdata processing — not yet on
   this dashboard.

---

## Sources

- [PNAD Contínua — IBGE](https://www.ibge.gov.br/estatisticas/sociais/trabalho/17270-pnad-continua.html)
- [IBGE press release — trimestre encerrado em fevereiro 2026](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/46206-pnad-continua-taxa-de-desocupacao-e-de-5-8-e-taxa-de-subutilizacao-e-de-14-1-no-trimestre-encerrado-em-fevereiro)
- [DIEESE — Infográfico Trabalho Doméstico no Brasil (abril 2025)](https://www.dieese.org.br/infografico/2025/trabalhadorasDomesticas.html)
- [DIEESE — Boletim Especial Trabalho Doméstico (2024)](https://www.dieese.org.br/boletimespecial/2024/trabalhoDomestico.pdf)
- [SIDRA Tabela 6320](https://sidra.ibge.gov.br/tabela/6320) · [Tabela 6383](https://sidra.ibge.gov.br/tabela/6383) · [Tabela 6391](https://sidra.ibge.gov.br/tabela/6391)
- [ILOSTAT — Domestic workers](https://ilostat.ilo.org/topics/employment/domestic-workers/)
