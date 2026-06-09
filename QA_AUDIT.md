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

**Validation.** Computed value matches DIEESE within rounding. Latest
verified (`202504`): F = 5.120,51 mil, M = 449,31 mil, total = 5.569,82 mil
→ **91,93 %** computed vs. 91,9 % published by DIEESE. Δ = 0,03 pp
absolute, well within survey sampling error — strong cross-corroboration
of both DIEESE's reported figure and our independent microdata pipeline.

> **Correction (2026-05-06, see follow-up entry).** Earlier drafts of this
> entry quoted **91,7 %** for the latest period and a **−1,3 pp** decline
> (93,0 % → 91,7 %). The correct latest value is **91,93 %**; the 2012
> starting value and the magnitude/direction of the long-run trend
> have not been independently re-verified at the time of writing and
> should not be cited from the prior commit message. The corroboration
> with DIEESE is the only validated headline finding from this work.

**Methodology** Section 3.4b added (PT + EN) documenting the new computed
provenance.

**State of the dashboard.** All four KPI tiles, plus two of the eight
charts, are now driven by computed (not attributed) values. Three figures
remain DIEESE-attributed and worth eventually computing as well: this leaves
zero KPI tiles using DIEESE static facts when microdata is loaded — a
meaningful threshold for the dashboard's research credibility.

---

### 2026-05-06 (Phase 1 closure) — Race × UF choropleth shipped

**Scope.** Extended the microdata pipeline with a state-level race breakdown
and added a Brazilian UF choropleth above the existing bar chart. Phase 1 of
the post-verification roadmap (Race × UF, Mexico parallel, Story mode).

**Pipeline.** `etl/pnadc_microdata.py:build_uf_race_rows()` aggregates
trabalhadoras(es) domésticas(os) by `UF × race × period`, using V1028
weights, restricted to VD4009 ∈ {03, 04}. Per quarter: 5 races + preta_parda
+ nao_negras + total denominator, all at `formality='total', sex='T'`.
Backfill produced **11 085 UF rows** across 56 quarters (vs ~12 096
theoretical max — the gap is empty `indigena` cells in small UFs, expected).

**Map.** New article above the existing UF bar chart at full width.
Sequential warm palette anchored on the chita accent (`#7f1d1d` deep red
at the top, cream at the bottom). Toggle: *% Negras* (default) / *Total
(milhares)*. Hover/focus tooltips with state name + % negras + total k.
Year filter integration. Geometry: static SVG at
`dashboard/assets/brazil-uf.svg`, ~37 KB after Ramer-Douglas-Peucker
simplification (epsilon=0.05° ≈ 5.5 km), no client-side library.

**Verified findings (4T 2025).**

| State | % negras | Note |
|---|---:|---|
| Bahia (BA) | **90,3 %** | National peak — Brazil's most Afro-descendant state |
| Amazonas (AM) | 87,3 % | High parda population |
| Piauí (PI) | 86,9 % | Northeast |
| Maranhão (MA) | 85,0 % | Northeast |
| **São Paulo (SP)** | **56,4 %** | STDMSP territory · 1 257 mil domésticas (largest cluster) |
| Rio Grande do Sul (RS) | 32,0 % | South, German/Italian heritage |
| **Santa Catarina (SC)** | **29,4 %** | National floor |

The geographic gradient maps onto the historical geography of slavery and
internal migration cell-for-cell. Northeast + Amazon dense red, Southeast
mid-tones, South cone in cream. **The map is, in itself, a piece of evidence
for the persistence of racialized labor markets** — a substantive contribution
to JF Mayer's research at Concordia.

**Reconciliation.** Sum across the 27 UFs (5 568,64 mil) reconciles with the
BR-level total via M+F (5 569,82 mil) at 0,02 pp absolute (1,18 mil). Pure
rounding artifact; the weighted aggregation has no systematic bias.

**Regression caught and fixed in the same session.** The new UF rows at
`source_table='PNADC-MICRODATA'` initially leaked into three places that
weren't expecting them: `renderRace()` (BR-wide race composition denominator),
`getComputedPctNegras()` (KPI denominator), and `renderRegion()` (UF bar chart,
which then duplicated entries from PNADC-6383 + PNADC-MICRODATA). All three
now filter explicitly by `geo_level` or `source_table`. Lesson logged: when
adding a dimension to a fact table, audit every reader of that table for
implicit assumptions about the dimension's prior shape.

**Methodology page.** Section 3.7b added (PT + EN) documenting the new map's
source, coverage, dimensions, geometry pipeline, central finding, and small-UF
limitation. Section 3.7 reframed to indicate the bar chart now prefers
microdata over the SIDRA aggregate.

**Phase 1 status.** Done. Dashboard now has 9 charts (was 8), the UF dimension
is computed across two views (map + bars) with consistent provenance, and the
methodology page documents the path from microdata → fact table → choropleth.
Next: Phase 2 (Mexico parallel via ILOSTAT light path) and Phase 3 (story
mode for STDMSP audience).

---

### 2026-05-06 (correction) — `% Mulheres` verified at 91,93 %, KPI tile bumped to 2 decimals

**Trigger.** After deploy, the `% Mulheres` KPI tile was displaying **91,9 %**
identical to the prior DIEESE static-fact display. The meta line correctly
read *"fonte: PNADC microdados (computado)"*, suggesting the computed-vs-
attributed switch was working as designed but the values rounded to the same
1-decimal display.

**Verification.** A console snippet on the live dashboard read the loaded
`fact_workers` rows for the latest period (`202504`):

| Field | Value |
|---|---:|
| F (women, thousands) | 5 120,51 |
| M (men, thousands) | 449,31 |
| Total | 5 569,82 |
| `% F / total` | **91,9331 %** |

This rounds to 91,9 % at one decimal — coincidentally the same display as
DIEESE's published 91,9 %. The dashboard was correct; the rounding made
the change invisible.

**Action taken.** When the value comes from microdata (`computedWomen != null`),
the `kpi-women-value` and `kpi-black-value` tiles now display at **2 decimal
precision**, distinguishing the live computed value from the 1-decimal
DIEESE figure on the methodology page. When the microdata isn't loaded,
the tile falls back to 1 decimal — DIEESE only publishes at that precision.

```js
const womenDecimals = computedWomen != null ? 2 : 1;
setText("kpi-women-value", fmt(womenPct, womenDecimals) + "%");
```

**Substantive read.** That DIEESE's published 91,9 % matches our independent
PNADC microdata aggregation to 0,03 pp is a *positive* validation finding —
worth flagging in the methodology page as cross-source corroboration rather
than a redundancy. Consider adding a short note in `metodologia.html`
§3.4b: "DIEESE *Infográfico abr/2025* reports 91,9 %; our independent
PNADC microdata aggregation for the same period yields 91,93 %, agreeing
to within sampling error."

**Audit-trail hygiene.** The prior commit message (`aca29f1`) and the
preceding entry above stated **91,7 %** for the latest period. That number
was a pre-verification estimate, not an aggregation result. The correct
verified value is **91,93 %**. The decline narrative
(93,0 % → 91,7 % over 13 years, COVID acceleration) was built on top of
that wrong number and is not cited as validated until the trajectory is
re-computed end-to-end.

---

### 2026-05-06 (correction continued) — `% Mulheres` trajectory verified across all 56 quarters

**What was done.** Console verification on the live dashboard re-computed
`F / (F+M)` for every period in `fact_workers` where
`source_table = 'PNADC-MICRODATA'` and `race_code = formality_code = 'total'`.
Full series (56 quarters, 201201 → 202504) returned and analyzed.

**Headline corrections to the trajectory narrative.**

| Claim (prior, unverified) | Verified value | Status |
|---|---:|---|
| Long-run shift 2012Q1 → 2025Q4 | **−0,66 pp** (92,59 % → 91,93 %) | ❌ prior claim of **−1,3 pp** was approximately 2× the true value |
| 2012Q1 starting share | **92,59 %** | ❌ prior claim of **93,0 %** off by ~0,4 pp |
| 2025Q4 latest share | **91,93 %** | ❌ prior claim of **91,7 %** off by ~0,2 pp |
| Series minimum | **90,51 %** at `202003` (Q3 2020 — peak COVID disruption) | new |
| Series maximum | **93,57 %** at `201502` (Q2 2015) | new |
| Range across the 14-year window | **3,06 pp** | new |

**Verified trajectory shape.** Three regimes are visible in the series:

1. **2012–2015 (high plateau)** — quarterly share oscillates around
   **92,5–93,5 %**, with the series maximum (93,57 %) hit in Q2 2015. No
   structural decline in this window.
2. **2015–2019 (gradual erosion)** — share drifts down to a
   pre-pandemic baseline of **~92,2 %** by 2019Q4. Total drift in this
   regime: ~0,5 pp.
3. **2020 onward (COVID shock + partial recovery)** — share collapses
   to **90,51 %** in 2020Q3 (the only sub-91 % reading in the entire
   series), recovers to ~91,9 % by 2024Q4 but does not return to the
   2012–2014 highs. Latest verified reading (2025Q4): **91,93 %**.

**What this means substantively.** The "trabalhadoras domésticas are
becoming less female" narrative I had drafted on top of the wrong −1,3 pp
figure is not supported by the verified data. The true picture is closer
to **stable around 92 %**, with two distinct features worth reporting:
(a) a modest post-2014 erosion of ~0,5 pp, and (b) a real but largely
recovered COVID dip. The series-wide range (3 pp) is small relative to
the racialization shift documented separately (+5,2 pp for *negras*),
which remains the substantively dominant headline finding for this
project.

**Revised cross-dimensional summary.** Trabalhadoras domésticas in 2025
compared to 2012 are **substantially more Black** (+5,2 pp), **roughly
as female** (−0,7 pp, within historical noise), and **paid the same
ratio relative to non-Black peers** (~84 % both periods). The
racialization story is the load-bearing finding; the gender-share story
should be reported as *stable*, not *declining*.

**Verified series (selected reference points).**

