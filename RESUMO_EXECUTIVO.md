# Trabalho doméstico no Brasil — Resumo executivo

**Maio de 2026 · Painel de dados em colaboração com a STDMSP e a pesquisa do Prof. Jean-François Mayer (Concordia)**

Este resumo apresenta as conclusões verificadas a partir do painel <https://stdmsp-trabalho-domestico.joaoroquer.workers.dev/>, alimentado pelos microdados da PNAD Contínua (IBGE) agregados pela equipe do projeto. Período coberto: 1º trimestre de 2012 a 4º trimestre de 2025 — 56 trimestres consecutivos, todos os 27 estados.

---

## Cinco achados verificados

### 1. Somos 5,5 milhões

A categoria das trabalhadoras domésticas no Brasil tem **5,5 milhões de pessoas**. Destas, **92% são mulheres** e **67,7% são negras** (pretas + pardas). Sustentamos uma em cada dez mulheres no mercado de trabalho brasileiro.

*Fonte: PNADC microdados (IBGE), 4T 2025. Validação cruzada com DIEESE (Infográfico abr/2025): % mulheres 91,93% computado vs. 91,9% DIEESE.*

### 2. A Lei das Domésticas (LC 150/2015) está sendo descumprida

Apenas **24% das trabalhadoras domésticas têm carteira assinada**. Mais grave: apenas **14,6% efetivamente contribuem para a previdência**. Isso significa que **mesmo entre quem tem carteira, muitas não estão tendo a contribuição recolhida** — o direito à aposentadoria não está sendo construído. Onze anos depois da entrada em vigor da LC 150, três em cada quatro trabalhadoras continuam na informalidade.

*Fonte: PNADC microdados (IBGE), variável V4032 (era contribuinte de previdência na semana de referência), agregada pela equipe do projeto.*

### 3. A jornada média é de 32 horas, não 40

A jornada média semanal das trabalhadoras domésticas no Brasil é de **31,7 horas**, estável há 13 anos e bem abaixo do limite legal de 44 horas/semana (CF Art. 7º, XIII; LC 150/2015 Art. 2º). A categoria é **estruturalmente part-time** — predominantemente diarista, trabalhando em múltiplos domicílios. Apenas 10% trabalham acima do limite legal. Políticas que assumem uma trabalhadora de tempo integral em um único patrão modelam incorretamente a realidade.

*Fonte: PNADC microdados, variável V4039 (horas habituais semanais no trabalho principal).*

### 4. Mais negras, mas não mais valorizadas

Em 13 anos, a participação de mulheres pretas e pardas na categoria subiu **+5,2 pontos percentuais** (de 62,5% para 67,7%). Ao mesmo tempo, o **hiato salarial racial permaneceu estável em torno de 84%** — uma trabalhadora doméstica negra continua recebendo R$ 84 para cada R$ 100 recebidos por uma não-negra. A racialização da categoria avança, mas a desvalorização das negras dentro dela não diminuiu.

*Fonte: PNADC microdados, agregação cor/raça (V2010) × rendimento (VD4019). Validação contra DIEESE: 84% computado vs. 84% publicado.*

### 5. São Paulo concentra 22,6% da categoria nacional — e está em situação distinta

São Paulo tem **1,26 milhão de trabalhadoras domésticas**, a maior categoria absoluta do país. Mas três pontos a destacar:

- A categoria está **encolhendo em SP** (−13% desde 2012), enquanto se mantém estável nacionalmente
- A racialização avançou **mais rápido em SP** que no resto do país: +7,7 pp negras vs. +5,2 pp nacional
- Em SP, **pretas e pardas trabalham mais horas e contribuem mais para a previdência** que as não-negras — uma reversão do padrão racial esperado. A explicação está na composição ocupacional: a força de trabalho negra em SP está concentrada em mensalistas, formato com jornada mais longa e maior probabilidade de formalização.

*Fonte: PNADC microdados, recorte UF=SP × cor/raça × jornada × previdência.*

---

## Metodologia

Os números deste resumo vêm dos **microdados oficiais da PNAD Contínua trimestral**, divulgados pelo IBGE. A agregação foi feita pela equipe do projeto aplicando os pesos amostrais V1028 sobre o filtro VD4009 ∈ {03, 04} (trabalhador doméstico com/sem carteira). Cruzamentos: cor/raça × sexo × formalidade × UF computados ao nível trimestral, totalizando 56 trimestres entre 1T 2012 e 4T 2025.

A validação cruzada com as publicações da DIEESE (Boletim Especial sobre Trabalho Doméstico 2024 e Infográfico de abril 2025) confirma os números até a precisão de uma casa decimal. Para o painel completo, intervalos de confiança por UF, séries temporais com marcação dos eventos políticos (EC 72/2013, LC 150/2015, ratificação da C189), e comparativo internacional Brasil ↔ México:

**Painel interativo:** <https://stdmsp-trabalho-domestico.joaoroquer.workers.dev/>
**Metodologia detalhada:** <https://stdmsp-trabalho-domestico.joaoroquer.workers.dev/metodologia.html>
**Código e ETL:** <https://github.com/joaoroquedasilvajunior/stdmsp-trabalho-domestico>
