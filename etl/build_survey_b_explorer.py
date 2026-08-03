"""
build_survey_b_explorer.py
==========================

Constrói um explorador de BUSCA SEMÂNTICA (lexical + morfológica) sobre as
respostas abertas da Pesquisa B (2021-23, n=241).

Por que assim (e não embeddings neurais):
  - Os dados são SENSÍVEIS (relatos de abuso, saúde, família). Nada pode ir
    para um serviço hospedado / vector DB na nuvem. Este explorador é um único
    HTML offline — abre no navegador, sem servidor, sem rede.
  - O problema real da Pesquisa B é ortografia informal + morfologia do
    português ("cuidar/cuidando/cuidado", "esclarescer/esclarecer"). Um
    normalizador morfológico (stemmer leve) resolve isso — a mesma lição do
    Q18. BM25 dá o ranqueamento por relevância.
  - Upgrade para embeddings verdadeiros (sinônimos) é possível depois, com
    sentence-transformers rodando localmente no Mac. Ver nota no rodapé do HTML.

Privacidade:
  - Campos de PII direta (nome, CEP, endereço/local de moradia, idade exata,
    nome da entrevistadora) são EXCLUÍDOS do corpus pesquisável.
  - Cada passagem é rotulada só pelo anon_id (B-001..B-241), nunca por nome.
  - O HTML resultante CONTÉM os depoimentos (incl. relatos sensíveis) e por
    isso NÃO deve ser commitado no git nem hospedado. Fica local.

Entrada:  Final version May_2023.xlsx   (Pesquisa B bruta)
Saída:    chapter/survey_b_explorer/explorer.html
          chapter/survey_b_explorer/passages.json   (dump auditável)
"""

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Final version May_2023.xlsx"
OUT_DIR = ROOT / "chapter" / "survey_b_explorer"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_HTML = OUT_DIR / "explorer.html"
OUT_JSON = OUT_DIR / "passages.json"

# Campos de PII direta — NUNCA entram no corpus pesquisável
PII_EXCLUDE = {
    "Carimbo de data/hora", "Timestamp",
    "Nome da entrevistadora", "Nome da pessoa entrevistada",
    "Data da entrevista",
    "CEP", "CEP do local de moradia", "CEP do local de trabalho",
    "Local de moradia",
    "Idade da pessoa entrevistada",
    # metadados já estruturados noutros lugares — não são depoimento
    "Origem étnica (“raça”) da pessoa entrevistada",
    "Nível de educação cumprido da pessoa entrevistada",
}


def short_label(col: str) -> str:
    """Rótulo curto para exibição (número da pergunta + trecho)."""
    c = str(col).strip()
    m = re.match(r"^\s*(\d+)\s*[\.\-]?\s*([A-Z]?)\s*[\.\-]", c)
    prefix = ""
    if m:
        num = m.group(1)
        letter = m.group(2)
        prefix = f"Q{num}{letter} · "
        body = c[m.end():].strip(" -.")
    else:
        body = c
    body = re.sub(r"\s+", " ", body)
    if len(body) > 58:
        body = body[:55].rstrip() + "…"
    return prefix + body


def is_open_text(ser: pd.Series) -> bool:
    s = ser.dropna().astype(str)
    if len(s) < 10:
        return False
    distinct_ratio = s.nunique() / len(s)
    avg_len = s.str.len().mean()
    return avg_len > 25 and distinct_ratio > 0.5


