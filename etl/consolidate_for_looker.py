"""
consolidate_for_looker.py — Single flat table optimized for Looker Studio
===========================================================================

Joins harmonized_core (483 respondents, common variables) with survey_b_extras
(241 Survey B respondents, richer demographics) into a single wide-format
table that can be imported into Google Looker Studio (formerly Data Studio)
directly via CSV upload or by pasting into a Google Sheet.

Adds a few derived dimensions that make dashboard-building in Looker easier:
  - has_carteira / is_diarista / is_mensalista / is_migrante  — boolean dims
  - data_resposta_year / data_resposta_quarter                — time slicers
  - tem_salario / acima_do_piso                               — salary flags
  - estado_origem_regiao                                      — NE/SE/etc.

OUTPUTS (under chapter/survey_harmonized/)
-------------------------------------------
  - survey_consolidated.csv       UTF-8, comma-separated, ISO dates, NA blank
  - survey_consolidated.xlsx      Google Sheets-friendly (import direct)
  - looker_studio_README.md       how to load and what each column means
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "chapter" / "survey_harmonized"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    core = pd.read_csv(OUT_DIR / "harmonized_core.csv")
    extras = pd.read_csv(OUT_DIR / "survey_b_extras.csv")

    # Left-join core (483 rows) with B extras (241 rows). Survey A respondents
    # will have NA for every extras column — fine for Looker Studio.
    df = core.merge(extras, on="respondent_anon_id", how="left")

    # Coerce data_resposta to ISO datetime, then derive year + quarter
    df["data_resposta"] = pd.to_datetime(df["data_resposta"], errors="coerce", utc=True)
    df["data_resposta_iso"] = df["data_resposta"].dt.strftime("%Y-%m-%d")
    df["data_resposta_year"] = df["data_resposta"].dt.year.astype("Int64")
    df["data_resposta_quarter"] = df["data_resposta"].dt.quarter.astype("Int64")
    df["data_resposta_yyyyqq"] = df.apply(
        lambda r: f"{int(r['data_resposta_year'])}-Q{int(r['data_resposta_quarter'])}"
        if pd.notna(r["data_resposta_year"]) else None,
        axis=1
    )

    # Boolean indicator flags (TRUE/FALSE strings — Looker handles these as dims)
    df["is_survey_a"] = (df["survey_id"] == "A")
    df["is_survey_b"] = (df["survey_id"] == "B")
    df["has_carteira"] = df["tem_carteira"].map({"Sim": True, "Nao": False})
    df["is_diarista"]  = df["tipo_contrato"].map({"diarista": True, "mensalista": False})
    df["is_mensalista"] = df["tipo_contrato"].map({"mensalista": True, "diarista": False})
    df["is_negra"] = (df["raca_grupo"] == "negras")

    # Salary flags (Survey A only — Survey B respondents get NA)
    PISO_CCT_2024 = 1476.75   # SP CCT piso roughly aligns with this in the data
    df["tem_salario_informado"] = df["salario_base_brl"].notna()
    df["salario_no_piso"] = (
        (df["salario_base_brl"].notna())
        & (df["salario_base_brl"] <= PISO_CCT_2024 + 0.5)
    )
    df["salario_acima_piso"] = (
        (df["salario_base_brl"].notna())
        & (df["salario_base_brl"] > PISO_CCT_2024 + 0.5)
    )

    # Migration dimension (Survey B only)
    df["is_migrante_para_sp"] = df["estado_origem"].apply(
        lambda v: False if v == "São Paulo" else (True if pd.notna(v) and str(v).strip() else None)
    )

    # Estado origem → região (Brazilian macro-regions)
    REGIAO = {
        "Acre": "Norte", "Amapá": "Norte", "Amazonas": "Norte", "Pará": "Norte",
        "Rondônia": "Norte", "Roraima": "Norte", "Tocantins": "Norte",
        "Alagoas": "Nordeste", "Bahia": "Nordeste", "Ceará": "Nordeste",
        "Maranhão": "Nordeste", "Paraíba": "Nordeste", "Pernambuco": "Nordeste",
        "Piauí": "Nordeste", "Rio Grande do Norte": "Nordeste", "Sergipe": "Nordeste",
        "Distrito Federal": "Centro-Oeste", "Goiás": "Centro-Oeste",
        "Mato Grosso": "Centro-Oeste", "Mato Grosso do Sul": "Centro-Oeste",
        "Espírito Santo": "Sudeste", "Minas Gerais": "Sudeste",
        "Rio de Janeiro": "Sudeste", "São Paulo": "Sudeste",
        "Paraná": "Sul", "Rio Grande do Sul": "Sul", "Santa Catarina": "Sul",
    }
    df["estado_origem_regiao"] = df["estado_origem"].map(
        lambda v: REGIAO.get(str(v).strip()) if pd.notna(v) else None
    )

    # Normalize NaN → empty string in CSV (Looker reads blank as null).
    # Order columns logically: identifiers, dates, dims, demographics,
    # contract, salary, location, family, education, origin, flags.
    col_order = [
        # identifiers
        "respondent_anon_id", "survey_id", "survey_year",
        # time
        "data_resposta_iso", "data_resposta_year", "data_resposta_quarter", "data_resposta_yyyyqq",
        # demographics core
        "idade_anos", "faixa_etaria_5b", "genero",
        "raca_etnia", "raca_grupo",
        # contract / formality
        "tipo_contrato", "tem_carteira", "carteira_fonte",
        "tempo_dom_categoria",
        # salary
        "salario_base_brl",
        # location
        "bairro_sp", "cep", "moradia_texto",
        # Survey B extras
        "estado_civil", "possui_filho", "n_filhos",
        "nivel_educacao", "escolaridade_mae", "escolaridade_pai", "ocupacao_pais",
        "estado_origem", "pais_origem", "estado_origem_regiao",
        "estado_saude", "modalidade_jornada", "trabalha_atualmente",
        # derived boolean flags (Looker-friendly)
        "is_survey_a", "is_survey_b", "is_negra",
        "has_carteira", "is_diarista", "is_mensalista",
        "tem_salario_informado", "salario_no_piso", "salario_acima_piso",
        "is_migrante_para_sp",
    ]
    # Drop the original Timestamp-typed datetime since we already exposed iso/year/quarter
    df = df[[c for c in col_order if c in df.columns]]

    # Outputs
    csv_path = OUT_DIR / "survey_consolidated.csv"
    xlsx_path = OUT_DIR / "survey_consolidated.xlsx"

    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_excel(xlsx_path, index=False, sheet_name="survey_consolidated")

    print(f"Wrote {csv_path}  ({len(df)} rows × {df.shape[1]} cols)")
    print(f"Wrote {xlsx_path}")

    # Quick coverage snapshot
    print("\n=== Coverage of derived Looker-friendly flags ===")
    for col in ["has_carteira", "is_diarista", "is_migrante_para_sp", "tem_salario_informado", "salario_no_piso"]:
        non_na = df[col].notna().sum()
        true_count = (df[col] == True).sum()
        print(f"  {col:30s}  not-null: {non_na:3d}/{len(df)}  ·  TRUE: {true_count}")

    # README for Looker Studio
    readme = """# Looker Studio — Loading the STDMSP Consolidated Survey Data

