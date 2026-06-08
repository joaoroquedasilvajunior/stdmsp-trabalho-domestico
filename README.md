# Trabalho Doméstico — STDMSP Dashboard

Bilingual (PT + EN) data dashboard on Brazilian domestic workers, built for the
**Sindicato das Trabalhadoras Domésticas do Município de São Paulo (STDMSP)**
in collaboration with **Jean-François Mayer** (Concordia University, RITHAL).

**Live:** <https://stdmsp-trabalho-domestico.joaoroquer.workers.dev/>

## Stack

| Layer | Choice | Why |
|---|---|---|
| Storage | Supabase Postgres — schema `domestic_work` inside project `sceneqc` (`vqwhzzaqddqeurrspcdz`, `ca-central-1`) | Hosted, multi-user, REST-ready. Schema-isolated from `sceneqc`'s other tables. |
| ETL | Python (`requests`, `pandas`, `supabase-py`) | Hits SIDRA + ILOSTAT REST APIs, normalizes to long-form facts, idempotent upsert. |
| Frontend | Single self-contained HTML page (Chart.js + Tailwind via CDN) | Embeddable on the union's site, no backend beyond Supabase REST, mobile-first. |

## Data sources

| Code | Source | URL |
|---|---|---|
| PNADC-6320 | PNAD Contínua trimestral — Tabela 6320 | https://sidra.ibge.gov.br/tabela/6320 |
| PNADC-4093 | PNAD Contínua anual — Tabela 4093 | https://sidra.ibge.gov.br/tabela/4093 |
| CENSO-2022 | Censo Demográfico 2022 | https://censo2022.ibge.gov.br |
| ILOSTAT-DOM | ILOSTAT — Domestic workers by sex and status | https://ilostat.ilo.org |
| DIEESE-DOM | DIEESE — Boletins sobre trabalho doméstico | https://www.dieese.org.br |

## Repo layout

```
.
├── README.md                  ← you are here
├── QA_AUDIT.md                ← audit trail: number verification + change log
├── RESUMO_EXECUTIVO.md/.docx  ← one-page executive summary (PT) for stakeholders
├── schema/
│   ├── 001_init.sql           ← original DDL (April 2026)
│   └── 002_recovery.sql       ← consolidated DDL incl. fact_prev, static_fact, n_unweighted, dw_prev, dw_static_facts — used to rebuild after data loss
├── etl/
│   ├── manifest.yaml          ← which SIDRA tables to fetch with what params
│   ├── fetch_sidra.py         ← SIDRA aggregate fetcher → fact_workers / fact_wages / fact_hours
│   ├── pnadc_microdata.py     ← PNADC microdata pipeline → race/sex/UF/hours/prev aggregates
│   ├── fetch_ilostat.py       ← ILOSTAT fetcher → fact_intl
│   ├── build_uf_svg.py        ← one-off: builds dashboard/assets/brazil-uf.svg
│   ├── export_static.py       ← exports dw_* views → dashboard/data/*.json
│   ├── refresh.sh             ← post-ETL helper: runs export_static + stages data
│   ├── repopulate_from_json.py ← rebuilds Supabase from committed JSON after schema loss
│   ├── .env.example           ← copy to .env, fill Supabase service role key
│   └── requirements.txt
└── dashboard/
    ├── index.html             ← bilingual PT+EN dashboard, embeddable
    ├── metodologia.html       ← methodology page (PT + EN)
    ├── calculadora.html       ← "Como você se compara?" calculator
    ├── assets/                ← chita SVG bands, brazil-uf.svg map geometry
    └── data/                  ← static JSON exports the dashboard reads at runtime
```

## Setup

```bash
cd etl
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
python fetch_sidra.py
python fetch_ilostat.py
```

## Network requirement

The ETL hits `apisidra.ibge.gov.br`, `servicodados.ibge.gov.br`, and
`rplumber.ilo.org`. If running inside the Cowork sandbox, those domains must be
allowlisted at **Settings → Capabilities** before the ETL can run. From a normal
dev machine no allowlisting is needed.

## Editorial framing

The end audience is dual:

1. **Union members** — mostly Black women, plain-language Portuguese, mobile-first,
   large readable charts, methodology in tooltips not in the main flow.
2. **Researchers / policy** — English labels available, source links beside every
   number, methodology notes accessible.

Time scope brackets the key regulation moments: **EC 72/2013**, **LC 150/2015**,
the **2020 STF ruling**, and the **COVID-19 shock**.

## Deployment

The dashboard is a single self-contained HTML file (`dashboard/index.html`) that
talks to Supabase via the public anon key + RLS. It deploys as a static site
with no build step.

**Cloudflare Pages config** (set once in the dashboard when connecting the GitHub repo):

| Field | Value |
|---|---|
| Framework preset | None |
| Build command | _(leave empty)_ |
| Build output directory | `dashboard` |
| Root directory | _(leave empty / project root)_ |

Every push to `main` triggers an auto-deploy. Preview deployments are
generated for every other branch — useful for trying out new charts before
they go live.

## Quarterly refresh — DIEESE bulletins

