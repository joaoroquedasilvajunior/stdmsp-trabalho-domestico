# RAIS — caminho para a cifra de filiação sindical das domésticas com carteira

## O que o RAIS oferece (e o que não oferece)

A **RAIS (Relação Anual de Informações Sociais)** é uma declaração obrigatória que todo empregador formal entrega anualmente ao Ministério do Trabalho. Cobre apenas vínculos de emprego **formal com carteira assinada** — o que para a categoria doméstica significa o universo dos ~24% de domésticas com carteira (das ~5,5 milhões totais).

O que importa para o capítulo: a RAIS captura uma variável chamada **"Contribuição Sindical"** ou **"Sindical Contribuintes"** que distingue trabalhadoras que contribuíram ao sindicato de sua categoria daquelas que não contribuíram. Após a Reforma Trabalhista de 2017 a contribuição passou a ser voluntária, então pós-2017 essa variável aproxima razoavelmente bem **filiação efetiva** (antes era contribuição obrigatória, então não distinguia).

A variável é binária por vínculo, agregável por CBO (ocupação) e UF.

## CBO relevantes para domésticas

| CBO 2002 | Descrição |
|---|---|
| 5121-05 | Empregada doméstica nos serviços gerais |
| 5121-10 | Lavadeira em serviços domésticos |
| 5121-15 | Passadeira em serviços domésticos |
| 5121-20 | Cozinheira do serviço doméstico |
| 5162-05 | Cuidadora de crianças |
| 5162-10 | Babá |

Para o capítulo, a agregação relevante é o CBO **5121** (todas as variantes), que captura empregada doméstica em serviços gerais e correlatos. A categoria 5162 (cuidado de crianças) tem sobreposição mas é tecnicamente um CBO distinto — vale somar conforme o recorte do capítulo.

## Onde conseguir os dados

### Opção 1 — Portal PDET (programa de disseminação MTE)

URL: <https://bi.mte.gov.br/bgcaged/>

Esse é o portal oficial. Permite consultas com filtros por CBO, UF, ano, e variáveis de vínculo (incluindo Contribuição Sindical). Limitações: a interface é em Flash-legacy migrado para HTML5, lenta, e nem sempre disponível.

### Opção 2 — Microdados RAIS via PDET

URL: <http://pdet.mte.gov.br/microdados-rais-e-caged>

Microdados anuais em CSV/DBF, divulgados com defasagem de ~12 meses. Para 2024, esperado em meados de 2026. A variável "CBO 2002" e "Sindical Contribuintes" (ou similar) estará nos arquivos do estabelecimento e do vínculo.

### Opção 3 — DIEESE Anuário do Sistema Público de Emprego, Trabalho e Renda

URL: <https://www.dieese.org.br/anuario/anuarioSistemaPublicoEmpregoTrabalhoRenda.html>

O DIEESE compila tabulações da RAIS anualmente. Costumam ter desagregações por CBO, mas precisa consultar os volumes específicos para ver se cruzam Contribuição Sindical × CBO 5121.

### Opção 4 — Solicitação direta ao MTE via LAI

Se as fontes acima não trouxerem o cruzamento exato (CBO 5121 × Contribuição Sindical × UF × Sexo × Cor/Raça), uma solicitação via **Lei de Acesso à Informação** (e-SIC, <https://falabr.cgu.gov.br/>) ao Ministério do Trabalho normalmente retorna em 20 dias úteis. Pedir tabulação cruzada com base na RAIS do ano-base mais recente.

## O que esperar como ordem de grandeza

Com base em referências cruzadas (boletins DIEESE, dissertações sobre trabalho doméstico, Acciari 2019), a filiação sindical entre **trabalhadoras domésticas com carteira** no Brasil é estimada em algo entre **2% e 6%** — bastante abaixo da média geral de filiação sindical no Brasil (~13-15% pré-2017, ~10-12% pós-reforma).

Esse intervalo é coerente com o que sabemos pela natureza da categoria: trabalho doméstico ocorre em domicílios privados isolados, sem locais de trabalho coletivos onde a organização sindical possa atuar. A baixa cobertura sindical da categoria é, ela mesma, um achado estrutural — não um detalhe metodológico.

## Como integrar a cifra ao capítulo

A leitura editorial mais útil é o **contraste em três escalas**:

1. **Cifra nacional via PNADC Anual** (a cifra geral, todas as domésticas): da ordem de 1-3%, capturando a categoria como um todo
2. **Cifra RAIS** (só as domésticas com carteira, 24% da categoria): da ordem de 2-6%, mostrando que **mesmo entre as formalizadas** a filiação é baixa
3. **Cifra da própria Pesquisa B Q32** (rede STDMSP, n=231): conhecida e específica — provavelmente significativamente acima de ambas, dado o viés de auto-seleção da amostra (são mulheres que estavam em contato com o sindicato)

Esse contraste em três escalas faz a contribuição metodológica do capítulo: mostra que o achado da Pesquisa B precisa ser lido contra os baselines nacionais, e que esses baselines variam dependendo do recorte (todas vs. formais).

## Próximo passo prático

Se preferir o caminho mais rápido, consulte o PDET (opção 1) com filtros:
- Variável de busca: "Contribuição Sindical" ou "Sindicalizados"
- CBO: 5121 (todas as variantes)
- Ano-base: o mais recente disponível
- UF: filtrar por SP se quiser cifra estadual, ou Brasil para nacional
- Sexo: F
- Cor/Raça: agregue depois

Tempo estimado: 30-60 minutos para extrair a tabulação. Se ficar travado no portal, a opção 4 (LAI) é mais lenta mas mais confiável.
