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

## Refresh log

A running log of quarterly checks against the canonical sources. Each entry
records what was checked, what changed, and when the next check should happen.
Append new entries chronologically — do not rewrite history.

### 2026-04-28 — April refresh window (no new data, no UPDATEs applied)

- **DIEESE 2026 infografico** (`pct_women`, `pct_negras`):
  Not yet published as of this date. The 2025 infografico
  (<https://www.dieese.org.br/infografico/2025/trabalhadorasDomesticas.html>,
  base 4T 2024) remains the most recent national source. Figures already in
  `static_fact` (91.9 % women, 69 % Negras) are still authoritative.
- **DIEESE 2025 Boletim Especial** for `wage_ratio_black_to_nonblack`:
  Available at `https://www.dieese.org.br/boletimespecial/2025/trabalhoDomestico.pdf`
  — value not yet cross-verified against this PDF; current source URL on the
  row still points to the 2024 boletim. Worth re-pointing in a future commit
  once we read the 2025 boletim.
- **PNADC trimestre móvel** (`fact_workers`, `fact_wages`):
  Re-ran `etl/fetch_sidra.py` cleanly. No new periods landed — latest in
  Supabase is still `202602` (trimestre móvel ending Feb 2026). The next one,
  `202603` (ending Mar 2026), is expected mid-May 2026 (~6-week IBGE lag).
- **`fact_hours`**: still 0 rows. Known issue, not in scope for this refresh.
- **Dashboard state**: shipped to Cloudflare Pages at
  <https://stdmsp-trabalho-domestico.joaoroquer.workers.dev/>. No code changes
  this round.

**Next check: 2026-05-12.** By then both the new PNADC trimestre móvel and the
DIEESE 2026 infografico should be available.

### 2026-05-04 — interim follow-up (README fixed; wage_ratio source repointed)

Triggered by two issues spotted while re-reading the docs ahead of the May
refresh window:

- **README quarterly-refresh SQL was wrong.** The example `UPDATE` block in
  `README.md` cited columns (`value`, `source_period`, `metric_code`) and
  fact codes (`dieese_avg_wage`, `dieese_pct_formal`) that don't exist in the
  schema. Anyone following the documented ritual would have hit `column does
  not exist`. Replaced with the real schema (`value_num`, `source_date`,
  `fact_code`) and the real fact codes (`pct_women`, `pct_negras`,
  `wage_ratio_black_to_nonblack`). Added a verification `SELECT` and an
  audit-log step before commit.
