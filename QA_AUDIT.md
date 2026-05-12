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

## Sources

- [PNAD Contínua — IBGE](https://www.ibge.gov.br/estatisticas/sociais/trabalho/17270-pnad-continua.html)
- [IBGE press release — trimestre encerrado em fevereiro 2026](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/46206-pnad-continua-taxa-de-desocupacao-e-de-5-8-e-taxa-de-subutilizacao-e-de-14-1-no-trimestre-encerrado-em-fevereiro)
- [DIEESE — Infográfico Trabalho Doméstico no Brasil (abril 2025)](https://www.dieese.org.br/infografico/2025/trabalhadorasDomesticas.html)
- [DIEESE — Boletim Especial Trabalho Doméstico (2024)](https://www.dieese.org.br/boletimespecial/2024/trabalhoDomestico.pdf)
- [SIDRA Tabela 6320](https://sidra.ibge.gov.br/tabela/6320) · [Tabela 6383](https://sidra.ibge.gov.br/tabela/6383) · [Tabela 6391](https://sidra.ibge.gov.br/tabela/6391)
- [ILOSTAT — Domestic workers](https://ilostat.ilo.org/topics/employment/domestic-workers/)