## What this file is

`survey_consolidated.csv` (and `.xlsx`) is a single wide-format table
combining the two STDMSP surveys into 483 rows × 42 columns. Each row is
one respondent. Survey A respondents (n=242) and Survey B respondents
(n=241) share a common set of demographic columns; Survey B respondents
additionally carry the richer fields (estado civil, escolaridade dos
pais, estado de origem, etc.) — those columns are blank for Survey A
respondents.

## How to load into Looker Studio (formerly Data Studio)

### Option 1 — Google Sheets (recommended for iteration)

1. Open https://sheets.google.com and create a new sheet.
2. File → Import → Upload → drag `survey_consolidated.xlsx`.
3. Choose "Replace spreadsheet" and import.
4. In Looker Studio, create a new report → Add data → Google Sheets connector
   → pick the sheet you just created.
5. Looker auto-detects column types (number / text / date / boolean).
   You may want to manually set:
   - `data_resposta_iso` → Date (YYYY-MM-DD)
   - `data_resposta_year` → Number (integer)
   - `salario_base_brl` → Number (currency BRL)
   - All `is_*` and `has_*` columns → Boolean

### Option 2 — CSV upload (simpler, less editable)

1. In Looker Studio: Add data → "File upload" connector.
2. Upload `survey_consolidated.csv`.
3. Same type-mapping notes as above apply.

## Column groups

### Identifiers (3 cols)

- `respondent_anon_id` — anonymized ID, format `A-001..A-242` or `B-001..B-241`.
  CPF was dropped from the file per project decision; no PII remains.
- `survey_id` — A or B.
- `survey_year` — "2024-25" or "2021-23".

### Time slicers (4 cols)

- `data_resposta_iso` — ISO date string when the response was submitted.
- `data_resposta_year`, `data_resposta_quarter`, `data_resposta_yyyyqq` —
  derived for Looker time controls.