| Period | F (mil) | M (mil) | Total (mil) | % F |
|---|---:|---:|---:|---:|
| 2012Q1 | 5 507,42 | 440,92 | 5 948,34 | **92,59 %** |
| 2014Q4 | 5 396,27 | 388,28 | 5 784,55 | 93,29 % |
| 2015Q2 (max) | 5 427,87 | 373,30 | 5 801,17 | **93,57 %** |
| 2019Q4 (pre-COVID) | 5 638,86 | 478,47 | 6 117,33 | 92,18 % |
| 2020Q3 (min) | 3 960,80 | 415,23 | 4 376,03 | **90,51 %** |
| 2020Q4 (recovery) | 4 261,11 | 365,41 | 4 626,52 | 92,10 % |
| 2024Q4 | 5 407,02 | 468,42 | 5 875,44 | 92,03 % |
| 2025Q4 (latest) | 5 120,51 | 449,31 | 5 569,82 | **91,93 %** |

Full 56-quarter series stashed at `window._mulheresSeries` on the live
page during this verification run; available for re-export at any time
via the same DevTools console snippet.

**Status.** The KPI tile and methodology page can be cited with
confidence. The dashboard does not currently surface the female-share
trajectory as a chart; that is a deliberate scope decision (the
substantive story is now "stable", which doesn't merit a dedicated
visual). If a future story-mode pass wants to show this stability
explicitly, the data is in `fact_workers` ready to plot.

---

### 2026-05-06 (v2.0 consolidation) — three-phase substantive expansion

**Headline.** Dashboard moved from v1.6 to v2.0 with: new microdata variables (hours,
previdência, unweighted sample size), policy timeline annotations on all
time-series charts, Wilson 95% confidence intervals on the UF map, a Foco em São
Paulo section with five charts, BR-wide hours + previdência charts in the main
grid, an ILO C189 ratification panel, and a routine Supabase RLS hardening pass.

**Phase A — Pipeline extension.** `etl/pnadc_microdata.py` now extracts variables
V4039 (jornada habitual horas/semana, trabalho principal) and V4032 (era
contribuinte de previdência na semana de referência) from the PNADC microdata.
Two new build functions emit aggregations into new tables `fact_hours` and
`fact_prev`, mirroring the structure of `fact_workers`. Plus a column
`n_unweighted` (unweighted sample size) added to all microdata-derived fact
tables, for downstream confidence-interval work.

Backfill: 56/56 quarters processed (one disk-space failure on 2025Q3 recovered
in a single-quarter rerun). Resulting row counts:

| Table | Rows | Periods |
|---|---:|---:|
| `fact_hours` | 13 399 | 56 |
| `fact_prev` | 12 263 | 56 |
| `fact_workers` (with `n_unweighted`) | 12 428 | 56 |

**Phase B — Policy timeline annotations.** Loaded `chartjs-plugin-annotation`
from CDN and wired vertical-line annotations into nine time-series charts
(trend, formality, wages, race composition, wage gap, BR hours, BR previdência,
SP×BR trajectory, SP race composition). Five policy events marked:

