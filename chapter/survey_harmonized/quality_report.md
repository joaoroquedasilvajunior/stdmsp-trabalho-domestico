# STDMSP Surveys — Quality Report (Harmonized Core)

Gerado por `etl/harmonize_surveys.py`. Survey A n=242, Survey B n=241, total n=483.

## 1. Cobertura por variável (preenchimento ≠ vazio)

### Survey A (2024-25) (n = 242)

| Variável | Preenchimento | % |
|---|---:|---:|
| `respondent_anon_id` | 242/242 | 100.0% |
| `survey_id` | 242/242 | 100.0% |
| `survey_year` | 242/242 | 100.0% |
| `data_resposta` | 242/242 | 100.0% |
| `idade_anos` | 0/242 | 0.0% |
| `faixa_etaria_5b` | 235/242 | 97.1% |
| `genero` | 236/242 | 97.5% |
| `raca_etnia` | 235/242 | 97.1% |
| `raca_grupo` | 235/242 | 97.1% |
| `tipo_contrato` | 158/242 | 65.3% |
| `tem_carteira` | 158/242 | 65.3% |
| `carteira_fonte` | 158/242 | 65.3% |
| `tempo_dom_categoria` | 236/242 | 97.5% |
| `salario_base_brl` | 221/242 | 91.3% |
| `bairro_sp` | 216/242 | 89.3% |
| `cep` | 137/242 | 56.6% |
| `moradia_texto` | 152/242 | 62.8% |

### Survey B (2021-23) (n = 241)

| Variável | Preenchimento | % |
|---|---:|---:|
| `survey_id` | 241/241 | 100.0% |
| `survey_year` | 241/241 | 100.0% |
| `respondent_anon_id` | 241/241 | 100.0% |
| `data_resposta` | 241/241 | 100.0% |
| `idade_anos` | 240/241 | 99.6% |
| `faixa_etaria_5b` | 240/241 | 99.6% |
| `genero` | 241/241 | 100.0% |
| `raca_etnia` | 234/241 | 97.1% |
| `raca_grupo` | 234/241 | 97.1% |
| `tipo_contrato` | 0/241 | 0.0% |
| `tem_carteira` | 236/241 | 97.9% |
| `carteira_fonte` | 236/241 | 97.9% |
| `tempo_dom_categoria` | 205/241 | 85.1% |
| `salario_base_brl` | 0/241 | 0.0% |
| `bairro_sp` | 0/241 | 0.0% |
| `cep` | 160/241 | 66.4% |
| `moradia_texto` | 203/241 | 84.2% |

### Core unificado (n = 483)

| Variável | Preenchimento | % |
|---|---:|---:|
| `respondent_anon_id` | 483/483 | 100.0% |
| `survey_id` | 483/483 | 100.0% |
| `survey_year` | 483/483 | 100.0% |
| `data_resposta` | 483/483 | 100.0% |
| `idade_anos` | 240/483 | 49.7% |
| `faixa_etaria_5b` | 475/483 | 98.3% |
| `genero` | 477/483 | 98.8% |
| `raca_etnia` | 469/483 | 97.1% |
| `raca_grupo` | 469/483 | 97.1% |
| `tipo_contrato` | 158/483 | 32.7% |
| `tem_carteira` | 394/483 | 81.6% |
| `carteira_fonte` | 394/483 | 81.6% |
| `tempo_dom_categoria` | 441/483 | 91.3% |
| `salario_base_brl` | 221/483 | 45.8% |
| `bairro_sp` | 216/483 | 44.7% |
| `cep` | 297/483 | 61.5% |
| `moradia_texto` | 355/483 | 73.5% |

## 2. Cruzamentos de sanidade

### Raça (grupo) × Survey — composição racial em cada survey

| raca_grupo   |   A |   B |   Total |
|:-------------|----:|----:|--------:|
| nao_negras   |  95 |  75 |     170 |
| negras       | 140 | 159 |     299 |
| nan          |   7 |   7 |     nan |
| Total        | 242 | 241 |     483 |

### Faixa etária × Survey

| faixa_etaria_5b   |   A |   B |   Total |
|:------------------|----:|----:|--------:|
| 18-29             |   5 |  17 |      22 |
| 30-39             |  47 |  38 |      85 |
| 40-49             |  70 |  61 |     131 |
| 50-59             |  71 |  82 |     153 |
| 60+               |  42 |  42 |      84 |
| nan               |   7 |   1 |     nan |
| Total             | 242 | 241 |     483 |

### Raça × Faixa etária (n combinado)

| raca_grupo   |   18-29 |   30-39 |   40-49 |   50-59 |   60+ |   nan |   Total |
|:-------------|--------:|--------:|--------:|--------:|------:|------:|--------:|
| nao_negras   |       6 |      38 |      47 |      47 |    31 |     1 |     170 |
| negras       |      16 |      45 |      77 |     105 |    49 |     7 |     299 |
| nan          |       0 |       2 |       7 |       1 |     4 |     0 |     nan |
| Total        |      22 |      85 |     131 |     153 |    84 |     0 |     483 |

### Survey A: Raça × Tipo de contrato (apenas para quem respondeu Q6)

| raca_grupo   |   diarista |   mensalista |   nan |   Total |
|:-------------|-----------:|-------------:|------:|--------:|
| nao_negras   |         36 |           36 |    23 |      95 |
| negras       |         45 |           39 |    56 |     140 |
| nan          |          0 |            2 |     5 |     nan |
| Total        |         81 |           77 |     0 |     242 |

### Survey B: Raça × Carteira (resposta direta)

| raca_grupo   |   Nao |   Sim |   nan |   Total |
|:-------------|------:|------:|------:|--------:|
| nao_negras   |    43 |    31 |     1 |      75 |
| negras       |    71 |    86 |     2 |     159 |
| nan          |     3 |     2 |     2 |     nan |
| Total        |   117 |   119 |     0 |     241 |

## 3. Salário base (Survey A apenas)
| raca_grupo   |   count |   mean |   median |
|:-------------|--------:|-------:|---------:|
| nao_negras   |      85 |   1695 |     1477 |
| negras       |     130 |   1739 |     1477 |

Resumo geral: n=221, mín R$ 1477, mediana R$ 1477, máx R$ 3500, média R$ 1722