DIEESE publishes its domestic-work bulletins twice a year: an
**Infográfico** around **April 28** (Dia Nacional das Trabalhadoras
Domésticas) and a **Boletim Especial** around **November 20** (Dia da
Consciência Negra). The refresh ritual:

1. **Pull the new bulletin** from <https://www.dieese.org.br>. Note the
   updated headline figures we mirror in `static_fact`:
   - `pct_women` — % de mulheres entre trabalhadoras(es) domésticas(os)
   - `pct_negras` — % negras (pretas + pardas) entre trabalhadoras domésticas
   - `wage_ratio_black_to_nonblack` — razão salarial negras ÷ não-negras (em %)
2. **Update the matching rows** in Supabase
   (schema `domestic_work`, table `static_fact`). The actual columns are
   `value_num` (numeric), `source_short`, `source_url`, `source_date` (date),
   `note_pt`, `note_en` — keyed by `fact_code`:

   ```sql
   update domestic_work.static_fact
      set value_num    = <new_value>,
          source_short = '<DIEESE — Boletim/Infográfico ...>',
          source_url   = '<https://www.dieese.org.br/...>',
          source_date  = '<YYYY-MM-DD>',
          note_pt      = '<atualização da nota se necessário>',
          note_en      = '<update the EN note if needed>'
    where fact_code = 'pct_women';        -- repeat for pct_negras, wage_ratio_black_to_nonblack
   ```

   You can run this from the Supabase SQL Editor or via `psql`. Verify
   afterwards:

   ```sql
   select fact_code, value_num, source_short, source_date
     from domestic_work.static_fact
    order by fact_code;
   ```
3. **Re-run the ETL** if a new trimestre has dropped since the last run:

   ```bash
   cd etl && source .venv/bin/activate
   python fetch_sidra.py
   python pnadc_microdata.py 0X2026     # the new quarter (single-quarter mode)
   python fetch_ilostat.py              # if ILOSTAT has new annual data
   ```
4. **Append a new entry to `QA_AUDIT.md` → Refresh log** documenting what
   you checked, what changed, and the next check date. Don't rewrite past
   entries.
5. **Regenerate the static data + deploy** — see the next section.

## Data refresh — static export (REQUIRED after any ETL run)

The dashboard is a **static site**: it reads `dashboard/data/*.json`, committed
to the repo and served by the same Cloudflare deploy as `index.html`. It does
**not** hold a live Supabase connection. (This was changed on 2026-05-20 after
a free-tier Supabase project pause took the live site down.)

Consequence: **after any ETL run, the static JSON must be regenerated** or the
dashboard silently serves stale data. Use the helper script:

```bash
./etl/refresh.sh
```

It runs `etl/export_static.py` (pages every `dw_*` view into
`dashboard/data/<view>.json` + a `manifest.json` timestamp), stages
`dashboard/data/`, and prints the commit + push commands. Then:

```bash
git commit -m "data: refresh static export 2026qN"
git push origin main
```

Cloudflare Pages auto-deploys on push. The dashboard's "data updated on" line
reflects `manifest.generated_at`, so a skipped export shows up as a stale date
rather than silently-wrong numbers.

**Supabase can pause freely between refreshes** — it is only the ETL target
and source of truth now, not a runtime dependency for the public site. Resume
the `sceneqc` project only when you need to run the ETL or `export_static.py`.

## Schema recovery — if Supabase data is lost

Free-tier Supabase projects can lose all data if the pause window is
exceeded (this happened on 2026-06-08: the `domestic_work` schema was
purged, the `public` schema emptied). The static-export migration means
the public dashboard keeps working off `dashboard/data/*.json`, but the
queryable backend has to be rebuilt before the next ETL run.

Rebuild ritual:

```bash
# 1. Wake the Supabase project (it may need a restore_project MCP call).

# 2. Apply the schema DDL — recreates every table, view, RLS policy.
#    Idempotent; safe to re-run.
psql "$SUPABASE_DB_URL" -f schema/002_recovery.sql
# ...or via the Supabase MCP apply_migration tool with the file contents.

# 3. Repopulate from the committed JSON exports.
cd etl && source .venv/bin/activate
python repopulate_from_json.py

# 4. Verify counts match the manifest.
python export_static.py --check
```

If step 4 reports the same row counts as `dashboard/data/manifest.json`,
the rebuild is complete and `etl/refresh.sh` is operational again. The
public dashboard is unaffected throughout — it reads JSON, not Supabase.

`schema/002_recovery.sql` and `repopulate_from_json.py` are both
idempotent. Re-running them after a successful rebuild is a no-op.

## Local development

The dashboard reads from Supabase via fetch(). Open it through a local web
server, **not** `file://` — browsers block CORS requests from `file://`:

```bash
cd dashboard
python -m http.server 8000
# then open http://localhost:8000
```

For ETL work, the Python venv at `etl/.venv` is the source of truth. Always
activate it before running fetch scripts (look for the `(.venv)` prefix in
your prompt as the canary):

```bash
cd etl
source .venv/bin/activate
```