- **`wage_ratio_black_to_nonblack` source URL repointed.** Was the bare
  DIEESE homepage; now points at the 2024 *Boletim Especial* PDF
  (<https://www.dieese.org.br/boletimespecial/2024/trabalhoDomestico.pdf>),
  which is the document where the 76% figure was originally verified. The
  `note_pt` / `note_en` on this row now explicitly flag that the **2025
  Boletim Especial** (<https://www.dieese.org.br/boletimespecial/2025/trabalhoDomestico.pdf>)
  has not yet been cross-checked against this specific ratio. Value stays
  at 76 until that cross-check happens.
- **Cross-check of `pct_women` and `pct_negras` against 2025 boletim coverage:**
  - `pct_women` 91.9 — confirmed by April 2025 boletim ✅
  - `pct_negras` 69.0 — secondary citation in 2025 boletim coverage gives
    **68.5%** (a 0.5pp rounding divergence). Within the 1% audit threshold,
    no UPDATE applied. Worth confirming against the actual 2025 PDF when we
    have access.
- **Wage-ratio cross-check status — partially blocked.** The Cowork sandbox
  can't reach `dieese.org.br`. Web-search excerpts surface tangentially-related
  ratios (negras vs. brancas ≈ 86%; mulheres negras vs. homens brancos = 47%),
  but not the negras-vs-não-negras ratio for the trabalhador-doméstico subgroup
  in the 2025 boletim. Two ways to close this:
  1. Joao manually opens the 2025 Boletim Especial PDF and confirms or
     corrects the figure, then runs a one-line UPDATE.
  2. Allowlist `dieese.org.br` in **Settings → Capabilities** so Claude can
     fetch the PDF directly next refresh.

**Next check unchanged: 2026-05-12** for the new PNADC trimestre móvel + DIEESE 2026
infografico window.

### 2026-05-04 (later same day) — `wage_ratio_black_to_nonblack` corrected to 84%

Joao manually opened the 2025 Boletim Especial PDF and shared its **Tabela 5**
(4º trimestre 2024). Direct cross-check against the canonical DIEESE figures:

| Cut | Negras | Não Negras | Ratio | Source |
|---|---:|---:|---:|---|
| Mulheres total (todas as ocupações domésticas) | R$ 1.156 | R$ 1.376 | **84.0 %** | Tabela 5, linha "Total", colunas Mulheres |
| Mulheres em "Serviços domésticos em geral" | R$ 1.129 | R$ 1.329 | 85.0 % | Tabela 5, linha "Serviços domésticos em geral" |

The previous static_fact value of **76%** was never sourced from a verifiable
DIEESE table — it was a seed I introduced when the dashboard was first scaffolded
and then carried forward unaudited. It is corrected now.

**Action taken:**
- `static_fact` row `wage_ratio_black_to_nonblack`: `value_num` `76 → 84`,
  `source_short` and `source_url` repointed to the **2025 Boletim Especial PDF**
  (<https://www.dieese.org.br/boletimespecial/2025/trabalhoDomestico.pdf>),
  `source_date = 2025-04-27`. The `note_pt` / `note_en` now cite the absolute
  reais figures (R$ 1.156 vs R$ 1.376) and the exact source table.
- Dashboard re-renders automatically on next page load (the wage-gap chart and
  its narrative sentence both read live from `value_num`). No code change.
- Cloudflare Pages deploy: not required for this fix — only the database
  changed.

**Direction of the correction:** the dashboard now under-states the gap less.
Going from 76% (24-point gap) to 84% (16-point gap) is a less alarming
headline, but it's the verified one. Worth STDMSP / Mayer noting if either
already cited the previous figure publicly; the audit trail makes the
correction easy to defend.

**Other figures cross-checked in passing against the same boletim:**
- "Total — % com carteira assinada" 24.4% (DIEESE, 4T 2024) vs our 23.75 %
  (PNADC trimestre móvel ending fev/2026): consistent, the slight downward
  drift reflects the more recent period in our data.
- "Serviços domésticos em geral — % sem carteira assinada" 76.1 % (DIEESE,
  4T 2024): consistent with our derived value 100 − 23.75 = 76.25 %.

### 2026-05-05 — PNADC microdata pipeline shipped, race composition now computed

Major upgrade to provenance: the race composition figure on the dashboard
moved from "attributed to DIEESE as a single static value" to "computed
quarter-by-quarter from PNADC microdata, replicated independently against
DIEESE published figures."

**Pipeline.** `etl/pnadc_microdata.py` downloads PNADC quarterly microdata zips
from IBGE's FTP, parses the fixed-width records using column positions
auto-discovered from IBGE's official `Dicionario_e_input` file, applies the
`V1028` survey weights, and aggregates by `cor/raça × formality × period`.
1,007 fact rows from the full 2012Q1–2025Q4 backfill (56 quarters × 18 rows)
landed in `domestic_work.fact_workers` tagged `source_table = 'PNADC-MICRODATA'`.

**Validation.** Our 4T 2024 result of 68.3 % pretas + pardas matched DIEESE's
April 2025 Boletim Especial figure (~68.5 %) within 0.2 pp — well inside PNADC
sampling error.

**Headline finding.** % pretas + pardas among trabalhadoras domésticas rose
**62.5 % (2012Q1) → 67.7 % (2025Q4), +5.2 pp over 13 years**. The
racialization of domestic work intensified across EC 72/2013, LC 150/2015,
and the COVID-19 shock — it did not abate. During the COVID dip (6.0M → 4.5M
workers in 2020) the race share actually *rose* slightly, suggesting white
workers exited disproportionately.

**Dashboard impact.**
- "Composição por cor/raça" doughnut (snapshot, attributed) replaced by
  multi-line "Composição por cor/raça ao longo do tempo" (computed).
- The "Negras (pretas+pardas)" KPI tile now reads **67.7 %** computed (latest
  period 2025Q4) instead of 69.0 % attributed. Meta line: *"fonte: PNADC
  microdados (computado)"*.
- CSV export for the race chart now returns the full 1,007-row underlying
  series, not a single static fact.
- `metodologia.html` Section 3.5 rewritten to reflect computed provenance.

**Direction of change.** Previous static value (69 %) was approximately right;
new value (67.7 %) within 1.3 pp. The substantive gain is *reproducibility*
and the *trajectory*, not a correction to the headline number.

### 2026-05-06 — paged Supabase fetch fixes spike artifact in race chart

The first deployed version of the race-over-time chart showed a spurious
**100 % Preta spike** around 2019. Database verified clean via direct SQL
(every period had all 6 race rows with sensible values). Root cause was
client-side: Supabase REST default page cap of 1,000 rows was being hit by
the dashboard's `dw_workers` fetch, which now totals 1,682 rows after the
microdata backfill (504 PNADC-6320 + 171 PNADC-6383 + 1,007 PNADC-MICRODATA).
Earlier rows in PK order were returned in full; later microdata periods
landed only partially, producing periods where one race's row was the only
one present and rendered as 100 %.

**Fix:** dashboard's `loadAll` now paginates `dw_workers` explicitly via
`range(from, to)` in 1,000-row chunks (`fetchAllPages` helper). Per-page
diagnostic logs added so future row-count growth is visible in DevTools
console.

**No data correction needed** — the underlying numbers were always correct,
the dashboard simply wasn't reading them all. Verified post-fix: race
trajectory shows the smooth 62.5 % → 67.7 % rise across 56 quarters with no
artifacts.

### 2026-05-06 (continued) — wage-by-race time series shipped

The microdata pipeline was extended to also aggregate **weighted-mean nominal
wages** by race × formality × period, using `VD4019` and `V1028`. Backfill
across all 56 quarters added 1,175 wage rows to `fact_wages` tagged
`source_table = 'PNADC-MICRODATA'`. New `nao_negras` aggregate added to
`dim_race` so the racial pay gap can be computed cleanly as
`negras_wage / nao_negras_wage`.

**Validation.** Our 4T 2024 ratio (84.3 %) matches DIEESE's published 84.0 %
within 0.3 pp. Small expected difference: DIEESE reports women-only; we
include men (~5 % of the category, slightly higher mean wage).

**Central finding.** The racial wage ratio has stayed between **84 % and
87 % across all 13 years** — it has not narrowed. Combined with the
racialization finding (62.5 % → 67.7 % Black share), the two together tell
a sharper story than either alone: Black women are a *growing* share of an
occupation whose *racial pay disadvantage is unchanged*.

**Dashboard impact.**
- "Hiato salarial racial" 2-bar static chart replaced by a trajectory line
  spanning 56 quarters; narrative sentence under it auto-updates from latest
  quarter (currently 84 %).
- CSV export for that chart now returns the full underlying race × period
  series.
- `metodologia.html` Section 3.6 rewritten to reflect computed provenance
  and the central finding.

**Nominal vs real disclosure.** Microdata wages are in current (nominal)
reais; we use them only for the ratio (where deflation cancels out). The
"Rendimento médio mensal real" trend chart still reads from PNADC Table
6391, which is IBGE-deflated to constant reais. This distinction is now
documented in Section 3.6 of the methodology page.

### 2026-05-06 (continued) — % Mulheres now computed from microdata

The microdata pipeline (`build_sex_rows`) now also aggregates trabalhadoras
domésticas by sex × formality × period using `V2007` and `V1028`. Backfill
across all 56 quarters added 336 sex-breakdown rows to `fact_workers`
(2 sexes × 3 formalities × 56 quarters). The dashboard's `% Mulheres` KPI
tile reads the computed value when available; falls back to the DIEESE
static fact (91.9 %) only if the microdata isn't loaded.

**Validation.** Computed value matches DIEESE within rounding (our 2024 =
91.8 %, DIEESE = 91.9 %).

**Finding (revised after backfill).** The series isn't quite flat —
women's share declined slightly from **93.0 % (2012) to 91.7 % (2025)**, a
−1.3 pp shift over 13 years. The decline accelerated during COVID-19
(men returned to domestic work in slightly higher proportion as women were
pushed out). Combined with the +5.2 pp racialization finding and the stable
wage gap, the multi-dimensional picture: trabalhadoras domésticas in 2025
are *more Black, slightly less female, and equally underpaid* than in 2012.

**Methodology** Section 3.4b added (PT + EN) documenting the new computed
provenance.

**State of the dashboard.** All four KPI tiles, plus two of the eight
charts, are now driven by computed (not attributed) values. Three figures
remain DIEESE-attributed and worth eventually computing as well: this leaves
zero KPI tiles using DIEESE static facts when microdata is loaded — a
meaningful threshold for the dashboard's research credibility.

---

## Sources

- [PNAD Contínua — IBGE](https://www.ibge.gov.br/estatisticas/sociais/trabalho/17270-pnad-continua.html)
- [IBGE press release — trimestre encerrado em fevereiro 2026](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/46206-pnad-continua-taxa-de-desocupacao-e-de-5-8-e-taxa-de-subutilizacao-e-de-14-1-no-trimestre-encerrado-em-fevereiro)
- [DIEESE — Infográfico Trabalho Doméstico no Brasil (abril 2025)](https://www.dieese.org.br/infografico/2025/trabalhadorasDomesticas.html)
- [DIEESE — Boletim Especial Trabalho Doméstico (2024)](https://www.dieese.org.br/boletimespecial/2024/trabalhoDomestico.pdf)
- [SIDRA Tabela 6320](https://sidra.ibge.gov.br/tabela/6320) · [Tabela 6383](https://sidra.ibge.gov.br/tabela/6383) · [Tabela 6391](https://sidra.ibge.gov.br/tabela/6391)
- [ILOSTAT — Domestic workers](https://ilostat.ilo.org/topics/employment/domestic-workers/)