def main():
    raw = pd.read_excel(SRC)
    raw.insert(0, "anon_id", [f"B-{i+1:03d}" for i in range(len(raw))])

    fields = []
    for c in raw.columns:
        if c == "anon_id" or c in PII_EXCLUDE:
            continue
        if is_open_text(raw[c]):
            fields.append(c)

    passages = []
    for c in fields:
        label = short_label(c)
        for _, row in raw[["anon_id", c]].dropna(subset=[c]).iterrows():
            txt = re.sub(r"\s+", " ", str(row[c]).strip())
            if len(txt) < 6:
                continue
            passages.append({
                "id": row["anon_id"],
                "q": label,
                "qfull": str(c).strip(),
                "t": txt,
            })

    # Lista de perguntas (para o filtro dropdown)
    q_labels = sorted({p["q"] for p in passages})

    # Dump auditável
    OUT_JSON.write_text(json.dumps(passages, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    html = build_html(passages, q_labels, n_resp=len(raw), n_fields=len(fields))
    OUT_HTML.write_text(html, encoding="utf-8")

    print(f"Passagens: {len(passages)}  ·  campos: {len(fields)}  ·  respondentes: {len(raw)}")
    print(f"HTML: {OUT_HTML}  ({OUT_HTML.stat().st_size/1024:.0f} KB)")
    print(f"JSON: {OUT_JSON}")


def build_html(passages, q_labels, n_resp, n_fields) -> str:
    data_json = json.dumps(passages, ensure_ascii=False, separators=(",", ":"))
    q_json = json.dumps(q_labels, ensure_ascii=False)

    # ---- HEAD + CSS (string simples, sem f-string para não brigar com JS) ----
    head = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Explorador de depoimentos — Pesquisa B · STDMSP</title>
<style>
  :root{ --ink:#1a1a1a; --paper:#fafaf7; --accent:#b91c1c; --accent-soft:#fee2e2;
         --rule:#e5e5e0; --muted:#6b7280; --hit:#fff3bf; }
  *{box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",system-ui,sans-serif;
       color:var(--ink); background:var(--paper); margin:0; line-height:1.5;}
  header{background:#fff; border-bottom:1px solid var(--rule); padding:18px 20px;}
  .wrap{max-width:920px; margin:0 auto; padding:0 20px;}
  h1{font-size:20px; font-weight:600; margin:0 0 4px;}
  .sub{font-size:13px; color:var(--muted); margin:0;}
  .warn{background:var(--accent-soft); border:1px solid #fca5a5; color:#7f1d1d;
        border-radius:8px; padding:10px 14px; font-size:12.5px; margin:14px auto; max-width:920px;}
  .searchbar{position:sticky; top:0; background:var(--paper); padding:16px 0 10px; z-index:5;
             border-bottom:1px solid var(--rule);}
  .row{display:flex; gap:10px; flex-wrap:wrap; align-items:center;}
  #q{flex:1; min-width:240px; padding:12px 14px; font-size:16px; border:1px solid var(--rule);
     border-radius:8px; background:#fff; color:var(--ink);}
  #q:focus{outline:2px solid var(--accent); outline-offset:-1px;}
  select{padding:11px 12px; font-size:14px; border:1px solid var(--rule); border-radius:8px; background:#fff;}
  .meta{font-size:12.5px; color:var(--muted); margin:10px 0 0;}
  .chips{display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;}
  .chip{font-size:12px; padding:5px 11px; border:1px solid var(--rule); border-radius:999px;
        background:#fff; cursor:pointer; color:#374151;}
  .chip:hover{background:#f5f5f0;}
  .results{margin:16px 0 60px;}
  .card{background:#fff; border:1px solid var(--rule); border-radius:10px; padding:14px 16px; margin:10px 0;}
  .card .top{display:flex; justify-content:space-between; gap:10px; align-items:baseline; margin-bottom:6px;}
  .anon{font-weight:600; font-size:13px; color:var(--accent); font-variant-numeric:tabular-nums;}
  .qlab{font-size:12px; color:var(--muted); text-align:right;}
  .score{font-size:11px; color:#9ca3af; font-variant-numeric:tabular-nums;}
  .txt{font-size:14.5px; color:#1f2937;}
  mark{background:var(--hit); padding:0 1px; border-radius:2px;}
  .empty{color:var(--muted); font-size:14px; padding:30px 0; text-align:center;}
  footer{border-top:1px solid var(--rule); padding:16px 0 40px; font-size:12px; color:var(--muted);}
  footer code{background:#f3f4f6; padding:1px 5px; border-radius:4px;}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Explorador de depoimentos — Pesquisa B</h1>
    <p class="sub">STDMSP · """ + f"{n_resp} respondentes · {n_fields} perguntas abertas · " + str(len(passages)) + """ passagens · 100% offline</p>
  </div>
</header>

<div class="warn wrap">
  <strong>Confidencial.</strong> Este arquivo contém depoimentos individuais, incluindo relatos sensíveis.
  Mantenha-o apenas no seu computador — não commite no git nem publique. Passagens identificadas apenas por código anônimo (B-001…).
</div>

<div class="wrap">
  <div class="searchbar">
    <div class="row">
      <input id="q" type="search" placeholder="Busque por tema em português…  ex: medo de perder o emprego" autocomplete="off">
      <select id="qfilter"><option value="">Todas as perguntas</option></select>
    </div>
    <div class="chips" id="chips"></div>
    <p class="meta" id="meta">Digite um tema acima. A busca entende variações de escrita e conjugação (cuidar / cuidando / cuidado).</p>
  </div>
  <div class="results" id="results"></div>
</div>

<footer class="wrap">
  <p><strong>Como funciona.</strong> Busca lexical com normalização morfológica do português (stemmer leve) + ranqueamento BM25.
  Tudo roda no navegador; nenhum dado sai do seu computador. Não usa modelo neural de embeddings —
  portanto encontra variações de <em>escrita e conjugação</em>, mas não sinônimos distantes
  (ex: "medo" não traz automaticamente "receio"). Para busca por sinônimos, o próximo passo é gerar
  embeddings localmente com <code>sentence-transformers</code> no seu Mac.</p>
  <p>Gerado por <code>etl/build_survey_b_explorer.py</code>.</p>
</footer>

<script id="data" type="application/json">__DATA__</script>
<script id="qlist" type="application/json">__QLIST__</script>
<script>
"""

    # ---- JS (string simples) ----
    js = r"""
const PASSAGES = JSON.parse(document.getElementById('data').textContent);
const QLABELS  = JSON.parse(document.getElementById('qlist').textContent);

// ---------- Normalizador morfológico PT ----------
// Dobra acentos, minúsculas, remove pontuação, aplica stemming leve por
// remoção de sufixos. O mesmo princípio que corrigiu o Q18: "cuidar",
// "cuidando", "cuidado" -> "cuid".
function foldAccents(s){
  return s.normalize('NFD').replace(/[̀-ͯ]/g,'');
}
const STOP = new Set(("de a o e que do da em um para com nao uma os no se na por mais " +
  "as dos como mas foi ao ele das tem seu sua ou ser quando muito ha nos ja esta eu " +
  "tambem so pelo pela ate isso ela entre depois sem mesmo aos seus quem nas me esse " +
  "eles voce essa num nem suas meu as minha numa pelos elas qual lhe deles essas esses " +
  "pelas este dele tu te vos vossa vossos vossas nosso nossa nossos nossas dela delas " +
  "esta estou estao ser sao e do da e").split(/\s+/));

const SUFFIXES = [
  // ordem: mais longos primeiro
  "issimos","issimas","issimo","issima",
  "amentos","amento","imentos","imento",
  "adores","adoras","ador","adora",
  "ando","endo","indo","ondo",
  "acoes","acao","coes","cao",
  "mente",
  "adas","idas","ada","ida","ado","ido","idos","ados",
  "aram","eram","iram","avam","iam",
  "aria","erias","arias","ariam",
  "ares","eres","ires","ar","er","ir",
  "eza","ezas","dade","dades","ista","istas","ismo","ismos",
  "oes","aes","aos",
  "s"
];

function stem(tok){
  let w = tok;
  if(w.length <= 3) return w;
  for(const suf of SUFFIXES){
    if(w.length - suf.length >= 3 && w.endsWith(suf)){
      return w.slice(0, w.length - suf.length);
    }
  }
  return w;
}

function tokenize(s){
  const base = foldAccents(String(s).toLowerCase());
  const raw = base.split(/[^a-z0-9]+/).filter(t => t.length >= 2 && !STOP.has(t));
  return raw.map(stem).filter(t => t.length >= 2);
}

// ---------- Índice BM25 (construído no load) ----------
const N = PASSAGES.length;
const docTokens = new Array(N);
const df = new Map();
let totalLen = 0;
for(let i=0;i<N;i++){
  const toks = tokenize(PASSAGES[i].t);
  docTokens[i] = toks;
  totalLen += toks.length;
  const seen = new Set();
  for(const t of toks){ if(!seen.has(t)){ seen.add(t); df.set(t,(df.get(t)||0)+1);} }
}
const avgdl = totalLen / Math.max(N,1);
const k1 = 1.5, b = 0.75;
function idf(term){
  const n = df.get(term) || 0;
  return Math.log(1 + (N - n + 0.5)/(n + 0.5));
}
// term frequency por doc (lazy map)
const tfCache = new Array(N);
function tf(i){
  if(tfCache[i]) return tfCache[i];
  const m = new Map();
  for(const t of docTokens[i]) m.set(t,(m.get(t)||0)+1);
  tfCache[i]=m; return m;
}

function score(qTerms, i){
  const dl = docTokens[i].length;
  const m = tf(i);
  let s = 0;
  for(const qt of qTerms){
    const f = m.get(qt); if(!f) continue;
    s += idf(qt) * (f*(k1+1))/(f + k1*(1 - b + b*dl/avgdl));
  }
  return s;
}

// ---------- Busca ----------
function search(query, qfilter){
  const qTerms = [...new Set(tokenize(query))];
  if(qTerms.length===0) return {terms:[], hits:[]};
  const hits = [];
  for(let i=0;i<N;i++){
    if(qfilter && PASSAGES[i].q !== qfilter) continue;
    const s = score(qTerms, i);
    if(s>0) hits.push({i, s});
  }
  hits.sort((a,b)=> b.s - a.s);
  return {terms:qTerms, hits:hits.slice(0,60)};
}

// ---------- Destaque ----------
function highlight(text, qTerms){
  // marca tokens cujo stem casa com algum termo da busca
  const words = String(text).split(/(\s+)/);
  const qset = new Set(qTerms);
  return words.map(w=>{
    const core = foldAccents(w.toLowerCase()).replace(/[^a-z0-9]/g,'');
    if(core && qset.has(stem(core))) return '<mark>'+escapeHtml(w)+'</mark>';
    return escapeHtml(w);
  }).join('');
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

// ---------- Render ----------
const elResults = document.getElementById('results');
const elMeta = document.getElementById('meta');
function render(query){
  const qfilter = document.getElementById('qfilter').value;
  if(!query || !query.trim()){
    elResults.innerHTML='';
    elMeta.textContent='Digite um tema acima. A busca entende variações de escrita e conjugação (cuidar / cuidando / cuidado).';
    return;
  }
  const {terms, hits} = search(query, qfilter);
  if(hits.length===0){
    elResults.innerHTML='<div class="empty">Nenhuma passagem encontrada para "'+escapeHtml(query)+'".</div>';
    elMeta.textContent='Termos buscados (radicais): '+terms.join(', ');
    return;
  }
  elMeta.textContent = hits.length+' passagens · radicais: '+terms.join(', ');
  elResults.innerHTML = hits.map(h=>{
    const p = PASSAGES[h.i];
    return '<div class="card"><div class="top">'+
      '<span class="anon">'+p.id+'</span>'+
      '<span class="qlab">'+escapeHtml(p.q)+'</span></div>'+
      '<div class="txt">'+highlight(p.t, terms)+'</div>'+
      '<div class="score">relevância '+h.s.toFixed(2)+'</div></div>';
  }).join('');
}

// ---------- UI wiring ----------
const input = document.getElementById('q');
let deb;
input.addEventListener('input', ()=>{ clearTimeout(deb); deb=setTimeout(()=>render(input.value), 120); });
document.getElementById('qfilter').addEventListener('change', ()=>render(input.value));

// popular filtro de perguntas
const sel = document.getElementById('qfilter');
for(const q of QLABELS){ const o=document.createElement('option'); o.value=q; o.textContent=q; sel.appendChild(o); }

// chips de exemplo
const EXAMPLES = ["medo de perder o emprego","abuso","não tinha comida","carteira assinada",
                  "sonho","discriminada","tempo livre","sindicato ajudou","dormia no emprego","salário atrasado"];
const chips = document.getElementById('chips');
for(const ex of EXAMPLES){
  const c=document.createElement('span'); c.className='chip'; c.textContent=ex;
  c.onclick=()=>{ input.value=ex; render(ex); input.focus(); };
  chips.appendChild(c);
}
</script>
</body>
</html>
"""

    return (head + js).replace("__DATA__", data_json).replace("__QLIST__", q_json)


if __name__ == "__main__":
    main()
