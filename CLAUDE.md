# CLAUDE.md — Domestic Work / STDMSP project

Instructions and context for any Claude session working in this repository.
Read this first. It captures the architecture, the hard-won constraints, and the
conventions so you don't re-learn them or repeat past mistakes.

---

## 1. What this project is

A bilingual (PT/EN) research + knowledge-mobilization project about **domestic
workers in Brazil**, in partnership with:

- **STDMSP** — Sindicato das Trabalhadoras Domésticas do Município de São Paulo
  (São Paulo domestic workers' union). The end audience for the union-facing
  products; copy addressed to them uses the union's own first-person voice.
- **Jean-François Mayer** — Concordia University, comparative politics; drives
  the academic side (a book chapter). RITHAL co-founder.

Deliverables built so far:
- An interactive **bilingual dashboard** (PNADC/DIEESE/IPEA data, 2012–latest).
- A **"Como você se compara?" calculator** — a self-assessment tool for workers.
- Analyses of two **STDMSP field surveys** (A and B) for Mayer's chapter.
- A **semantic explorer + resistance-repertoire analysis** of Survey B testimony.

---

## 2. CRITICAL constraints & gotchas (read before doing anything)

1. **Git from the Mac terminal, NOT the sandbox.** The Cowork bash sandbox
   cannot manipulate `.git/` on the mounted `Domestic Work` folder. NEVER run
   git write operations in the sandbox. Instead, hand the user exact git
   commands (add/commit/push) to paste into their Mac terminal. Read-only git
   inspection (`git log`, `git ls-files`) does work in the sandbox.

2. **Supabase project is SHARED.** Project `vqwhzzaqddqeurrspcdz` (aka `sceneqc`)
   hosts BOTH this project's `domestic_work` schema AND SceneQuebec's `public`
   schema. Always filter by schema `domestic_work` before any action. When
   reading Advisor/security findings, separate the two schemas.

3. **`period_code` has TWO meanings — do not confuse them.**
   - `source_table = PNADC-6391` (SIDRA): `YYYYMM` where MM is the **final month
     of the rolling quarter**. E.g. `202604` = quarter ending April 2026.
   - `source_table = PNADC-MICRODATA`: `YYYY0Q` where Q is the **calendar
     quarter**. E.g. `202601` = Q1 2026.
   They collide for MM/Q 01–04, so you MUST use `source_table` to disambiguate.
   A past "fix" wrongly displayed "4T 2026" for April data — reverted. See
   `dashboard/calculadora.html` → `periodLabel()`.

4. **Sensitive data — never commit, never host.**
   - Raw survey XLSX (`Condições de Trabalho...xlsx`, `Final version May_2023.xlsx`)
     contain **CPF** and are gitignored (`*.xlsx`). Never commit them.
   - CPF was dropped from ALL harmonized outputs. Do not reintroduce it.
   - Survey B testimony includes abuse accounts; the semantic explorer
     (`chapter/survey_b_explorer/`) is gitignored and must stay local — never
     host it or commit it. Passages are labelled only by anon ID (B-001…).
   - The harmonized XLSX still carry `cep` (postal code) in git history — a
     known privacy item; consider truncating to 5 digits if revisited.

5. **Do NOT reference Eliete as a project participant.** Eliete Edwiges Barbosa
   is the editor of the book Mayer's chapter goes into — not a research
   collaborator. The chapter/analytical work is Mayer's.

6. **Storage = Supabase (hosted Postgres), not DuckDB.** A deliberate user
   choice; respect it for stack decisions.

7. **STDMSP-facing copy uses the union voice** — first-person plural ("nós",
   "somos"), direct attribution ("está sendo descumprida"), not
   researcher-neutral hedging. Academic copy (Mayer) keeps caveats and CIs.

---

## 3. Architecture / stack

- **Data store:** Supabase Postgres, schema `domestic_work` (dims + fact_* tables),
  exposed via `public.dw_*` views with `security_invoker = true` + RLS.
- **Dashboard:** static HTML/JS + Tailwind (CDN) + Supabase JS client. Hosted on
  **Cloudflare Workers** at `stdmsp-trabalho-domestico.joaoroquer.workers.dev`.
  GitHub repo `joaoroquedasilvajunior/stdmsp-trabalho-domestico` auto-deploys on push.
- **Static-export resilience:** the dashboard also reads baked JSONs in
  `dashboard/data/*.json` so it survives Supabase pausing. Regenerate with
  `etl/export_static.py`. These JSONs ARE committed (Cloudflare serves them) —
  which is why `.git` bloats over time (see §12).
- **Embed:** `chapter/embed_for_mayer_weebly.html` — iframe block for Mayer's
  Weebly site (100% column width, 85vh, internal scroll; no 100vw breakout).

---

## 4. Data sources

- **PNADC (IBGE)** — via SIDRA API and microdata. Key SIDRA tables used:
  6320 (workers), 6383 (UF distribution + mensalista/diarista), 6391 (wages),
  4093/6471 (conta-própria × CNPJ for the MEI proxy), PNADC-Anual V4097 (union
  membership). Microdata pipeline: `etl/pnadc_microdata.py`.
- **DIEESE** — "Trabalhadoras Domésticas no Brasil" infográfico (latest abr/2026,
  base 4T 2025). Feeds `static_fact` headline figures (%, race wage ratio).
- **ILOSTAT** — international comparator (esp. Mexico). `etl/fetch_ilostat.py`.
- **STDMSP surveys A and B** — see §8.
- **Release calendar:** PNADC-C 2T 2026 → 14/08/2026; platform-work module 2025
  → 04/09/2026 (both have scheduled-task reminders, see §11).

---

## 5. Supabase schema (`domestic_work`)

Dims: `dim_time, dim_geo, dim_sex, dim_race, dim_formality, dim_contract,
dim_education, dim_family, dim_housing, dim_age_group, dim_age_band`.
Facts: `fact_workers, fact_wages, fact_hours, fact_prev, fact_contract,
fact_education, fact_family, fact_housing, fact_age, fact_autonomous, fact_intl`.
Other: `data_source, static_fact`.
Public views: `dw_workers, dw_wages, dw_hours, dw_prev, dw_intl, dw_sources,
dw_static_facts` (+ dw_contract/education/family/housing/autonomous/age).

Migrations in `schema/`:
- `001_init.sql` — base schema + views.
- `002_recovery.sql` — rebuild + static_fact table + extra facts.
- `003_mei_proxy.sql`, `004_fact_autonomous.sql` — MEI/autonomous proxy.
- `005_fix_security.sql` — flip legacy views to security_invoker + RLS on fact_autonomous.
- `006_calculator_facts.sql` — static_facts for the calculator (DIEESE race wages,
  CC-SP floor). NOTE: live `static_fact` table has NO `updated_at` column and
  `fact_code` is unique (ON CONFLICT target).

Apply migrations via the Supabase MCP (`execute_sql` / `apply_migration`).

---

## 6. ETL scripts (`etl/`)

Grouped by purpose (all Python; run locally with a venv — `.venv` is gitignored
and disposable, recreate with pip; `etl/raw` microdata is gitignored and
re-downloadable):

- **SIDRA/probe:** `fetch_sidra.py`, `probe_metadata.py`, `inspect_row.py`,
  `probe_wage_contract.py`, `probe_general_pop_race.py`, `probe_sidra_4093.py`,
  `probe_mei_vars.py`, `probe_union.py`, `probe_union_annual.py`,
  `probe_survey_b_union.py`.
- **Microdata:** `pnadc_microdata.py` (main historical backfill),
  `pnadc_annual_housing.py`, `union_annual_timeseries.py` (V4097 + UF/SP cuts).
- **International:** `fetch_ilostat.py`.
- **Export / maps:** `export_static.py` (baked JSONs), `build_uf_svg.py`,
  `repopulate_from_json.py`, `build_dw_union_json.py`.
- **Surveys — harmonization:** `harmonize_surveys.py` (A+B → anon IDs A-001..,
  B-001.. by row order; drops CPF), `consolidate_for_looker.py`.
- **Survey A analysis:** `analyze_survey_a.py` (main, 12+ questions),
  `analyze_q13_by_race.py`, `analyze_q13_by_age.py`, `analyze_q13_by_tenure.py`,
  `analyze_q13_gap_explanation.py`, `analyze_q14_by_race.py`,
  `categorize_q18.py`, `audit_q18_categorization.py`, `generate_q18_chart.py`,
  `generate_q18_chart_mayer.py` (uses Mayer's manual coding).
- **Union charts:** `generate_union_chart.py`, `generate_sp_union_chart.py`,
  `generate_chapter_chart.py`, `build_survey_charts.py`.
- **Survey B qualitative (sensitive, outputs gitignored):**
  `build_survey_b_explorer.py` (offline BM25 + PT stemmer explorer),
  `embed_survey_b.py` (neural embeddings + resistance repertoire scoring — run
  locally with sentence-transformers), `analyze_resistance_by_demographics.py`
  (resistance × demographics), `chart_filiacao_voz.py` (the headline chart).

---

## 7. Dashboard (`dashboard/`)

- `index.html` — main dashboard (mobile-first: bottom tab nav, sticky header,
  sparklines, collapsible leads, themes pill-nav). Reads Supabase live, falls
  back to `data/*.json`.
- `calculadora.html` — the "Como você se compara?" calculator (bilingual,
  privacy-first, print + WhatsApp). Compares wage vs national/UF mean, minimum
  wage, and **CC-SP floor R$ 1.874,36** (piso estadual jun/2026 > CCT R$ 1.804;
  the higher prevails). Rights checklist (LC 150/2015) turns the piso item to "!"
  when wage < floor. `reaisCents()` shows cents for legal values.
- `embed.html`, `mockup.html`, `data/*.json`, `assets/` (chita SVG bands).

Conventions: CSS vars, accent red `#b91c1c`, slate `#475569`; pt-BR number
formatting (vírgula decimal); everything bilingual via `data-i18n`.

---

## 8. The two STDMSP surveys

- **Survey A** — `Condições de Trabalho...(Responses).xlsx`, 2024, **n=242**,
  Google Forms self-administered. Race: afro (pardas+pretas) n=140, brancas n=93.
  Short closed + short open-text (Q11A/Q12A/Q13A/Q17A/Q18). Anon IDs A-001..A-242.
- **Survey B** — `Final version May_2023.xlsx`, 2021–23, **n=241**, deep
  qualitative (life histories, employer relations, abuse, dreams; ~38 open-text
  fields, ~5,000 passages). Anon IDs B-001..B-241 by row order. Q32 = union
  membership (Sim 72 / Não 159).
- Both are convenience samples in the STDMSP orbit — self-selected, NOT
  population-representative. Keep them distinct from PNADC. No respondent-level
  link between A and B.

Chart style for the chapter: serif font, `COL_AFRO=#b91c1c`, `COL_BRANCA=#475569`,
Wilson 95% CIs, pt-BR formatting, honest significance reporting.

---

## 9. Survey B resistance analysis (the standout finding)

Repertoire of individual resistance (Hirschman + extensions): **saída/exit,
voz/voice, evitação/avoidance, lealdade/loyalty, espiritualidade/faith,
solidariedade/kin**. Passages scored by semantic similarity to seed-phrase
centroids (`embed_survey_b.py`). Cross-tab vs demographics with within-respondent
z-centering + Mann-Whitney (`analyze_resistance_by_demographics.py`).

**Headline finding (robust):** union membership substitutes VOICE for FAITH.
Filiadas: voice dominant 31% vs 12%; spirituality 11% vs 26%. Voice intensity
p=0.002, spirituality p=0.037. Validated by reading passages — union voice is
rights-based and learned ("aprendi neste sindicato a exigir meus direitos");
non-union voice is individual, unstable, bleeding into exit/supplication.
Chart: `chapter/survey_b_resistance/filiacao_voz_substitution.png`; write-up:
`achado_filiacao_voz.docx`. Caveat: association not causation; n small; exploratory.

---

## 10. Other key findings (for continuity)

- Union filiation: **SP is BELOW the national average** (SP ~1.4% vs BR ~2.86%);
  Nordeste leads (PI 12%); STDMSP entorno (31%) is ~19× the SP baseline — the
  union is an *island* of organization, not typical of SP.
- Survey A Q13 (CC brought benefit?): afro 40% vs brancas 31% — Δ+9pp but
  **NOT statistically significant** (Fisher p=0.24, CIs overlap). Report as
  suggestive. Strong, significant patterns instead: by AGE (30-39 dip, 10% vs
  ~42%, p=0.0003) and by TENURE (step-change at 10 years, 26%→50%, p=0.0003).
- Q14 × race: recognition ≠ receipt — Black and white workers receive CC
  benefits at similar rates, but ~32% of Q14 respondents said in Q13 the CC
  brought them no benefit → a recognition gap, not an access gap.
- Q18 (union's most important function): use **Mayer's manual categorization**
  (`q18_categorized.xlsx`, n=215) as ground truth, not the keyword heuristic.
  Brancas 50% "residual/vague" vs afro 32%; "cuidado/proteção" almost exclusively
  afro (12 vs 1). Keyword lesson: use STEMS (cuid, proteg) not full words.

---

## 11. Scheduled tasks

Two one-time reminders exist (managed in the app's "Scheduled" section):
- `pnadc-2t-2026-refresh` — 15/08/2026 09:00 −03:00. Refresh dashboard with
  PNADC-C 2T 2026 (SIDRA + microdata + DIEESE static_facts; hand git to user).
- `pnadc-plataformas-2025-check` — 05/09/2026 09:00 −03:00. Probe the PNADC
  platform-work 2025 module for a domestic × platform cut (probe-first; likely
  needs microdata cross of platform vars × occupation code V4010/CBO; may be
  hard to isolate). Connects to Survey B's app-precarization signal.

---

## 12. Deploy & repo hygiene

- **Deploy:** commit + push to `main` from the Mac terminal → Cloudflare Worker
  auto-redeploys. Verify the live URL after data changes.
- **`.gitignore`** covers: `*.xlsx` + the two named raw surveys, `etl/raw`,
  `etl/.venv`, `chapter/survey_b_explorer/` (sensitive). Keep it that way.
- **Git bloat:** the committed `dashboard/data/*.json` (10MB+ each) re-committed
  every refresh inflates `.git`. Cleaned once via `git filter-repo` (stripped
  their history, kept current versions) — repo went from 4.6G → ~58M. It will
  grow again ~10-40MB/refresh; re-run the cleanup annually if needed.

---

## 13. Open / pending work

- #33 ENIGH heavy path (computed Mexico parallel) — decision pending.
- #37 Story mode: pilot review with STDMSP.
- #54 Fix PNC + Conadon annotation visibility (code_movel anchor + SIDRA refresh).
- #68 Extend fact_contract to UF granularity.
- #70 Extend fact_wages with contract dimension (full time-series).
- UF-specific wage comparison in the calculator is **dormant code** — `dw_wages`
  only has `geo_level='country'` today; it activates for free once #68/#70 land.

---

*Working conventions: respond concisely; ask before large multi-step work;
validate numbers against published IBGE/DIEESE before shipping; probe-first
before building pipelines; qualitative findings are machine-assisted but
human-validated by reading.*