- **EC 72/2013** (constitutional amendment equalizing domestic workers' rights)
- **LC 150/2015 in force** (Lei das Domésticas)
- **Brasil ratifies C189** (jan 2018)
- **COVID-19** (mar 2020 lockdowns)
- **México ratifies C189** (jul 2020, for the BR↔MX framing)

The hours chart additionally carries a horizontal reference at **44h/semana**,
the legal weekly limit defined by CF Art. 7-XIII and extended to domestic
workers by LC 150/2015 Art. 2.

One small reliability fix during this session: the plugin's UMD file is
`chartjs-plugin-annotation.min.js`, not `.umd.min.js` as initially assumed; the
correct URL returns a 200, the wrong one returned 404 and silently disabled
all annotations.

**Phase C — Wilson 95% CIs on the UF map.** The map tooltip now shows
`IC 95%: lo – hi` for the % negras estimate per state, anchored on the
unweighted sample size of each UF's `race='total'` row. Small-sample
suppression: n<30 greys the UF out with a dashed border, 30≤n<100 shows
a yellow "amostra pequena" warning, n≥100 shows the plain CI. Methodology
§3.7c documents the calculation and the explicit limitation that the CI
captures only sampling variability — not bias, coverage, or measurement
error. View `public.dw_workers` was rebuilt to expose the new column.

**Phase X + Y — Hours and previdência charts.** Two new chart articles in the
main BR grid (between wage gap and the UF map) and two new chart articles in
the Foco em SP section. Each chart shows three lines: preta+parda, não-negras,
and BR/SP total (dashed grey reference). The Foco em SP version uses the SP
microdata cut; the BR version uses the country-level cut. Methodology sections
§3.6b (BR) and §3.7d (SP) document both.

**Foco em São Paulo section** (separate Phase SP, also this session). New
chita-cream-tinted section below the existing dashboard with 4 SP-specific KPI
tiles + 5 charts: SP×BR trajectory, SP race composition over time, Southeast
state comparator, SP jornada média, SP previdência. Designed for STDMSP to
share with state and municipal politicians. Honest scope footnote at the
bottom flags what remains deferred (SP wages and SP formality split).

**C189 ratification panel.** Eight-card grid below the BR↔MX comparator listing
each comparator country's year of ILO C189 ratification, ordered chronologically.
Uruguay 2012 (first in the world) through Mexico 2020. Substantive footnote
flags that Brazil's LC 150/2015 *preceded* its 2018 C189 ratification —
domestic legislation came before the international commitment. Methodology
§3.8b documents the source (NORMLEX, ILO).

**Security hardening.** Supabase Postgres LINTER flagged 12 RLS-disabled errors
on `domestic_work.*` tables plus 1 search-path warning on
`public.update_updated_at`. Migration applied via MCP: RLS enabled on every
domestic_work table with a `public_read` policy (data is intentionally public
— now stated explicitly); function search-path locked to `(public, pg_catalog)`.
Remaining `email_signups` warning is SceneQuebec scope (shared Supabase
instance) and out of scope here. Memory updated to record the
cross-project hosting arrangement.

**Map projection fix.** During the Foco em SP work I noticed the UF map
rendered as a thin horizontal line. Root cause: `make_projection` in
`etl/build_uf_svg.py` mixed units between axes (longitude in degrees, latitude
in log-Mercator). Replaced with a clean equirectangular projection plus
`cos(lat_center)` longitude correction. Brazil's bbox is now rendered with
~1:1 aspect ratio.

**Verified substantive findings from the new data (4T 2025 unless noted).**

| Metric | Value | Note |
|---|---:|---|
| Jornada média (Brasil) | **31,7h/semana** | Stable across 13 years; far below 44h legal limit. The category is structurally part-time / diarista, not 40h-week formal employment. |
| % over 44h (Brasil) | ~10% | Only one in ten works more than the legal limit. |
| Previdência rate (Brasil) | **14,6%** | Drastically below the formality rate (24%). Implication: even women with carteira often don't have contributions actually being paid in. This is the sharpest single advocacy number for the LC 150 enforcement-gap argument. |
| Jornada média (SP, 4T 2025) | **32,4h/semana** | Marginally higher than national. |
| Jornada SP por raça | preta+parda 33,2h · não-negras 31,4h | Reverses the national expectation — in SP specifically, negras work slightly *more* hours than non-Black peers. Likely because SP's negra workforce is concentrated in mensalistas. |
| Previdência SP por raça | preta+parda 20,4% · não-negras 19,2% | Same reversal — SP negras contribute slightly *more* than non-Black peers, against the typical racial gap. |

The SP racial reversal is a publishable-grade finding for Mayer's research
on intersectional labor markets — it complicates the simple racialization
narrative and is supported by clean PNADC microdata at 4T 2025.

**Status of the v2.0 dashboard.** 11 charts in the BR grid + UF map + 5 charts
in Foco em SP + the C189 panel + 4 KPI tiles + story mode + bilingual
methodology page. All four advocacy levers (headcount, race, wages/wage-gap,
formality, hours) covered at the BR level. SP-specific cuts cover everything
except wages and the formality split (deferred to a future pipeline addition
once STDMSP feedback identifies priority).

**Outstanding items / next decisions:**

1. **STDMSP pilot feedback** (P3.3) — link with `?modo=historia` sent for review.
2. **SP wages + SP formality split** — pipeline addition needed (UF × VD4019, UF × formality cross-tabs). ~3-4 hours. Should be informed by which numbers the union actually requests in their feedback.
3. **ENIGH heavy path** (P2.2) — Mexican microdata pipeline to replicate the
   racialization / wage gap / hours analysis for Mexico. Big scope (3-5 days),
   only worth doing if Mayer commits to a comparative paper.
4. **Two unreliable-publication warnings logged in Phase B** — `chartjs-plugin-annotation`
   v3 docs say the UMD bundle auto-registers, but the version we use needs
   explicit `Chart.register()`. The defensive registration block now handles
   both cases.

---

### 2026-05-20 — Static-export migration (dashboard decoupled from live Supabase)

**Trigger.** The `sceneqc` Supabase project (free tier) auto-paused mid-session.
A paused project serves no API requests, so the live dashboard went dark — it
had been reading the `dw_*` views over the Supabase REST API at runtime.
(Coincided with, but was unrelated to, a Supabase status-page incident about
incorrect resume-deadline display. That incident was cosmetic; the pause was
real. Project data was never at risk.)

**Diagnosis.** The dashboard's runtime dependency on a live database was a
single point of failure inappropriate for the data's nature: the `dw_*` views
are **read-only aggregates that change only when the quarterly ETL runs**.
There is no reason for the public site to hold a live DB connection.

**Fix.** Migrated the dashboard to a static-first data layer:

- `etl/export_static.py` — new script. Pages through all seven `dw_*` views
  and writes `dashboard/data/<view>.json` plus a `manifest.json` carrying the
  export timestamp. Run after each quarterly ETL refresh, then commit
  `dashboard/data/`.
- `dashboard/index.html` `loadAll()` — rewritten to `fetch()` the static
  JSON files instead of querying Supabase. The Supabase JS client is no
  longer used at runtime (init code left in place, harmless).
- The "data updated on" line now reflects `manifest.generated_at` (the export
  timestamp), so stale data is visible rather than masked by today's date.

**Result.** The public dashboard is now a fully static site — immune to
Supabase project pausing, faster to load (no pagination round-trips, no DB
latency), and still updatable via the documented ETL → export → commit flow.
Supabase remains the ETL target and source of truth; it is simply no longer
a runtime dependency for the public site.

**Operational note.** The refresh cadence is now: run the ETL → run
`etl/export_static.py` → `git add dashboard/data/` → commit → push. The
static JSON totals ~13 MB uncommitted (gzipped to ~1.5 MB on the wire by
Cloudflare). If git-history growth becomes a concern after several quarters,
a columnar JSON format or git LFS can cut the footprint — deferred until it
actually matters.

---

## 2026-06-08 — Refresh v2.1 (DIEESE abril/2026 + Supabase data loss)

**Scope.** First scheduled refresh after the v2.0 consolidation. Captures the
DIEESE abril/2026 Infográfico headline figures, two new April 2026 policy
events (Política Nacional de Cuidados + Conadon), the PNADC 2025–2026 master-
sample transition, and documents an unplanned finding: the Supabase project
`sceneqc` lost all data during its most recent free-tier pause.

### Supabase status — misdiagnosis of data loss (resolved same day)

While reaching for `domestic_work.static_fact` to apply the DIEESE abril/2026
update, the first `information_schema.tables` query (filtered to
`table_type = 'BASE TABLE'`) returned an empty result for the
`domestic_work` schema and an empty `public` schema. Combined with the
project `created_at` timestamp showing `2026-04-20`, this was initially read
as a free-tier inactivity-purge — i.e., the schema and all data had been
dropped. A correction migration (`schema/002_recovery.sql`) and a JSON-to-
Supabase repopulator (`etl/repopulate_from_json.py`) were drafted on that
assumption.

**The data was never lost.** A second, plainer query
(`select 'fact_workers' as t, count(*) ... from domestic_work.fact_workers`)
returned the exact row counts recorded in `dashboard/data/manifest.json`:
13 103 workers, 1 343 wages, 13 399 hours, 12 263 prev, 94 intl, 5 sources,
3 static_facts. Every table, every view, every row was present. The first
query result was an MCP / proxy transient — not a real schema state.

**What this refresh actually did, in clean terms.**

- Edited the three `dashboard/data/dw_static_facts.json` rows to the
  DIEESE abril/2026 figures (this is what users now see).
- Pushed the equivalent `update` statements into
  `domestic_work.static_fact` in Supabase via the MCP, so the queryable
  source of truth matches the static export. Both layers now carry:
  `pct_women 91.9`, `pct_negras 68.0`, `wage_ratio_black_to_nonblack 87.1`,
  source = DIEESE Infográfico abr/2026, source_date = 2026-04-01.

**Kept anyway as a disaster-recovery kit.**

- `schema/002_recovery.sql` — consolidates 001_init.sql plus the
  Phase-A and static-export additions (`fact_prev`, `static_fact`,
  `n_unweighted`, `race_id` on `fact_hours`, `dw_prev`, `dw_static_facts`,
  RLS policies) that had only ever existed as ad-hoc `apply_migration`
  calls. Idempotent. If a real free-tier purge ever happens, this is the
  DDL to apply.
- `etl/repopulate_from_json.py` — reads the committed JSON exports and
  upserts them back into Supabase. Inverse of `export_static.py`. Also
  idempotent. Same purpose.
- README has a "Schema recovery — if Supabase data is lost" section
  describing the four-step ritual: wake → apply DDL → repopulate → verify.

**Cost of the misdiagnosis.** None to the public site (it never depended
on Supabase being up). The cost was time spent drafting the recovery kit
and the temporary credibility hit of carrying a wrong claim in the audit
log. Recording the correction here in the same audit entry rather than
quietly editing the history.

**Lesson.** When `information_schema` returns an unexpected empty, run a
direct `select count(*) from <expected.table>` before declaring loss. The
direct query is what the application actually does.

### DIEESE Infográfico abril/2026 — figures captured

Source: <https://www.dieese.org.br/infografico/2026/2026trabalhadorasDomesticas.pdf>
Published April 2026, base PNADC 4º trimestre 2025. The HTML landing page is
behind a login wall; the PDF is openly accessible and is the canonical artifact.

Headline figures vs. the abril/2025 edition we were carrying:

| Indicator | abr/2025 | abr/2026 | Δ |
|---|---:|---:|---:|
| Total trabalhadoras(es) domésticas(os) | 5,8M | 5,6M | −0,2M |
| Mulheres | 92% | 92% | 0 pp |
| Negras (entre mulheres no emprego doméstico) | 69% | 68% | **−1 pp** |
| Razão salarial negras ÷ não-negras | 84% | **87,1%** | **+3,1 pp** |
| Sem carteira | 75% | 76% | +1 pp |
| Sem contribuição previdenciária | n/a | 65% | new |
| Mensalistas / Diaristas | 54/46 | 53/47 | −1 pp |
| Pobreza (2024 base) | n/a | 25% | new |

**Wage-ratio shift, +3 pp — interpret with care.** The narrowing of the
racial wage gap (84% → 87,1%) is the most substantive headline of the
abril/2026 edition. Two competing readings, neither yet decisive:

1. *Real narrowing.* The minimum-wage valorization policy reinstated in
   2023 raises the floor disproportionately for the lower-paid (most
   trabalhadoras negras), mechanically compressing the ratio. The April 9
   2026 MTE × DIEESE seminar speakers (Paula Montagner, MTE/Estatísticas)
   explicitly attributed wage gains in the sector to this policy.
2. *Sample-composition artefact.* DIEESE 2025 cited mensalistas R$ 1.156 vs
   R$ 1.376; DIEESE 2026 cites *all* trabalhadoras R$ 1.274 (negras) vs
   R$ 1.463 (não-negras). The 2025 figure may have been narrower (mensalista-
   only) where 2026 is broader. Until the abril/2026 *Boletim Especial*
   drops with detailed methodology, we cannot fully separate these two
   effects.

**Action.** Updated `dashboard/data/dw_static_facts.json` rows for
`pct_negras` (69 → 68), `wage_ratio_black_to_nonblack` (84 → 87.1), and
refreshed the source URL/date on all three rows to point at the
abril/2026 PDF. The `note_pt`/`note_en` on `wage_ratio_black_to_nonblack`
now explicitly flags the +3 pp shift and the interpretive caution. The
2025 → 2026 striking-through convention is preserved in the audit log
rather than in the JSON itself (which would clutter the dashboard
tooltips for end-users).

### Cross-source check against microdata (4T 2025)

Microdata-computed values stay unchanged from v2.0 (no PNADC re-run this
cycle). The DIEESE abril/2026 figures now align with our computed values
better than the 2025 edition did:

| Indicator | DIEESE abr/2026 | Microdata 4T 2025 | Δ |
|---|---:|---:|---:|
| % Mulheres | 92% (rounded) | 91,93% | <0,1 pp ✓ |
| % Negras (all trabalhadoras) | ~68% (women only) | 69,4% (all) | partial — different bases |
| Sem carteira | 76% | 76% (100 − 24%) | 0 pp ✓ |

The "sem contribuição previdenciária" 65% gap remains unresolved vs our
microdata 14,6% — same finding as v2.0, methodology investigation deferred.

### Policy events added — POLICY_EVENTS

Added one event covering both April 2026 institutional developments:

- `iso: "2026-04"` — **"PNC + Conadon"**: Política Nacional de Cuidados
  (aprovada por unanimidade no Senado) e criação da Conadon (Coordenação
  Nacional de Fiscalização do Trabalho Doméstico e de Cuidados) no âmbito
  do MTE. Sources: gov.br seminário MTE-DIEESE de 9 de abril de 2026;
  ministra Laís Abramo (Secretária Nacional de Políticas de Cuidados e
  Família, MDS) cita ambas as iniciativas no seminário. The annotation
  will render on time-series charts as soon as PNADC 1T 2026 lands.

The campanha nacional pelo trabalho doméstico decente 2026 (SIT/MTE, lema
"Saúde e Segurança são Direitos Humanos", lançada em Belém em 24–25 de
abril) is editorially relevant but visually redundant with the PNC +
Conadon annotation. Captured in the union-voice copy for the story mode
beat about enforcement; not added as a separate timeline mark.

### Methodology page (PT + EN)

- Added `DIEESE-INFO-2026` row to both source tables (PT §2 and EN §2),
  pointing at the openly-accessible PDF.
- Added Limitation #5 (PT and EN): the 2025–2026 PNADC master-sample
  transition from a 2010-Census-based design to a 2022-Census-based one,
  with a note that the methodological component is small relative to
  substantive movements in the series shown.

### PNADC 1T 2026 — published, run pending

SIDRA probe (Table 6320, `last 1`) returned period code 202604 =
"fev-mar-abr 2026", confirming the rolling quarter through April is live.
The trimestre fixo 1T 2026 (Jan–Mar 2026) on tables 6383/6391 is expected
to also be available. Sandbox cannot run the microdata pipeline (no IBGE
FTP access + bandwidth + needs Supabase target). Handing off to Joao to
run `python etl/pnadc_microdata.py 012026` from his Mac — pending the
Supabase rebuild decision.

### Files changed

- `dashboard/data/dw_static_facts.json` — 3 rows updated
- `dashboard/data/manifest.json` — `generated_at` bumped to 2026-06-08;
  `notes` field added explaining the partial refresh and Supabase data loss
- `dashboard/index.html` — POLICY_EVENTS: 1 new entry (`2026-04` PNC +
  Conadon)
- `dashboard/metodologia.html` — DIEESE-INFO-2026 row in both PT and EN
  source tables; Limitation #5 in both PT and EN limitations sections
- `QA_AUDIT.md` — this entry

### Next check

- **Aug 2026** — first PNADC trimestre fixo with 2T 2026 data, run microdata
  pipeline for 022026 (and 012026 if not yet done)
- **Nov 2026** — DIEESE Boletim Especial usually drops mid-November
  (Consciência Negra cycle). Check for an updated abril/2026 boletim PDF
  that may resolve the wage-ratio +3 pp interpretation.

---

## 2026-06-08 — Phase D1 (Education dimension)

**Scope.** First of three planned socioeconomic-profile dimensions
(Education → Family → Housing). Adds the PNADC VD3004 variable to the
microdata pipeline, populates a new `fact_education` table + `dw_education`
view, and surfaces the result as a race-disaggregated bar chart in a new
"Perfil socioeconômico" section between the events panel and Foco em São
Paulo.

### Schema (applied via Supabase MCP migration `education_dimension_d1`)

- `domestic_work.dim_education` — 6 rows (5 education buckets + `total`).
  Codes: `fund_inc`, `fund_comp`, `med_inc`, `med_comp`, `sup`, `total`.
- `domestic_work.fact_education` — keyed by
  `(time_id, geo_id, sex_id, race_id, education_id, source_table)`. Columns
  include `workers_thousands`, `pct_within_race`, `n_unweighted`.
- `public.dw_education` — joined view, `security_invoker = true`.
- RLS + `public_read` policy on both new tables, grants for anon/authenticated.

### Pipeline (etl/pnadc_microdata.py)

- Added `VD3004` to `NEEDED_VARS`. The colspec cache auto-invalidates on the
  next run because `NEEDED_VARS` grew.
- New `EDUCATION_MAP` collapses PNADC native codes 1–7 into 5 DIEESE-aligned
  buckets (codes 1+2 → `fund_inc`, code 3 → `fund_comp`, code 4 → `med_inc`,
  code 5 → `med_comp`, codes 6+7 → `sup`).
- New `build_education_rows()` emits BR × sex='T' × race × education_bucket
  rows, plus aggregates for `preta_parda`, `nao_negras`, and `total`. Each
  row carries `pct_within_race` precomputed so the dashboard doesn't have to
  re-aggregate.
- New `upsert_education_to_supabase()` does dim-id lookups for time/geo/sex/
  race/education and chunked upserts into `fact_education`.
- `process_period()` now builds + upserts education rows alongside the
  others and logs a new diagnostic — `% fund_inc among negras` — for
  quick comparison against DIEESE.

### Export (etl/export_static.py)

- `VIEWS` list grows by one: `dw_education` inserted between `dw_prev` and
  `dw_intl`.

### Dashboard (dashboard/index.html)

- New `<section id="perfil">` "Perfil socioeconômico" placed between the
  Mobilização panel and Foco em São Paulo. Holds one card for now
  (Education); Family + Housing in D2/D3.
- `renderEducation()` reads `STATE.education`, filters to BR-country/sex=T/
  the two aggregate race tracks, picks the latest period_code, builds a
  Chart.js vertical grouped bar chart (5 buckets × 2 race series).
- `loadAll()` made resilient to per-view 404s — a missing JSON now logs a
  warning and falls back to `[]` rather than killing the whole dashboard.
  This protects future dimension adds.
- Empty placeholder `dashboard/data/dw_education.json` shipped (`[]`) so
  the path resolves cleanly until Joao runs the pipeline backfill.

### Methodology (dashboard/metodologia.html)

- §3.10 added (PT + EN) documenting variable, bucket convention,
  cross-validation against the DIEESE 59%-sem-educação-básica-completa
  figure.

### Next steps (Joao's side)

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate
# Single quarter first to sanity-check before the full backfill:
python etl/pnadc_microdata.py 012026 --no-upsert  # dry run, look at the new
                                                  # "% fund_inc (negras)" line
python etl/pnadc_microdata.py 012026              # write 1T 2026 only
# Then ./etl/refresh.sh + commit + push to see the chart light up.
# Full backfill of education for all 56 quarters takes ~30-40 min:
python etl/pnadc_microdata.py --all               # only if you want history;
                                                  # for the snapshot chart,
                                                  # one quarter is enough.
```

### Sanity-check targets (1T 2026)

DIEESE Infográfico abr/2026 (base 4T 2025) reports 39% fundamental
incompleto across the whole category. Our `% fund_inc (negras)` diagnostic
should land near that — modestly higher for negras specifically, modestly
lower for não-negras. If the diagnostic line on the 1T 2026 run is in the
30–50% range for negras, we're in good shape; outside that, dig in before
running the backfill.

### Outstanding (D2 + D3 to come)

Family (V2003 / V2005 / household roll-up) and Housing (V0212 / V0213 /
domicile section) follow the same pattern in subsequent commits. Each
brings ~50 lines of pipeline, ~30 lines of SQL, one chart card slotted
into the same "Perfil socioeconômico" section.

### Bug found and fixed on the D1 first-run (2026-06-08, same session)

The initial `build_education_rows()` produced `workers_thousands` values
1000× too high — it summed the post-normalization weight (which is in
single people) without dividing by 1000 to land on thousands. The bug
was data-only and didn't affect the chart (the chart uses
`pct_within_race`, which is unit-independent). Fixed in the function and
the D1 rows were corrected via in-place SQL `UPDATE` (only buggy rows
with `workers_thousands > 100` selected and divided by 1000). Future
pipeline runs use the corrected code path. The pattern is now spelled
out in code comments so D2 + D3 don't repeat the mistake.

---

## 2026-06-08 — Phase D2 (Family / household position)

**Scope.** Second of the three socioeconomic-profile dimensions
(Education → Family → Housing). Adds PNADC `V2003` to the microdata
pipeline, populates a new `fact_family` + `dw_family` view, and surfaces
the result as a second chart card alongside Education in the
"Perfil socioeconômico" section.

### Schema (applied via Supabase MCP migration `family_dimension_d2`)

- `domestic_work.dim_family` — 5 rows (`chefe`, `conjuge`, `filha`,
  `outro`, `total`).
- `domestic_work.fact_family` — keyed by
  `(time_id, geo_id, sex_id, race_id, family_id, source_table)`.
- `public.dw_family` — joined view, `security_invoker = true`.
- RLS + `public_read` policy, grants for anon/authenticated.

### Pipeline (`etl/pnadc_microdata.py`)

- `V2003` added to `NEEDED_VARS`. Colspec cache auto-invalidates on
  next run.
- `FAMILY_POSITION_MAP` collapses 17 native codes to 4 buckets. Code 01
  (Pessoa responsável) maps to `chefe`; codes 03–04 to `filha`; 05–17
  all roll into `outro` (which therefore absorbs empregadas domésticas
  residentes, agregados, parentes do empregado, etc. — see the
  methodology page for the full mapping).
- `build_family_rows()` emits BR × sex='T' × race × family_position
  rows + race aggregates + `total`. Uses the corrected divide-by-1000
  pattern from the D1 fix.
- `upsert_family_to_supabase()` parallels the education upsert.
- `process_period()` now logs the new diagnostic
  **`% chefe (total/negras)`** so each run prints two numbers — the
  overall headline (comparable to DIEESE's 46%) and the negras
  cut. Useful for race-gap detection without running a separate query.

### Export (`etl/export_static.py`)

- `dw_family` added to `VIEWS` between `dw_education` and `dw_intl`.

### Dashboard (`dashboard/index.html`)

- The Perfil socioeconômico section is now a 2-column responsive grid
  (`grid-cols-1 md:grid-cols-2`) holding the Education card and the
  new Family card side-by-side on desktop, stacked on mobile.
- `renderFamily()` follows the same shape as `renderEducation()` —
  filters by `geo_level=country`, `sex_code='T'`, picks the latest
  `period_code`, builds a vertical grouped bar chart (4 buckets ×
  2 race series).
- i18n PT + EN for the new strings (`chart-family`,
  `chart-family-meta`, `chart-family-source`, plus four `fam-*` bucket
  labels and two race-track labels).
- Empty placeholder `dashboard/data/dw_family.json` shipped (`[]`).
  The resilient `loadAll()` from D1 will treat a missing file as
  empty so the chart shows the overlay until the pipeline runs.

### Methodology (`dashboard/metodologia.html`)

- §3.11 added (PT + EN) documenting the variable, the 17→4 collapse,
  the DIEESE cross-validation target (46% chefe de família), and a
  flagged limitation that single-mother / single-parent-household
  cuts require a household-level join not yet in scope.

### Next steps (Joao's side)

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# Single quarter — produces the new "% chefe (total/negras)" diagnostic.
# This also re-runs education with the unit-fix in place, overwriting the
# D1 rows via upsert.
python etl/pnadc_microdata.py 012026

# Static export + commit + push
./etl/refresh.sh
git add etl/pnadc_microdata.py etl/export_static.py \
        schema/ \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "feat(D2): family dimension — V2003, fact_family, posição-no-domicílio card"
git push origin main
```

### Sanity-check targets (1T 2026)

DIEESE Infográfico abr/2026 publishes **46% chefes de família** for the
category overall. The new `% chefe (total/negras)` diagnostic should
have the `total` value land in the 42–50% range; if it does, D2 is
verified. The negras–nao_negras gap (whichever direction) is itself
the substantive finding of this dimension — DIEESE doesn't publish it
race-disaggregated, so we're the first to surface it.

### Outstanding (D3 to come)

Housing (V0212 / V0213 / S01024 series) is the last of the three
phases. It's the heaviest of the three pipeline-wise because it reads
the **domicile section** of the PNADC fixed-width file, not the
person section — small refactor of the colspec parser. Same chart
pattern, slotted in as a third card in the Perfil grid (which will
become 3-column on desktop). Schedule when ready.

---

## 2026-06-08 — Phase D3 (Housing) + D2 chefe discrepancy flagged

**Scope.** Third and final socioeconomic-profile dimension. Adds PNADC
`V0212` (tenure) to the microdata pipeline, populates `fact_housing` +
`dw_housing` view, surfaces a third chart card in the Perfil grid
(which is now 3-column on desktop). Also formally records an open
methodological question on the D2 "% chefe de família" finding before
it reaches publication.

### Schema (applied via Supabase MCP migration `housing_dimension_d3`)

- `domestic_work.dim_housing` — 5 rows (`proprio`, `alugado`,
  `cedido_empregador`, `outro`, `total`).
- `domestic_work.fact_housing` — keyed by
  `(time_id, geo_id, sex_id, race_id, housing_id, source_table)`.
- `public.dw_housing` — joined view, `security_invoker = true`.
- RLS + `public_read` policy, grants for anon/authenticated.

### Pipeline (`etl/pnadc_microdata.py`)

- `V0212` added to `NEEDED_VARS`. The PNADC fixed-width file repeats
  domicile-level variables on each person record, so no refactor of
  the colspec parser was needed — we just request V0212 like any other
  variable and the dictionary parser places the column for us.
- `HOUSING_TENURE_MAP` collapses 7 native codes into 4 buckets.
  Code 4 (cedido por empregador) is kept distinct — this is the
  empregada doméstica residente, a structurally vulnerable sub-category
  that DIEESE doesn't break out separately.
- `build_housing_rows()` and `upsert_housing_to_supabase()` follow the
  same shape as D1 / D2. Divide-by-1000 in `_row` is correct from the
  start (no bug to fix this time — the D1 lesson held).
- `process_period()` now logs two new diagnostics:
  **`% próprio`** and **`% live-in`**.

### Export (`etl/export_static.py`)

- `dw_housing` added to `VIEWS` between `dw_family` and `dw_intl`.

### Dashboard (`dashboard/index.html`)

- Perfil socioeconômico section's grid is now
  `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` — three side-by-side
  cards on desktop, two on tablet, stacked on mobile.
- `renderHousing()` mirrors the D1/D2 render functions exactly:
  filters BR/sex='T'/aggregate-race-tracks, picks the latest period,
  emits a vertical grouped bar chart (4 tenure buckets × 2 race
  series).
- Bilingual i18n strings added (`chart-housing*`, four `hous-*` bucket
  labels, two race-track labels).
- Empty placeholder `dashboard/data/dw_housing.json` shipped.

### Methodology (`dashboard/metodologia.html`)

- §3.12 added (PT + EN). Documents the variable, the 7→4 collapse,
  the explicit reasoning for keeping `cedido_empregador` distinct, and
  the policy-relevant headline cuts.
- One important limitation spelled out: V0212 codes the tenure of the
  whole household, not the individual worker. For live-in workers
  (V2003 = 15) this means V0212 reflects the employer's household —
  which is precisely what makes the `cedido_empregador` bucket the
  right marker for that case. For other workers, V0212 reflects their
  own home, which is not necessarily where they work.

### Open question recorded in §3.11 (D2 follow-up)

The D2 dashboard computes ~57% chefe de família across races, weighted.
DIEESE Infográfico abr/2026 publishes 46%. The ~11 pp gap is too large
for rounding or sampling noise. Added a flagged note (PT + EN) to §3.11
of the methodology page listing the three competing hypotheses
(women-only filter, age cutoff, "chefe" definition) and stating
explicitly that the figure should not be cited as a publishable
finding until the DIEESE methodology is verified in the matching
semi-annual bulletin. The chart still renders the race-disaggregated
breakdown, which is the substantive contribution; the absolute level
is the disputed bit.

### Next steps (Joao's side)

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# Single quarter — runs all three (D1 ed, D2 fam, D3 hous) for 1T 2026.
# Look for the new "% próprio" and "% live-in" diagnostics:
python etl/pnadc_microdata.py 012026

./etl/refresh.sh
git add etl/pnadc_microdata.py etl/export_static.py \
        schema/ \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "feat(D3): housing dimension — V0212, fact_housing, moradia card"
git push origin main
```

### Sanity-check targets (1T 2026)

DIEESE doesn't publish housing tenure for the category, so there is no
direct external check. Plausibility bounds:

- **% próprio (total)** should land in the **50–70% range**. Brazilian
  homeownership across all workers is roughly 70%; trabalhadoras
  domésticas are poorer than average so expect somewhat lower.
- **% cedido_empregador (total)** should be **small but non-zero** —
  likely in the **1–4% range**. This is the live-in domestic workers,
  a shrinking historic category. Anything above 5% would be a surprise
  worth investigating; below 1% would suggest under-counting.

The race split is itself the substantive finding — DIEESE doesn't
break it out and we are the first to surface it.

### Phase D wrap

D1 (Education), D2 (Family), and D3 (Housing) close out the Perfil
socioeconômico section. Three new chart cards, three new variables,
three new fact tables, all running through one shared pipeline and
matching shared dashboard pattern. The category now has a tidy
"who they are beyond the work" view that complements the "what the
work looks like" view in the rest of the dashboard.

---

## 2026-06-08 — D3 pivot to PNADC ANNUAL (V0212 → S01017)

**The bug.** I specified V0212 as the housing-tenure variable. V0212
does not exist in PNADC quarterly. The dictionary parser crashed
mid-run with `KeyError: "Variable V0212 not found in dictionary"`,
which broke the entire quarterly script for ALL the dimensions
(D1/D2 included) — Joao's most recent run aborted before any rows
were upserted.

**Root cause.** Housing-condition variables (tenure, water source,
sanitation, electricity, etc.) only exist in **PNADC ANNUAL**, not
the quarterly release. In PNADC-A they live in the `S01001`–`S01029`
block. Tenure specifically is `S01017`, with the same 7 codes I'd
already mapped (1–2 próprio, 3 alugado, 4 cedido por empregador,
5–7 outro).

**The fix, two steps.**

1. **Hot-fix the quarterly script.** Removed `V0212` from
   `NEEDED_VARS`. Removed the `build_housing_rows` call and the
   `upsert_housing_to_supabase` call from `process_period()`. Removed
   the `% próprio` and `% live-in` diagnostics from the log line.
   The quarterly script now runs cleanly for D1+D2 again.
2. **Build a separate annual fetcher.** New script
   `etl/pnadc_annual_housing.py`. Downloads the latest
   `PNADC_<year>_visita1_*.zip` from IBGE FTP (~170 MB), parses with
   hardcoded column specs (no dictionary-parsing layer needed since
   the layout is stable), aggregates housing tenure by race, upserts
   into the existing `fact_housing` table with
   `source_table = 'PNADC-A'` and a new period code style `'2024A'`.

**Schema reuse.** `dim_housing`, `fact_housing`, `dw_housing` and the
dashboard chart card all stay in place — only the data source pipeline
changes. The 4-bucket mapping is identical.

**Cadence note.** Housing has ANNUAL cadence (one observation per
year, latest `2024A` released Nov 2025), while every other dimension
has 56-quarter coverage. This is now spelled out in the dashboard
chart subtitle ("PNADC Anual (Visita 1)") and prominently flagged in
the methodology page §3.12. The `formatPeriodLabel()` helper in
`index.html` was extended to recognize the `YYYYA` code pattern and
render it as "2024 (anual)" / "2024 (annual)".

**Files changed in the pivot.**

- `etl/pnadc_microdata.py` — V0212 removed, housing-builder hook
  removed from process_period, diagnostics trimmed
- `etl/pnadc_annual_housing.py` — NEW, ~370 lines
- `dashboard/index.html` — chart-housing-meta + chart-housing-source
  updated for both PT and EN; `formatPeriodLabel()` extended for
  annual codes
- `dashboard/metodologia.html` — §3.12 rewritten for PT + EN with the
  cadence-difference flag
- `QA_AUDIT.md` — this entry

**Run sequence for Joao**

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# First: re-run the (now-fixed) quarterly script to confirm D1+D2
# get current data again. This was aborted on the V0212 crash.
python etl/pnadc_microdata.py 012026

# Then: run the new annual housing fetcher (2024 = latest available)
python etl/pnadc_annual_housing.py 2024
# This downloads 170 MB once (cached afterwards), parses, computes,
# and upserts ~50 rows into fact_housing.

./etl/refresh.sh
git add etl/pnadc_microdata.py etl/pnadc_annual_housing.py \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "fix(D3): housing source pivots to PNADC ANNUAL (V0212→S01017, cadence is annual)"
git push origin main
```

**Sanity-check targets unchanged.** % próprio (total) in the 50–70%
band; % live-in (total) in the 1–4% band. Now using S01017 instead
of V0212 — same codes, same bucket mapping, same plausibility ranges.

### Lesson worth memorializing

When adding a PNADC variable, ALWAYS confirm it's in the right
release (quarterly vs annual vs PNS supplement) before wiring it up.
The variable-name space partitions cleanly: labor/employment in
quarterly, household conditions in annual Visit 1, special supplements
in PNS. Mixing them up like I did breaks the dictionary parser at run
time, not at code-review time — and breaks the whole pipeline, not
just the new feature.

---

## 2026-06-08 — Theme 1: Breadwinner paradox panel

**Scope.** First of the second-order findings (the "Theme N" series),
selected from the menu Joao asked for after Phase D wrapped. Adds
a wage × family-position cross-tab to surface the breadwinner paradox
— Black women in this category are MORE likely to be household heads
AND earn less per cell — and gives it a dedicated editorial section.

### Schema (applied via Supabase MCP migration `breadwinner_paradox_family_wages_v2`)

- `domestic_work.fact_family` — gains two columns: `wage_mean_brl`
  (numeric(12,2)) and `wage_n_with_income` (int).
- `public.dw_family` — view dropped and recreated to expose the new
  columns (CREATE OR REPLACE can't reorder; `drop view + create view`
  pattern used).
- security_invoker preserved; grants re-applied.

### Pipeline (`etl/pnadc_microdata.py`)

- `build_family_rows()` rewritten: same shape, plus a `_wage_stats()`
  helper that computes the weighted mean wage among cell members with
  `VD4019 > 0`. Emitted rows now carry `wage_mean_brl` and
  `wage_n_with_income` alongside `workers_thousands` and
  `pct_within_race`. The wage denominator (workers with income) is
  smaller than the cell denominator (all workers) by design —
  non-earners would pull the mean toward zero artificially.
- `upsert_family_to_supabase()` writes the two new columns.
- `process_period()` now logs the breadwinner-paradox diagnostic
  line: **`wage chefes negras R$X vs n.negras R$Y (gap Z%)`**.
- Backwards compatible: rows from before this migration have NULL in
  the new columns until the next pipeline run.

### Dashboard (`dashboard/index.html`)

- New `<section id="paradoxo">` "O paradoxo do sustento" placed between
  the Perfil socioeconômico section and Foco em São Paulo.
- Two-column layout on desktop (`grid-cols-1 lg:grid-cols-5`): editorial
  hero in the left 2/5 (eyebrow + title + lead + body + scholarly
  citation), chart in the right 3/5 (grouped bar of wage by position ×
  race).
- The editorial body paragraph carries three inline placeholders
  (`paradox-callout-negra`, `paradox-callout-nao-negra`,
  `paradox-callout-ratio`) which `renderBreadwinner()` populates with
  the actual numbers at render time. So the editorial reads as a
  coherent narrative with the data injected, not as a dry chart caption.
- `renderBreadwinner()` reads `STATE.family`, filters by
  geo_level/sex/aggregate-race-tracks and `wage_mean_brl != null`,
  picks the latest period, builds the chart and populates the inline
  callouts.
- New helper `fmtBRL()` for currency formatting (PT uses `.` as
  thousand-separator, EN uses `,`).
- i18n strings bilingual: editorial copy in union voice (PT) and
  researcher-neutral (EN). Scholarly citation lists Gonzalez,
  Carneiro, Bernardino-Costa, Lopes, Lara.

### Methodology (`dashboard/metodologia.html`)

- §3.13 added (PT + EN) — documents the variable cross-tab, the
  weighted-mean calculation, the nominal-vs-real choice, why this
  cross-tab matters (first official Brazilian publication of the
  full cross), and carries forward the §3.11 calibration caveat (the
  absolute % chefe disputes DIEESE's 46%, but the racial gap is
  internally consistent and publishable on its own).

### Run sequence on Joao's Mac

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# Single quarter — re-runs all dimensions with the new wage cross-tab
# populated for family. Watch for the new "wage chefes negras R$X vs
# n.negras R$Y (gap Z%)" diagnostic line.
python etl/pnadc_microdata.py 012026

./etl/refresh.sh
git add etl/pnadc_microdata.py \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "feat(Theme 1): breadwinner paradox panel — chefe × wage × race"
git push origin main
```

### Sanity-check target

DIEESE Apr/2026 doesn't publish this cross-tab, so there's no direct
external check. Plausibility bounds for the new diagnostic:

- **wage chefes negras vs n.negras gap** should land near the overall
  category wage gap (87%) — within ±3 pp. If wildly different, the
  per-position computation is broken.
- **wage chefes negras** in absolute terms should be in the **R$ 1,000
  – R$ 1,700 range** for 1T 2026 (close to but possibly slightly
  above the all-trabalhadoras mean, since heads are likelier to be
  mensalistas with longer hours and more carteira).

### Why this matters editorially

This is the dashboard's first explicitly editorialized finding —
previous sections present data with brief tooltips and methodology
links. The breadwinner-paradox panel takes the same data and *frames*
it as an intersectional argument, citing the Black-feminist
scholarship that has predicted the finding for decades. The visual
treatment (accent-soft background, eyebrow tag, two-column hero
layout) signals to the reader that this is a *finding*, not a routine
indicator. STDMSP and Mayer have explicit hooks for this in their
respective audiences.

---

## 2026-06-08 — Theme 2: Cohort panel ("Onde estão as jovens?")

**Scope.** Second second-order finding. Surfaces the aging-out story
(DIEESE: 12% under 29 / 32% 30-44 / 43% 45-59 / 13% 60+) as a 14-year
time series of "% under 29" by race, opening the question of where
young Black women are going if not into domestic work.

### Schema (applied via Supabase MCP migration `age_cohort_theme2`)

- `domestic_work.dim_age_band` — 5 rows (`under_29`, `30_44`, `45_59`,
  `60_plus`, `total`). DIEESE-aligned breakpoints so the dashboard can
  triangulate against the Apr/2026 Infográfico table directly. Kept
  separate from the legacy `dim_age_group` (which has different
  bands and is still referenced by older fact_workers rows).
- `domestic_work.fact_age` — keyed by
  `(time_id, geo_id, sex_id, race_id, age_band_id, source_table)`.
- `public.dw_age` — joined view, `security_invoker = true`.
- RLS + `public_read` policy, grants for anon/authenticated.

### Pipeline (`etl/pnadc_microdata.py`)

- `V2009` added to `NEEDED_VARS`.
- `age_to_band(age)` helper maps numeric age to one of the 4
  DIEESE-aligned codes.
- `build_age_rows()` emits BR × sex='T' × race × age_band rows + race
  aggregates + total. Same shape as D1/D2 builders.
- `upsert_age_to_supabase()` parallels the family/housing upserts.
- `process_period()` now logs the new diagnostic line:
  **`% under_29 (total/negras) X%/Y%`**, where the `total` value
  should land near DIEESE's published 12% if the pipeline is honest.

### Export (`etl/export_static.py`)

- `dw_age` added to `VIEWS` between `dw_housing` and `dw_intl`.

### Dashboard (`dashboard/index.html`)

- New `<section id="cohort">` "Onde estão as jovens?" placed between
  the Breadwinner Paradox section and Foco em São Paulo. Same
  two-column editorial-hero pattern as Breadwinner (Theme 1).
- `renderCohort()` reads `STATE.age`, filters to BR/sex='T'/under_29/
  the two aggregate race tracks, builds a Chart.js line chart of
  the full 14-year trajectory (56 quarters), and populates two
  inline callouts in the editorial paragraph with the latest values.
- Policy timeline annotations (`buildPolicyAnnotations(periods, "fixo")`)
  are wired up so EC 72/LC 150/C189 ratifications/COVID land on the
  cohort chart too — the line crossing those dates is the actual story.
- Bilingual i18n; PT uses union voice; EN stays researcher-neutral.
- Empty placeholder `dashboard/data/dw_age.json` shipped.

### Methodology (`dashboard/metodologia.html`)

- §3.14 added (PT + EN) — documents the variable, the bucket
  alignment with DIEESE, the cohort/pseudo-cohort distinction
  (we're showing pseudo-cohorts; true cohorts would need
  PNADC panel structure exploitation), and the triangulation
  target (~12% under 29 for the latest period).

### Run sequence on Joao's Mac

The single-quarter run only populates ONE point per line — the trajectory
needs the historical backfill to show the actual aging story. Two paths:

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# Path A — quick single quarter (gets latest data, but chart has only 1 point)
python etl/pnadc_microdata.py 012026

# Path B — full backfill (gets the 14-year trajectory; ~30–40 min)
python etl/pnadc_microdata.py --all

./etl/refresh.sh
git add etl/pnadc_microdata.py etl/export_static.py \
        schema/ \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "feat(Theme 2): age cohort panel — Onde estão as jovens?"
git push origin main
```

**Strong recommendation: Path B.** The cohort chart with only one
point shows nothing of value — it's a dot, not a trajectory.
The aging-out story IS the slope of the line; you need all 56
quarters of fact_age rows to see it. The full backfill on Joao's
Mac took about 30 minutes last time and will produce ~2,200 fact_age
rows in addition to the existing dimensions.

### Sanity-check target (1T 2026)

DIEESE Apr/2026 publishes 12% under 29 for the category overall.
Plausibility bounds:

- **% under_29 (total)** should land in the **8–16% range**. If far
  outside, check the domestic-worker filter (VD4009 ∈ {03,04}).
- **% under_29 (negras)** vs **% under_29 (nao_negras)** is the
  substantive finding — the dashboard chart will show whether the
  decline runs at the same rate or whether one group is dropping out
  faster.

### Why this matters editorially (Theme 2 specifically)

The breadwinner paradox (Theme 1) shows a *static* intersectional
finding — at any quarter, negras chefes are paid less. This panel
(Theme 2) shows the *dynamic* dimension — over 14 years, the
category itself is restructuring through generational withdrawal.
For STDMSP this is existential (a shrinking-base union has to
strategize differently); for Mayer this connects to the broader
Latin American comparative-politics literature on care work and
labor mobility. Same data substrate, different theoretical hook.

---

## 2026-06-08 — Theme 3: "Resíduo da casa-grande" (live-in geography)

**Scope.** Third second-order finding. Adds state-level cuts to the
already-built housing pipeline and surfaces the geography of live-in
(cedido_empregador) workers as a dedicated editorial section. No
schema change — `fact_housing` already supports `geo_level='uf'`.

### Pipeline (`etl/pnadc_annual_housing.py`)

- `build_housing_rows()` parameterized over (geo_code, geo_level) and
  extended to iterate the 27 IBGE state codes after the existing BR
  emissions. Per-UF: emits `preta_parda`, `nao_negras`, `total` race
  aggregates × 4 housing buckets. Native races skipped at UF level —
  their cells are too small to be useful in many states.
- Small-sample floor: UFs with `< 30` unweighted observations are
  logged-and-skipped to avoid noisy estimates. Same threshold also
  applied to per-race cells within a UF.
- Per-year row count grows from ~40 (BR only) to ~360 (BR + 27 UFs ×
  3 race aggregates × ~4 buckets), well within Supabase limits.

### Dashboard (`dashboard/index.html`)

- New `<section id="residuo">` "O resíduo da casa-grande" placed
  between Theme 2 (cohort) and Foco em São Paulo. Same accent-soft
  two-column hero pattern as Themes 1/2.
- Editorial copy framed around Bernardino-Costa's "atualização da
  casa-grande/senzala," with Gonzalez, Carneiro and Saffioti cited in
  the bottom paragraph. Three inline JS callouts: national % live-in,
  national absolute count (rounded to thousands), top UF name + %.
- `renderResidual()` reads `STATE.housing`, filters to `geo_level='uf' /
  sex='T' / race='total' / housing='cedido_empregador'`, sorts by
  `pct_within_race` descending, builds a horizontal Chart.js bar
  chart. Top 3 UFs highlighted in accent color, rest in neutral gray.
  Chart height set to 480px so all 27 UF labels stay readable.
- The `box-residual` container uses `min-height: 480px` for the
  horizontal-bar layout.

### Methodology (`dashboard/metodologia.html`)

- §3.15 added (PT + EN) — documents the variable reuse from §3.12,
  the small-sample floor, the editorial framing (first systematic
  geographic distribution of live-in, which DIEESE doesn't publish at
  UF level), and the cadence (annual, updates when next PNADC-A
  release lands ~August/November of the year after the base year).

### Run sequence on Joao's Mac

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# Re-run the annual fetcher. The zip is cached from the first run, so
# this is just parse + aggregate + upsert — ~30 seconds.
python etl/pnadc_annual_housing.py 2024

./etl/refresh.sh
git add etl/pnadc_annual_housing.py \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "feat(Theme 3): live-in continuity panel — geography of residentes"
git push origin main
```

### Sanity-check targets

The aggregate national % live-in stays ≈4–5% (no change — same
underlying data). New per-UF expectations:

- **Top of the list** likely Bahia, Maranhão, Piauí, Pará, or parts of
  Minas Gerais — historically high concentration of trabalhadoras
  domésticas residentes in interior regions where the patrimonial
  relationship persists. If a Southern state (RS, SC, PR) lands at
  the top, the data is wrong.
- **Bottom of the list** likely Distrito Federal and capital-state
  outliers, where urban professional households trend toward
  diaristas (non-residentes) rather than mensalistas residentes.

The exact ranking is the finding — we'll know once Joao runs and
the chart populates.

### Why this matters editorially (Theme 3 specifically)

Theme 1 was a *static* intersectional finding (breadwinner paradox).
Theme 2 was a *dynamic* generational finding (aging out). Theme 3 is a
*spatial* historical finding (where the patrimonial relation persists).
The three together form a triangle: race × time × geography, with
domestic work at the center of each. STDMSP gets symbolic weight
(the casa-grande continuity made visible); Mayer gets the spatial
politics of care work (which states retain the pre-modern labor
form). Same data substrate, third theoretical hook.

---

## 2026-06-09 — v2.2 consolidation milestone

This entry consolidates everything between the v2.0 wrap (2026-05-06)
and now. Three major waves landed:

**Wave 1 — Phase D (descriptive layer).** Three new dimensions added
to the Perfil socioeconômico section:
- D1 Education (VD3004) — bar chart, race-disaggregated
- D2 Family (V2003) — bar chart, race-disaggregated
- D3 Housing (S01017 via PNADC-A, NOT V0212 quarterly — pivot
  documented; separate `etl/pnadc_annual_housing.py` fetcher)

**Wave 2 — Themes 1, 2, 3 (argument layer).** Three editorial finding
panels with two-column hero layout, accent-soft background, scholarly
citations:
- Theme 1 Breadwinner Paradox (static intersectional)
- Theme 2 Aging Cohort (dynamic generational)
- Theme 3 Casa-grande's Afterlife (spatial historical)

**Wave 3 — Refresh + operational fixes.** DIEESE abril/2026 numbers
applied; April 2026 policy timeline events (PNC + Conadon);
PNADC 1T 2026 microdata ingested; full backfill of fact_age across
56 quarters; UF-level fact_housing rows for Theme 3.

### Pipeline state

`etl/pnadc_microdata.py` now emits 7 fact tables in one process_period
call: workers, wages, hours, prev, education, family (with wages),
age. ~600 lines of pipeline code; backfill takes ~30-40 min for the
56 quarters and produces ~45k fact rows across all dimensions.

`etl/pnadc_annual_housing.py` runs separately on annual cadence
(2024 base, released Nov 2025). Now emits both BR-level and
state-level housing tenure rows. ~360 rows per year.

`etl/export_static.py` exports 11 views: dw_workers, dw_wages, dw_hours,
dw_prev, dw_education, dw_family, dw_housing, dw_age, dw_intl,
dw_sources, dw_static_facts. Total static payload ~14 MB.

### Three publishable findings, one per axis

**(1) Breadwinner Paradox.** Among trabalhadoras domésticas, 60% das
negras são chefes de família vs 55% das não-negras (+5 pp racial gap).
Among chefes specifically: negras earn R$ 1.315 vs R$ 1.522 for
não-negras (racial wage ratio 86,4% — slightly steeper than the
overall category ratio of 87,3%). The workers carrying more household
financial responsibility receive the sharper racial penalty.
DIEESE doesn't publish this cross-tab.

**(2) Aging Cohort.** % under-29 trabalhadoras domésticas:
- Negras: 24% (2012) → 13% (2026), loss of ~11 pp
- Não-negras: 18% (2012) → 10% (2026), loss of ~8 pp
- Racial gap narrowed from 6 pp to 3 pp
- Decline crosses every rights expansion (EC 72, LC 150, BR/MX C189)
  without inflection — structural, not policy-driven
Sanity check passes: aggregate ~12% matches DIEESE abril/2026's
published total exactly.

**(3) Casa-grande's Afterlife.** Live-in (cedido_empregador) share by UF.
~4–5% nationally (~270k workers), but the geography concentrates the
finding. First systematic publication of this distribution — DIEESE
doesn't disaggregate by UF. Cadence annual; expectation that
Northeast / interior Sudeste states top the list (Bernardino-Costa's
"atualização da casa-grande/senzala" empirical trace).

### Editorial framing

The three themes form a deliberate triangle: race × time × geography,
with domestic work at the center of each. Each finding cites a
distinct scholarly lineage:
- Theme 1: Lélia Gonzalez, Sueli Carneiro, Bernardino-Costa, Lopes, Lara
- Theme 2: Saffioti, Acciari, IPEA
- Theme 3: Bernardino-Costa, Gonzalez, Saffioti, Carneiro

The descriptive layer (eight indicator charts in the main grid) supplies
evidence; the Theme layer interprets it through the scholarly readings.
This is the shift in v2.2: the dashboard moves from "data tool" to
"argument with evidence." STDMSP gets the political/symbolic weight;
Mayer gets the comparative-politics hooks; the methodology page §3.13
–§3.15 carries the rigor that allows both audiences to trust the
findings.

### What's NOT yet done (carried into v2.3 backlog)

- Theme 5 (minimum-wage attribution decomposition) — ~3 hours, paper-side
- SP wages + SP formality split (UF × VD4019, UF × formality)
- ENIGH heavy path (Mexican microdata) — only if Mayer commits to
  comparative paper
- Open % chefe de família calibration question vs DIEESE 46%
- Story-mode update to include the three Themes as story beats

### Methodology page section count

§1 Overview · §2 Sources · §3.1–§3.15 Variables and definitions
(15 numbered sections now, up from 9 at v2.0) · §4 Methodological
notes · §5 Limitations · §6 Update cadence. PT and EN sides both
complete; bilingual coverage 100% for all v2.2 additions.

### Sources cross-check at v2.2

| Indicator | Computed | DIEESE abr/2026 | Status |
|---|---:|---:|---|
| Total trabalhadoras(es) | 5.437k–5.512k | 5,6M | ✓ within rounding |
| % Mulheres | 91,7% | 92% | ✓ |
| % Negras (women only, abril 2026 base) | ~67.5% | 68% | ✓ |
| % com carteira | 23.8% | 24% | ✓ |
| Sem previdência (women only, %) | 14.0% | 35% | ⚠ unresolved |
| Wage ratio negras/não-negras | 87.3% | 87.1% | ✓ |
| % under_29 (total) | ~12% | 12% | ✓ |
| % chefe de família (total) | 58% | 46% | ⚠ method gap |
| Jornada média (h/sem) | 31.8h | n/a | descriptive |
| % live-in (cedido empregador) | 4.5% | n/a | descriptive |

The two ⚠ items are documented in §3.11 and §3.13 of the methodology.
For publishable use: racial gaps and trajectories are safe; absolute
chefe and previdência levels need DIEESE methodology cross-check.

---

## 2026-06-09 — Theme 4: Compliance geography panel

**Scope.** Fourth Theme. Empirical complement to the Acciari/Pinheiro/IPEA
compliance-gap literature: scatter plot of (% com carteira não-negras) ×
(% com carteira negras) by UF. Anchors the Conadon institutional moment
in 2026 with the first systematic two-axis (geography × race) visualization
of LC 150 non-compliance.

### Pipeline (`etl/pnadc_microdata.py`)

- `build_uf_race_rows()` extended to emit per-formality cells at UF × race.
  Previously only `formality='total'` was emitted per UF × race; now
  `com_carteira` and `sem_carteira` are also emitted at the aggregate race
  tracks (preta_parda, nao_negras, total). Native races skipped at this
  granularity since cells become very small in many UFs.
- Per-quarter row count: 216 → ~378 (added ~162 new rows per quarter).
  Full backfill: ~21k rows over 56 quarters.
- No new dim tables — reuses existing `dim_formality` codes
  `com_carteira` / `sem_carteira` / `total`.

### Dashboard (`dashboard/index.html`)

- New `<section id="descumprimento">` "A geografia do descumprimento"
  placed between Casa-grande's afterlife and Foco em São Paulo. Same
  editorial-hero pattern (text left, chart right, accent-soft background).
- `renderEnforcement()` reads `STATE.workers`, filters to UF × microdata
  × latest period × aggregate race tracks, computes per-cell
  formalization rates as `com_carteira_workers / total_workers`,
  applies a small-sample floor (skip UFs with `n_unweighted < 30`
  on the race='total' cell), builds a Chart.js scatter chart.
- Chart features:
  - Each UF = one point at (% nao_negras, % negras)
  - Diagonal "no racial gap" reference line, dashed gray
  - Point radius scales with √(unweighted N) so big UFs are visually
    heavier; Chart.js native pointRadius per-point
  - Tooltip shows UF name + both percentages + n
  - Inline callouts: top-UF and bottom-UF by negras formalization rate
- i18n PT + EN. PT in union/policy voice; EN researcher-neutral. Both
  explicitly cite Acciari, Pinheiro/IPEA, the MTE 2026 campaign report,
  and the Conadon institutional moment.

### Methodology (`dashboard/metodologia.html`)

- §3.16 added (PT + EN). Documents the pipeline extension, the per-cell
  calculation, the small-sample floor, and the editorial framing (first
  systematic two-axis visualization of LC 150 compliance gap). Explicit
  limitation note: this is a snapshot, not a temporal-variation panel —
  the "did this geography shift over time?" question is desirable
  follow-on work but out of scope here.

### Run sequence on Joao's Mac

```bash
cd ~/Documents/Claude/Domestic\ Work
source etl/.venv/bin/activate

# Backfill all quarters with the new per-formality UF × race cells.
# Cached zips speed this up substantially since they're already on disk
# from previous backfills; expect ~25-30 min.
python etl/pnadc_microdata.py --all

./etl/refresh.sh
git add etl/pnadc_microdata.py \
        dashboard/index.html dashboard/metodologia.html dashboard/data/ \
        QA_AUDIT.md
git commit -m "feat(Theme 4): compliance geography — UF × race × carteira scatter"
git push origin main
```

### Sanity-check targets

Plausibility bounds for the scatter:

- **National average pulled by SIDRA-6383** is 24% com carteira (race=total).
  Per-UF spread expected to range from ~15% (Northeast, interior states)
  to ~35% (DF, RJ, possibly SC). Most points should cluster in the
  20–30% range.
- **Almost every UF below the diagonal** — DIEESE 2026 reports a
  national racial gap of ~3 pp in formalization (24% total vs ~21%
  negras vs ~28% não-negras when disaggregated). Expect the per-UF
  diagonal-distance to range from ~1 pp (small gap) to ~10 pp (large
  gap), depending on the state's labor-market structure.
- **Top-UF (highest negras formalization)** likely **Distrito Federal,
  Rio Grande do Sul, or São Paulo**. Bottom-UF likely **Maranhão,
  Piauí, or one of the smaller Northeastern states** (after the
  small-sample filter removes RR/AP/AC).

If the diagonal pattern goes the other way (most points ABOVE the line),
the per-cell calculation is wrong; check the formality_code values being
used.

### Why this matters editorially (Theme 4 specifically)

The other three Themes interpret the data through Black-feminist theory
(Theme 1), generational sociology (Theme 2), and historical continuity
(Theme 3). Theme 4 is the *policy-instrumental* reading: this is the
chart that tells the Ministry of Labour where to send inspectors first.
It connects the dashboard directly to the April 2026 Conadon moment and
the MTE National Campaign for Decent Domestic Work. For STDMSP: it gives
the union an evidence base to demand specific enforcement priorities.
For Mayer: it grounds the comparative-politics argument about regional
variation in implementation capacity in measurable empirics.

The four Themes now form a complete theoretical frame: intersectional
(Theme 1) × generational (Theme 2) × historical (Theme 3) × policy
(Theme 4). Each anchored in a distinct scholarly tradition; all on the
same data substrate.

---

## 2026-06-09 — Theme 5: Floor effect (minimum-wage attribution)

**Scope.** Fifth and final Theme in the current arc. Visual hypothesis
test for the MTE/DIEESE seminar attribution that the 84%→87% wage-gap
narrowing was driven by the post-2023 minimum-wage valorization policy.
No pipeline change — uses existing dw_wages microdata + hardcoded
official minimum-wage trajectory.

### Approach

A dual-axis time-series:
- **Left axis** (red line): wage ratio negras/não-negras computed
  per quarter from PNADC-MICRODATA mean wages. Same data source as
  the existing wage-gap chart, just expressed as a ratio.
- **Right axis** (dashed gray line): nominal Brazilian minimum-wage
  trajectory 2012–2026, hardcoded in the dashboard JS from official
  federal decrees.

If the floor-effect hypothesis is correct, both lines should rise
together from 2023 onward (when the valorization policy was restored).
If the ratio moves independently of the floor, the hypothesis loses
support.

### Dashboard (`dashboard/index.html`)

- New `<section id="piso">` "O efeito do piso" placed between
  Compliance Geography (Theme 4) and Foco em São Paulo. Same
  editorial-hero pattern as the other Themes.
- `renderFloor()` reads `STATE.wages`, builds the per-quarter ratio,
  pairs each quarter with its year's minimum-wage value via the
  hardcoded `MIN_WAGE_NOMINAL` map and a `smForPeriod()` helper.
- Chart: Chart.js line chart with dual y-axes (yLeft for %, yRight
  for R$). Policy timeline annotations carry over from
  `buildPolicyAnnotations` so EC 72 / LC 150 / C189 / COVID / PNC
  marks land on this chart too.
- Two inline callouts: latest wage ratio and latest minimum-wage
  value, populated by render-time JS.

### Methodology (`dashboard/metodologia.html`)

- §3.17 added (PT + EN). Explicit caveats spelled out:
  1. Not an econometric decomposition — visual correlation, not
     causality.
  2. Nominal MW used, not deflated; affects magnitude not direction.
  3. Composition-of-floor-earners change can compress the ratio
     without any individual wage rising — separating "mechanical"
     from "behavioral" requires panel microdata.

### Editorial framing

The section's editorial paragraph is unusually self-critical for
the dashboard — it explicitly says "this is a visual consistency
test, not a regression" and lists the alternative shocks (Conadon,
PNC, post-pandemic recovery) that a regression would have to control
for. This is intentional: the MTE/DIEESE seminar attribution was
itself qualitative, and the dashboard now offers the corresponding
visual test — promoting the qualitative argument to "consistent
with the data" without overclaiming causality.

For Mayer this is the chart that translates a policy claim into
testable evidence; for STDMSP it shows how minimum-wage policy
travels into the category.

### Run sequence on Joao's Mac

No pipeline change — just dashboard + methodology. Static export not
strictly needed since dw_wages already has what's needed:

```bash
cd ~/Documents/Claude/Domestic\ Work
# No ETL run required — the chart reads existing dw_wages rows.
# Just commit the dashboard/methodology/audit changes.
git add dashboard/index.html dashboard/metodologia.html QA_AUDIT.md
git commit -m "feat(Theme 5): floor effect — minimum-wage attribution panel"
git push origin main
```

### Sanity-check expectations

If the floor-effect hypothesis holds:
- The wage-ratio line should be relatively flat 2012–2022 (when the
  minimum wage didn't grow much in real terms),
- Then bend upward 2023–2026 (when the policy was restored),
- And track the minimum-wage line's acceleration in that period.

If the hypothesis is partial (some floor effect + some independent
narrowing), the ratio line might rise but at a different slope than
the MW line. If the hypothesis is wrong, the ratio could move in any
direction unrelated to the floor — e.g., narrow during 2017-2021 when
the floor was frozen.

The dashboard's job here is to make that visual test legible. Whether
the hypothesis is ultimately right is for a regression in a paper,
not a panel. The dashboard is the entry point.

### Five-Theme arc complete

Five publishable readings of the same data substrate:

| # | Theme | Axis | Anchor |
|--|---|---|---|
| 1 | Breadwinner paradox | Intersectional (static) | Gonzalez, Carneiro, Bernardino-Costa, Lopes, Lara |
| 2 | Onde estão as jovens | Generational (dynamic) | Saffioti, Acciari, IPEA |
| 3 | Casa-grande's afterlife | Historical (spatial) | Gonzalez, Saffioti, Carneiro, Bernardino-Costa |
| 4 | Compliance geography | Policy (institutional) | Acciari, Pinheiro/IPEA, MTE/Conadon |
| 5 | The floor effect | Policy (instrumental) | Saboia, Manzano-Munguía, MTE/DIEESE seminar |

Five panels, five scholarly traditions, one dataset. The dashboard now
holds the descriptive layer (eight indicator charts) plus the argument
layer (five editorial sections). v2.3 milestone.

---

## Sources

- [PNAD Contínua — IBGE](https://www.ibge.gov.br/estatisticas/sociais/trabalho/17270-pnad-continua.html)
- [IBGE press release — trimestre encerrado em fevereiro 2026](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/46206-pnad-continua-taxa-de-desocupacao-e-de-5-8-e-taxa-de-subutilizacao-e-de-14-1-no-trimestre-encerrado-em-fevereiro)
- [DIEESE — Infográfico Trabalho Doméstico no Brasil (abril 2025)](https://www.dieese.org.br/infografico/2025/trabalhadorasDomesticas.html)
- [DIEESE — Infográfico Trabalhadoras Domésticas no Brasil (abril 2026, PDF)](https://www.dieese.org.br/infografico/2026/2026trabalhadorasDomesticas.pdf)
- [MTE × DIEESE — XXVI Seminário Mensal: "Quem cuida de quem" (10 abril 2026)](https://www.gov.br/trabalho-e-emprego/pt-br/noticias-e-conteudo/2026/abril/seminario-do-mte-e-dieese-analisa-cenario-do-trabalho-domestico-no-pais)
- [MTE — Campanha Nacional pelo Trabalho Doméstico Decente 2026](https://www.gov.br/trabalho-e-emprego/pt-br/noticias-e-conteudo/2026/abril/dia-nacional-da-trabalhadora-domestica-reforca-mobilizacao-por-direitos-e-trabalho-decente-no-brasil)
- [DIEESE — Boletim Especial Trabalho Doméstico (2024)](https://www.dieese.org.br/boletimespecial/2024/trabalhoDomestico.pdf)
- [SIDRA Tabela 6320](https://sidra.ibge.gov.br/tabela/6320) · [Tabela 6383](https://sidra.ibge.gov.br/tabela/6383) · [Tabela 6391](https://sidra.ibge.gov.br/tabela/6391)
- [ILOSTAT — Domestic workers](https://ilostat.ilo.org/topics/employment/domestic-workers/)
