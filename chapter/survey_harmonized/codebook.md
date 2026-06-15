# Codebook — STDMSP Surveys Harmonized Core

Gerado por `etl/harmonize_surveys.py` em 2026-06-12.

## Decisões editoriais

- **CPF dropado integralmente.** O CPF da entrevistada presente na Survey A (col 4, 87,6% cobertura) NÃO é incluído em nenhuma das saídas harmonizadas. Apenas IDs anônimos sequenciais (A-001..A-242, B-001..B-241) são mantidos. Os arquivos brutos preservam o CPF mas não devem ser commitados nem compartilhados.
- **Gênero da Survey B presumido feminino.** A Survey B não pergunta gênero diretamente; o enquadramento qualitativo todo é em forma feminina ("trabalhadora", "ela"). Marcamos como `Feminino_presumido` em vez de `Feminino` para tornar visível que é uma inferência.
- **Carteira da Survey A inferida.** A Survey A não pergunta carteira diretamente. Inferimos a partir da Q6 (diarista vs com vínculo): "com vínculo" → carteira=Sim; "diarista" → carteira=Não. A coluna `carteira_fonte` distingue `inferido_de_Q6` (A) de `direto_Q13` (B). Cobertura limitada pela Q6 (65,3% na Survey A).
- **Tipo de contrato apenas na Survey A.** A Survey B não distingue mensalista/diarista. A coluna `tipo_contrato` é NA para todos os respondentes B.
- **Faixas etárias harmonizadas em 5 bandas** (18-29, 30-39, 40-49, 50-59, 60+) por compatibilidade com a granularidade da Survey A. Para a Survey B reconstruímos as bandas a partir da idade numérica (99,6% cobertura). A coluna `idade_anos` é populada apenas para B.

## Variáveis — `harmonized_core.csv` / `harmonized_core.xlsx`

| Coluna | Tipo | Survey A | Survey B | Notas |
|---|---|---|---|---|
| `survey_id` | str | "A" | "B" | identificador do survey |
| `survey_year` | str | "2024-25" | "2021-23" | janela de campo |
| `respondent_anon_id` | str | A-001..A-242 | B-001..B-241 | ID anônimo sequencial |
| `data_resposta` | datetime | Timestamp do Google Forms | idem | quando a resposta foi submetida |
| `idade_anos` | num | NA | col "Idade da pessoa entrevistada" | apenas B coleta numérica |
| `faixa_etaria_5b` | str | mapeada da col Q1 | derivada de `idade_anos` | bandas 18-29/30-39/40-49/50-59/60+ |
| `genero` | str | col Q2 (Feminino/Masculino) | "Feminino_presumido" | B não pergunta direto |
| `raca_etnia` | str | col Q3 normalizada | col "Origem étnica" normalizada | preta/parda/branca/amarela/indigena |
| `raca_grupo` | str | derivado | derivado | negras (preta+parda) / nao_negras |
| `tipo_contrato` | str | mensalista/diarista de Q6 | NA | só Survey A pergunta |
| `tem_carteira` | str | inferido de Q6 | direto de Q13 | `carteira_fonte` distingue |
| `carteira_fonte` | str | "inferido_de_Q6" | "direto_Q13" | rastreabilidade |
| `tempo_dom_categoria` | str | col Q7 (texto) | col Q1 (texto) | tempo de ocupação |
| `salario_base_brl` | num | parsed de Q9 | NA | só Survey A pergunta |
| `bairro_sp` | str | col "Bairro" direta | NA | B não separa bairro |
| `cep` | str | col CEP normalizada | col "CEP do local de moradia" normalizada | formato XXXXX-XXX |
| `moradia_texto` | str | col Q4 livre | col "Local de moradia" livre | texto bruto preservado |

## Variáveis — `survey_b_extras.csv` (Survey B apenas)

| Coluna | Descrição |
|---|---|
| `respondent_anon_id` | ID anônimo B-001..B-241 |
| `estado_civil` | solteira/casada/divorciada/viúva/união estável |
| `possui_filho` / `n_filhos` | Sim/Não + número |
| `nivel_educacao` | 8 categorias do analfabetismo ao superior |
| `escolaridade_mae` / `escolaridade_pai` | mesma escala |
| `ocupacao_pais` | texto livre |
| `estado_origem` / `pais_origem` | migração interna e internacional |
| `estado_saude` | autorreporte |
| `modalidade_jornada` | Completo/Parcial (não é mensalista/diarista) |
| `trabalha_atualmente` | Sim/Não |

## Limitações conhecidas

- **Survey A é auto-aplicada**, com lacunas substanciais nas perguntas longas (Q12 contrato 65%, Q13/Q14 sobre CCT 47–52%). As demografias core (idade, gênero, raça) têm 97% de cobertura.
- **Survey B é entrevista guiada**, com cobertura demográfica acima de 96% em todas as variáveis core. As lacunas estão nos campos qualitativos longos (relatos de abuso, negociação) — preservados nos arquivos brutos mas fora do escopo desta harmonização.
- **Composição racial das amostras** difere: Survey A 59,6% pretas+pardas (240/235 válidos), Survey B 67,9% (159/234). Ambas são amostras de conveniência via STDMSP — não são representativas da categoria em SP. A diferença pode refletir vieses de auto-seleção (quem aceita responder formulário escrito vs. quem aceita entrevista qualitativa).
- **Não há vínculo respondente entre os dois surveys.** Tratá-los como amostras independentes.
