# MEI-proxy pipeline addition — scope

**Question:** are domestic workers shifting toward MEI (Microempreendedor Individual) status, and how do we measure it?

**TL;DR:** Build the answer from three complementary feeds, sequenced. The PNADC side is the analytical core; SIDRA gives the IBGE-blessed headline; the Receita Federal MEI registry triangulates from the administrative side. All three land in the existing `domestic_work` schema, behind two new fact tables and two new views. ~4–5 days of work end-to-end; the PNADC microdata extension is the only piece that *requires* a quarter re-pull.

**Why this can't ride on the existing `fact_workers` filter.** The current pipeline filters microdata to `VD4009 in {"03","04"}` (trabalhador doméstico, com/sem carteira). IBGE's V4019 — the CNPJ question that proxies MEI — is **only asked of conta-própria and empregadores**, i.e. people whose VD4009 = `"09"`. So the population we need lives *outside* the existing filter. A diarista who legally could be (or actually is) an MEI is still classified by IBGE as VD4009 = `"04"` *because she works in a residence*, and V4019 is blank on her record. The MEI question therefore has to be operationalised on the *conta-própria population whose CBO-Domiciliar is domestic-adjacent*, with the trabalhador doméstico stock from `fact_workers` as the comparison denominator.

---

## 1. Required PNADC variables

Append to `NEEDED_VARS` in `pnadc_microdata.py`:

| Var | Meaning | Used for |
|---|---|---|
| `V4010` | Ocupação principal — CBO-Domiciliar (4-digit) | identify domestic-adjacent occupations among conta-própria |
| `V4019` | Possuía CNPJ neste trabalho? (1=Sim, 2=Não) | the MEI proxy itself |
| `V4012` | Posição raw (before VD4009 derivation) | sanity check that we're looking at conta-própria, not employer |

`V1028`, `V2007`, `V2010`, `V4032`, `VD4009`, `VD4019`, `UF` are already extracted — reuse them.

**CBO-Domiciliar groupings to compute.** The PNADC CBO-Domiciliar is a simplified version of CBO 2002, not the full 6-digit code. The four cuts that matter:

| `cbo_group` | CBO-Domiciliar | What's there |
|---|---|---|
| `domestic_5121` | 5121 | Trabalhadores nos serviços domésticos em geral — diaristas/mensalistas working in residences |
| `caregiver_5162` | 5162 | Cuidadores (crianças, idosos, pessoas com deficiência) — the cleanest MEI-eligible bucket |
| `cleaning_5141` | 5141, 5143 | Limpeza/conservação em prédios — overlaps with the MEI CNAE 8121-4/00 |
| `other` | everything else | catch-all for sample-size sanity |

**Note on CBO drift.** IBGE phased in the CBO 2022 update around 2023; the legacy 4-digit groupings above are stable on the PNADC-Domiciliar side, but the parser should log the distribution of `V4010` codes the first time the backfill hits a 2023+ quarter — flag the maintainer if anything new appears.

---

## 2. New fact tables

Append to `schema/002_recovery.sql` (or open `schema/003_mei_proxy.sql`):

```sql
-- Conta-própria + CNPJ + previdência cross-tab from PNADC microdata.
-- One row per (period × geo × sex × race × cbo_group × autonomy_code).
create table if not exists domestic_work.fact_autonomous (
  fact_id            bigserial primary key,
  time_id            int  not null references domestic_work.dim_time(time_id),
  geo_id             int  not null references domestic_work.dim_geo(geo_id),
  sex_id             int  not null references domestic_work.dim_sex(sex_id),
  race_id            int  not null references domestic_work.dim_race(race_id),
  cbo_group          text not null check (cbo_group in
                       ('domestic_5121','caregiver_5162','cleaning_5141','other')),
  autonomy_code      text not null check (autonomy_code in
                       ('conta_propria_cnpj','conta_propria_sem_cnpj',
                        'empregador_cnpj','empregador_sem_cnpj')),
  workers_thousands  numeric(12,2),
  pct_with_prev      numeric(5,2),   -- V4032 contribution rate within the cell
  mean_wage_brl      numeric(12,2),  -- optional, when n_unweighted >= 30
  n_unweighted       int not null,
  source_table       text not null,  -- 'PNADC-MICRODATA'
  loaded_at          timestamptz not null default now(),
  unique (time_id, geo_id, sex_id, race_id, cbo_group, autonomy_code, source_table)
);
create index if not exists ix_fact_autonomous_time on domestic_work.fact_autonomous (time_id);
create index if not exists ix_fact_autonomous_cbo  on domestic_work.fact_autonomous (cbo_group);

-- Administrative MEI count by CNAE from the Portal do Empreendedor / Receita
-- Federal feed. One row per (period × geo × cnae).
create table if not exists domestic_work.fact_mei_registry (
  fact_id        bigserial primary key,
  time_id        int  not null references domestic_work.dim_time(time_id),
  geo_id         int  not null references domestic_work.dim_geo(geo_id),
  cnae_code      text not null,            -- e.g., '8800-6/00'
  cnae_label_pt  text not null,
  cnae_label_en  text not null,
  active_mei     int  not null,            -- count of active MEIs in the cell
  source         text not null,            -- 'PORTAL_EMPREENDEDOR' or 'RECEITA_DADOS_ABERTOS'
  loaded_at      timestamptz not null default now(),
  unique (time_id, geo_id, cnae_code, source)
);
```