### Core demographics (5 cols)

- `idade_anos` — numeric age (Survey B only; A has bands only).
- `faixa_etaria_5b` — harmonized 5-band scheme: 18-29 / 30-39 / 40-49 / 50-59 / 60+.
- `genero` — "Feminino" (A direct), "Masculino" (A only), "Feminino_presumido" (B inferred).
- `raca_etnia` — preta / parda / branca / amarela / indigena.
- `raca_grupo` — negras (preta+parda) / nao_negras.

### Contract & formality (4 cols)

- `tipo_contrato` — mensalista / diarista (Survey A only).
- `tem_carteira` — Sim / Nao. Direct from Q13 in Survey B; INFERRED from
  Q6 in Survey A (with vínculo = Sim, diarista = Nao).
- `carteira_fonte` — "direto_Q13" or "inferido_de_Q6" to flag confidence.
- `tempo_dom_categoria` — text/categorical, free.

### Salary (1 col + 3 derived flags)

- `salario_base_brl` — numeric monthly salary in BRL (Survey A only).
- `tem_salario_informado` — boolean: salary present at all.
- `salario_no_piso` — boolean: salary ≈ R$ 1.477 (CCT piso).
- `salario_acima_piso` — boolean: salary > piso.

### Location (3 cols)

- `bairro_sp` — neighborhood name (Survey A direct, B blank).
- `cep` — normalized to XXXXX-XXX format.
- `moradia_texto` — raw free-text address.

### Survey B extras (12 cols)

Blank for Survey A respondents.

- `estado_civil`, `possui_filho`, `n_filhos`,
- `nivel_educacao`, `escolaridade_mae`, `escolaridade_pai`, `ocupacao_pais`,
- `estado_origem`, `pais_origem`, `estado_origem_regiao` (Norte/Nordeste/etc.),
- `estado_saude`, `modalidade_jornada`, `trabalha_atualmente`.

### Looker-friendly boolean dimensions (10 cols)

These are derived for fast filter-building. All are TRUE/FALSE/NA.

- `is_survey_a`, `is_survey_b` — survey indicator flags.
- `is_negra` — TRUE for negras (preta+parda).
- `has_carteira` — TRUE if `tem_carteira == "Sim"`.
- `is_diarista`, `is_mensalista` — TRUE/FALSE by contract type.
- `tem_salario_informado` — TRUE if salary present.
- `salario_no_piso` — TRUE if reported salary at the CCT piso.
- `salario_acima_piso` — TRUE if reported salary above the piso.
- `is_migrante_para_sp` — TRUE if `estado_origem != "São Paulo"` (Survey B only).

## Suggested first dashboards to build for testing

1. **Composição racial × carteira (Survey B)**. Filter `is_survey_b = TRUE`,
   chart % by `raca_grupo` and `has_carteira`. Should reproduce the
   Black-higher-carteira finding (54,8% vs 41,9%).

2. **Distribuição do salário (Survey A)**. Filter `is_survey_a = TRUE`,
   histogram of `salario_base_brl` with annotation at R$ 1.477.
   Or use `salario_no_piso` as a category dimension.

3. **Mapa de origem (Survey B)**. Bar chart of `estado_origem` grouped by
   `estado_origem_regiao` for color.

4. **Cobertura por survey**. Use `is_survey_a` / `is_survey_b` as filters,
   any column as the metric.

## Limitations to keep in mind

- **Not a probability sample.** Both surveys are convenience samples
  through the STDMSP membership network. Inferences to the general
  category require caution; for representative SP-wide claims, the
  PNAD Contínua microdata (separate dashboard) is the right source.
- **Survey A is worker-administered** and has substantial gaps in the
  longer-text questions (Q12 contract type only 65,3% answered, etc.).
- **Carteira for Survey A is inferred** from Q6, not asked directly.
  Use `carteira_fonte == "direto_Q13"` as a filter when you need
  high-confidence carteira data only.
- **Survey B does not ask salary directly.** Salary-related visualizations
  should filter to `is_survey_a = TRUE`.

## Regenerating this file

When new survey waves land, place the new XLSX files at the project root and run:

```bash
cd ~/Documents/Claude/Domestic\\ Work
python etl/harmonize_surveys.py
python etl/consolidate_for_looker.py
```

Then re-upload to Google Sheets or refresh the Looker file connector.
"""
    (OUT_DIR / "looker_studio_README.md").write_text(readme, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'looker_studio_README.md'}")


if __name__ == "__main__":
    main()
