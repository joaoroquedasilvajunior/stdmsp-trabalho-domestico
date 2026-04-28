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
├── schema/
│   └── 001_init.sql           ← version-controlled DDL (already applied to Supabase)
├── etl/
│   ├── manifest.yaml          ← which SIDRA tables to fetch with what params
│   ├── fetch_sidra.py         ← PNADC fetcher → fact_workers / fact_wages / fact_hours
│   ├── fetch_ilostat.py       ← ILOSTAT fetcher → fact_intl
│   ├── .env.example           ← copy to .env, fill Supabase service role key
│   └── requirements.txt
└── dashboard/
    └── index.html             ← bilingual PT+EN dashboard, embeddable
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

DIEESE publishes its domestic-work bulletins twice a year, in **April** and
**November**. The refresh ritual:

1. **Pull the new bulletin** from <https://www.dieese.org.br>. Note the new
   national average wage and the % of workers with carteira assinada.
2. **Update the two `static_fact` rows** in Supabase
   (schema `domestic_work`, table `static_fact`):

   ```sql
   UPDATE domestic_work.static_fact
   SET value = <new_value>, source_period = '<YYYY-MM>'
   WHERE metric_code = 'dieese_avg_wage';

   UPDATE domestic_work.static_fact
   SET value = <new_value>, source_period = '<YYYY-MM>'
   WHERE metric_code = 'dieese_pct_formal';
   ```
3. **Re-run the PNADC ETL** if a new trimestre móvel has dropped since the
   last run:

   ```bash
   cd etl && source .venv/bin/activate
   python fetch_sidra.py
   ```
4. **Commit and push** — Cloudflare Pages auto-deploys. The DIEESE values
   are read live from Supabase, so no dashboard code change is needed unless
   the schema changed.

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