Two corresponding `security_invoker = true` views in `public`:

```sql
create or replace view public.dw_autonomous as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code,
       s.code as sex_code, r.code as race_code,
       fa.cbo_group, fa.autonomy_code,
       fa.workers_thousands, fa.pct_with_prev, fa.mean_wage_brl,
       fa.n_unweighted, fa.source_table
from domestic_work.fact_autonomous fa
join domestic_work.dim_time t on t.time_id = fa.time_id
join domestic_work.dim_geo  g on g.geo_id  = fa.geo_id
join domestic_work.dim_sex  s on s.sex_id  = fa.sex_id
join domestic_work.dim_race r on r.race_id = fa.race_id;

create or replace view public.dw_mei_registry as
select t.period_code, t.year, t.quarter,
       g.level as geo_level, g.code as geo_code,
       fm.cnae_code, fm.cnae_label_pt, fm.cnae_label_en,
       fm.active_mei, fm.source
from domestic_work.fact_mei_registry fm
join domestic_work.dim_time t on t.time_id = fm.time_id
join domestic_work.dim_geo  g on g.geo_id  = fm.geo_id;

alter view public.dw_autonomous   set (security_invoker = true);
alter view public.dw_mei_registry set (security_invoker = true);
grant select on public.dw_autonomous, public.dw_mei_registry to anon, authenticated;
```

---

## 3. Code changes in `pnadc_microdata.py`

Add a new builder, mirroring `build_prev_rows()`:

```python
# CBO-Domiciliar groups (4-digit codes from V4010)
CBO_DOMESTIC_ADJACENT = {
    "5121": "domestic_5121",
    "5162": "caregiver_5162",
    "5141": "cleaning_5141",
    "5143": "cleaning_5141",  # collapse into the 5141 bucket
}

def build_autonomous_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Conta-própria / empregador × CNPJ cross-tab, restricted to
    domestic-adjacent CBO-Domiciliar codes. The MEI-proxy panel."""
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    # Filter: conta-própria (VD4009='09') OR empregador (VD4009='08' if present)
    AUTONOMY_CODES = {"09": "conta_propria", "08": "empregador"}
    auto = df[df["VD4009"].isin(AUTONOMY_CODES.keys())].copy()
    auto["position_root"] = auto["VD4009"].map(AUTONOMY_CODES)
    auto["has_cnpj"] = auto["V4019"].astype(str).str.strip() == "1"
    auto["cnpj_known"] = auto["V4019"].astype(str).str.strip().isin(["1", "2"])
    auto = auto[auto["cnpj_known"]]
    auto["autonomy_code"] = (
        auto["position_root"] + auto["has_cnpj"].map({True: "_cnpj", False: "_sem_cnpj"})
    )
    auto["cbo_group"] = auto["V4010"].astype(str).str.strip().str[:4].map(
        lambda c: CBO_DOMESTIC_ADJACENT.get(c, "other")
    )
    auto["race_code"] = auto["V2010"].map(RACE_MAP)
    auto["sex_code"]  = auto["V2007"].map(SEX_MAP)
    auto = auto[auto["race_code"].notna() & auto["sex_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    def _agg(group):
        w = group["weight"]
        if w.sum() == 0:
            return None
        prev_known = group["V4032"].astype(str).str.strip().isin(["1", "2"])
        prev_g = group[prev_known]
        wage_g = group[pd.to_numeric(group["VD4019"], errors="coerce") > 0]
        return {
            "workers_thousands": round(float(w.sum()) / 1000, 2),
            "pct_with_prev": (
                round(100 * float((
                    (prev_g["V4032"].astype(str).str.strip() == "1") * prev_g["weight"]
                ).sum() / prev_g["weight"].sum()), 2)
                if prev_g["weight"].sum() > 0 else None
            ),
            "mean_wage_brl": (
                round(float((
                    pd.to_numeric(wage_g["VD4019"], errors="coerce") * wage_g["weight"]
                ).sum() / wage_g["weight"].sum() / 100), 2)   # implicit 2 decimals in VD4019
                if len(wage_g) >= 30 else None
            ),
            "n_unweighted": int(len(group)),
        }

    # BR × sex='T' × race × cbo_group × autonomy_code
    for (race, cbo, aut), g in auto.groupby(["race_code", "cbo_group", "autonomy_code"]):
        a = _agg(g)
        if a:
            rows.append({
                "_period_code": db_period,
                "_geo_code": "BR", "_geo_level": "country",
                "_sex": "T", "_race": race,
                "cbo_group": cbo, "autonomy_code": aut,
                **a,
            })

    # BR × preta_parda aggregate × cbo_group × autonomy_code
    is_negra = auto["race_code"].isin(["preta", "parda"])
    for (cbo, aut), g in auto[is_negra].groupby(["cbo_group", "autonomy_code"]):
        a = _agg(g)
        if a:
            rows.append({
                "_period_code": db_period,
                "_geo_code": "BR", "_geo_level": "country",
                "_sex": "T", "_race": "preta_parda",
                "cbo_group": cbo, "autonomy_code": aut,
                **a,
            })

    # SP-level cut (geo='35'), race='total', only when n_unweighted >= 30 inside _agg
    sp = auto[auto["UF"].astype(str).str.zfill(2) == "35"]
    for (cbo, aut), g in sp.groupby(["cbo_group", "autonomy_code"]):
        a = _agg(g)
        if a and a["n_unweighted"] >= 30:
            rows.append({
                "_period_code": db_period,
                "_geo_code": "35", "_geo_level": "uf",
                "_sex": "T", "_race": "total",
                "cbo_group": cbo, "autonomy_code": aut,
                **a,
            })

    return rows
```

Hook it up in the `main()` flow next to `build_prev_rows()` and add an upsert to `domestic_work.fact_autonomous`. Mirror the existing pattern for resolving `time_id`/`geo_id`/`sex_id`/`race_id` from dim tables.

---

## 4. Expected magnitudes (sanity gates)

Before approving the backfill, the single-quarter run should land in these ranges:

| Cell | Expected n_unweighted | Expected weighted |
|---|---|---|
| BR · conta_propria · CBO 5121 (any CNPJ) | ~150–300 / quarter | ~250–500 k workers |
| BR · conta_propria · CBO 5162 (any CNPJ) | ~250–500 / quarter | ~400–700 k workers |
| BR · conta_propria_cnpj · CBO 5162 | ~50–120 / quarter | ~80–200 k workers |
| BR · conta_propria · CBO 5141 (cleaning) | ~150–300 / quarter | ~300–500 k workers |
| **% with CNPJ inside CBO 5162** | — | **~15–25 % (the MEI-zation rate)** |
| SP · same cells | ~25–40 % of BR sample | matches SP share of national stock |

If `% with CNPJ inside CBO 5162` lands outside ~10–35 %, suspect a V4019 byte-position drift and check the dictionary parser logs.

For race × CBO × CNPJ at the quarterly level, **n_unweighted < 30** is common — emit the row but flag it null for downstream consumers, or aggregate to 4-quarter pools. The `_agg()` helper above already gates `mean_wage_brl` on n≥30; do the same on the dashboard side for `pct_with_prev`.

---

## 5. SIDRA quick-win (one day, before the microdata work)

The headline "% of conta-própria with CNPJ" exists as a published time series in **SIDRA Tabela 4093** (PNADC anual — características da pessoa ocupada, by `posição na ocupação e categoria do emprego no trabalho principal`). Extend `etl/fetch_sidra.py` with a new manifest entry pulling that variable at BR + SP, no race cut. Lands in `fact_workers` with `formality_code = "conta_propria_cnpj"` / `"conta_propria_sem_cnpj"` after a one-line addition to `dim_formality`.

Use this as the **headline KPI** ("X % of self-employed Brazilians have a CNPJ — Y % in São Paulo"). The microdata pipeline above gives the *cross-tab depth* (race × CBO × CNPJ × previdência) that SIDRA can't.

---

## 6. MEI registry side — `fetch_mei_registry.py`

Receita Federal publishes the active-MEI register as monthly snapshots through the **Portal do Empreendedor** and Receita's Dados Abertos. Two CNAEs are MEI-eligible and adjacent to domestic work:

| CNAE | Label | Why it matters |
|---|---|---|
| 8800-6/00 | Serviços de assistência social sem alojamento, não especificados anteriormente | the cuidadora bucket |
| 9609-2/99 | Outras atividades de serviços pessoais | residual personal services |
| 8121-4/00 | Limpeza em prédios e em domicílios | cleaning subcontractors |
| 9700-5/00 | Serviços domésticos | *not* legally MEI-eligible, but appears in the register — interesting compliance signal |

`fetch_mei_registry.py` polls Receita's Dados Abertos CSV (national, by CNAE × UF × month), filters to those four codes, and upserts into `fact_mei_registry`. Cadence: monthly when the file refreshes; the Dados Abertos endpoint returns a `Last-Modified` we can short-circuit on.

Practical gotcha: the file is large (~500 MB compressed national CSV). Stream it line-by-line and accumulate per-CNAE counts in a dict — don't load the whole thing in pandas.

---

## 7. Dashboard surface

One new panel — slot it next to the Mensalistas/Diaristas chart in `dashboard/index.html`:

**Panel title:** *MEI e trabalho doméstico — uma fronteira em formação · MEI and domestic work — a forming frontier*

**Three cuts, three lines on one chart:**

1. **% of cuidadoras (CBO 5162) who are conta-própria com CNPJ** — annual series, BR + SP, with a Wilson 95% CI where sample size allows. The headline trend.
2. **MEI registry stock (CNAE 8800-6/00 + 9609-2/99 + 8121-4/00)** on a secondary axis — absolute counts of registered MEIs. The administrative confirmation.
3. **% of trabalhadoras doméstica (VD4009='04') who contribute to previdência** — the existing `fact_prev` series, reframed here as "the rights MEI is supposed to give you, except a lot of formal empregadas don't have them either." Anchors the comparison.

Add a methodology footnote (link to `metodologia.html`) that explains the two operationalisations: (a) survey-side conta-própria com CNPJ in domestic-adjacent CBOs; (b) administrative-side MEI count in domestic-adjacent CNAEs. They measure adjacent things and the gap between them is itself the story (pejotização, in academic register; informalidade reembalada, in advocacy register).

The Foco em São Paulo section also gets a short SP-specific summary card pulling the same `pct_with_cnpj` cell at `geo_code='35'`.

---

## 8. Export to the static dashboard

`etl/export_static.py` already pages every `dw_*` view into JSON. Add `dw_autonomous` and `dw_mei_registry` to its view list. Total disk footprint should be small (~50 KB combined — these are coarse aggregates).

After the first backfill, the static export step is the one that drives the dashboard refresh — make sure it's in the quarterly checklist (per `README.md` step 2).

---

## 9. Sequencing

| Step | What | Why first | Time |
|---|---|---|---|
| 0 | Resume sceneqc, apply the new schema migration | unblocks everything else | 10 min |
| 1 | SIDRA Tabela 4093 conta-própria + CNPJ feed | the headline KPI, immediate value, no microdata re-pull needed | 0.5 day |
| 2 | `build_autonomous_rows()` in `pnadc_microdata.py`, single-quarter run on 2024Q4 | validates the V4010/V4019 byte positions; sanity gates above | 1 day |
| 3 | Backfill the new builder across the 56-quarter PNADC archive | depends on (2) passing the gates | half day of wall-clock, mostly IO-bound |
| 4 | `fetch_mei_registry.py` for the four CNAEs | independent of PNADC; can run in parallel after (1) | 1 day |
| 5 | Dashboard panel + methodology footnote | depends on (1), (3), (4) all landed | 0.5–1 day |
| 6 | Append a QA_AUDIT.md entry documenting the new feed | per the project convention | 30 min |

**Total:** ~4–5 days of focused work. The microdata extension (steps 2–3) is the only piece that needs an active sceneqc connection during the run; (1) and (4) can complete with sceneqc paused if the ETL writes locally first and you batch the upsert after a one-click resume.

---

## 10. Open questions for Mayer

Two things worth confirming with JF before building the dashboard panel:

1. **Framing.** Should the panel lead with the *legal-MEI* reading (cuidadoras and diaristas-as-autônomas) or the *pejotização* reading (mensalistas pushed into MEI to dodge LC 150)? They imply different headline copy. The data supports both — the framing affects which line gets the y-axis emphasis.
2. **Cross-tab depth for the union audience.** STDMSP's base is overwhelmingly diaristas/mensalistas. Do they want the cuidadora cut surfaced too (a politically adjacent but distinct constituency), or should we keep this panel CBO-5121-and-5141 only?

These shape (5) but not (1)–(4); the data layer is the same either way.
