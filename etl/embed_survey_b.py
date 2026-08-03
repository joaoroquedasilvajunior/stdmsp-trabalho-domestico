"""
embed_survey_b.py — Busca semântica + repertório de resistência (Pesquisa B)
===========================================================================

Gera embeddings NEURAIS locais das respostas abertas da Pesquisa B e pontua
cada passagem contra um repertório de formas de resistência individual,
inspirado em Hirschman (1970, Exit/Voice/Loyalty) estendido com evitação,
espiritualidade e solidariedade — repertório documentado na literatura sobre
trabalho doméstico no Brasil (Bernardino-Costa e outros).

PRIVACIDADE
-----------
Roda 100% LOCAL. O modelo é baixado uma vez do HuggingFace (pesos públicos,
não sensíveis). As passagens NUNCA saem do seu computador — não há chamada de
API de nuvem. Os arquivos gerados contêm depoimentos sensíveis: mantenha
locais, não commite, não hospede.

REQUISITOS (rodar uma vez no seu Mac)
-------------------------------------
    pip install sentence-transformers pandas numpy openpyxl

USO
---
    python etl/embed_survey_b.py
    # modo de teste do pipeline, sem baixar modelo (vetores aleatórios):
    python etl/embed_survey_b.py --mock

SAÍDAS
------
    chapter/survey_b_explorer/survey_b_resistance_scores.csv
        anon_id, pergunta, texto, + uma coluna por conceito + conceito_dominante
    chapter/survey_b_explorer/semantic_explorer.html
        explorador offline: escolha um conceito de resistência → passagens
        ranqueadas; clique "semelhantes" para vizinhança semântica.

MODELO
------
Padrão: 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
(768 dim, forte em português, ~1GB). Para algo mais leve troque por
'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2' (384 dim).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Final version May_2023.xlsx"
OUT_DIR = ROOT / "chapter" / "survey_b_explorer"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "survey_b_resistance_scores.csv"
OUT_HTML = OUT_DIR / "semantic_explorer.html"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# =============================================================
# REPERTÓRIO DE RESISTÊNCIA — edite livremente.
# Cada conceito é definido por frases-semente (não keywords). O embedding
# médio das sementes vira o "centróide" do conceito; cada passagem é pontuada
# pela similaridade de cosseno com esse centróide. Frases em PT-BR coloquial
# ajudam o modelo a ancorar no registro das respondentes.
# =============================================================
CONCEPTS = {
    "saida_exit": {
        "label_pt": "Saída (exit)",
        "desc": "Sair do emprego, pedir demissão, trocar de patrão, ir embora.",
        "seeds": [
            "pedi demissão e saí do emprego",
            "fui embora, não aguentei mais e larguei o serviço",
            "troquei de patrão, mudei de casa para trabalhar",
            "decidi sair porque me sentia explorada",
            "abandonei aquele emprego e procurei outro",
        ],
    },
    "voz_voice": {
        "label_pt": "Voz (voice)",
        "desc": "Confrontar, reclamar, negociar, exigir direitos, recorrer ao sindicato/justiça.",
        "seeds": [
            "falei que não estava certo e reclamei com a patroa",
            "não aceito mais desaforo, respondo e me imponho",
            "fui ao sindicato e entrei com processo contra o patrão",
            "negociei meu salário e exigi meus direitos",
            "cobrei o que era meu e disse o que pensava",
        ],
    },
    "evitacao_avoidance": {
        "label_pt": "Evitação / silêncio",
        "desc": "Ficar quieta, engolir, evitar conflito, suportar por medo.",
        "seeds": [
            "fiquei quieta e não falei nada por medo",
            "engoli o desaforo e deixei quieto para não perder o emprego",
            "sempre fui muito calada, evito confusão",
            "aguentei tudo calada, não reagia",
            "por medo de perder o emprego eu aceitava tudo",
        ],
    },
    "lealdade_loyalty": {
        "label_pt": "Lealdade / acomodação",
        "desc": "Permanecer, paciência, gratidão, ver o patrão como família.",
        "seeds": [
            "eles me tratam como se eu fosse da família",
            "sou grata aos meus patrões, fiquei muitos anos na mesma casa",
            "tenho paciência e relevo, são bons patrões",
            "gosto de onde trabalho e pretendo continuar",
            "me consideram parte da família e eu retribuo",
        ],
    },
    "espiritualidade_faith": {
        "label_pt": "Espiritualidade / fé",
        "desc": "Deus, fé, oração, igreja, religião como amparo e força.",
        "seeds": [
            "graças a Deus tenho saúde e força para continuar",
            "minha fé em Deus me dá forças para aguentar",
            "rezo e vou à igreja, entrego tudo nas mãos de Deus",
            "só Deus sabe o que passei, é ele que me sustenta",
            "peço a Deus todos os dias, a religião me conforta",
        ],
    },
    "solidariedade_kin": {
        "label_pt": "Solidariedade / rede",
        "desc": "Recorrer a família, colegas, irmãs, sobrinhas do sindicato.",
        "seeds": [
            "converso com minha irmã e minhas colegas quando preciso",
            "minha sobrinha que é do sindicato me ajudou e me informou",
            "conto com a família, filhos e amigas nos momentos difíceis",
            "as colegas de trabalho trocam informação e se apoiam",
            "procurei uma pessoa de confiança para me orientar",
        ],
    },
}

PII_EXCLUDE = {
    "Carimbo de data/hora", "Timestamp",
    "Nome da entrevistadora", "Nome da pessoa entrevistada",
    "Data da entrevista",
    "CEP", "CEP do local de moradia", "CEP do local de trabalho",
    "Local de moradia",
    "Idade da pessoa entrevistada",
    "Origem étnica (“raça”) da pessoa entrevistada",
    "Nível de educação cumprido da pessoa entrevistada",
}


def short_label(col: str) -> str:
    c = str(col).strip()
    m = re.match(r"^\s*(\d+)\s*[\.\-]?\s*([A-Z]?)\s*[\.\-]", c)
    if m:
        prefix = f"Q{m.group(1)}{m.group(2)} · "
        body = c[m.end():].strip(" -.")
    else:
        prefix, body = "", c
    body = re.sub(r"\s+", " ", body)
    if len(body) > 58:
        body = body[:55].rstrip() + "…"
    return prefix + body


def extract_passages() -> pd.DataFrame:
    raw = pd.read_excel(SRC)
    raw.insert(0, "anon_id", [f"B-{i+1:03d}" for i in range(len(raw))])
    rows = []
    for c in raw.columns:
        if c == "anon_id" or c in PII_EXCLUDE:
            continue
        ser = raw[c].dropna().astype(str)
        if len(ser) < 10:
            continue
        if not (ser.str.len().mean() > 25 and ser.nunique() / len(ser) > 0.5):
            continue
        label = short_label(c)
        for _, r in raw[["anon_id", c]].dropna(subset=[c]).iterrows():
            t = re.sub(r"\s+", " ", str(r[c]).strip())
            if len(t) >= 6:
                rows.append({"anon_id": r["anon_id"], "q": label,
                             "qfull": str(c).strip(), "t": t})
    return pd.DataFrame(rows)


def embed_texts(texts, mock: bool):
    if mock:
        # Vetor determinístico por TEXTO (hash → seed). Assim textos distintos
        # geram vetores distintos e textos iguais geram o mesmo vetor —
        # imitando o comportamento real e permitindo testar a diferenciação
        # entre conceitos. NÃO é semântico; só valida o pipeline.
        import hashlib
        rows = []
        for t in texts:
            h = int(hashlib.md5(str(t).encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(h)
            rows.append(rng.standard_normal(64).astype(np.float32))
        v = np.vstack(rows)
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    from sentence_transformers import SentenceTransformer
    print(f"Carregando modelo {MODEL_NAME} … (download único na 1ª vez)")
    model = SentenceTransformer(MODEL_NAME)
    print(f"Gerando embeddings de {len(texts)} passagens …")
    v = model.encode(texts, batch_size=64, show_progress_bar=True,
                     normalize_embeddings=True, convert_to_numpy=True)
    return v.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true",
                    help="testa o pipeline sem baixar modelo (vetores aleatórios)")
    args = ap.parse_args()

    df = extract_passages()
    print(f"Passagens: {len(df)}")

    # 1. Embeddings das passagens
    P = embed_texts(df["t"].tolist(), args.mock)   # (N, D) normalizados

    # 2. Centróides dos conceitos
    concept_keys = list(CONCEPTS.keys())
    centroids = []
    for k in concept_keys:
        seeds = CONCEPTS[k]["seeds"]
        S = embed_texts(seeds, args.mock)
        c = S.mean(axis=0)
        c = c / (np.linalg.norm(c) + 1e-9)
        centroids.append(c)
    C = np.vstack(centroids)                        # (K, D)

    # 3. Similaridade passagem × conceito (cosseno; ambos normalizados → dot)
    scores = P @ C.T                                # (N, K)

    # 4. CSV
    out = df[["anon_id", "q", "t"]].copy()
    for j, k in enumerate(concept_keys):
        out[k] = scores[:, j].round(4)
    out["conceito_dominante"] = [concept_keys[i] for i in scores.argmax(axis=1)]
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"CSV: {OUT_CSV}")

    # 5. HTML self-contained (vetores quantizados int8 p/ 'semelhantes')
    write_html(df, P, scores, concept_keys, mock=args.mock)
    print(f"HTML: {OUT_HTML}  ({OUT_HTML.stat().st_size/1024/1024:.1f} MB)")


def quantize_int8(M: np.ndarray) -> str:
    """Quantiza matriz normalizada [-1,1] em int8 e devolve base64."""
    q = np.clip(np.round(M * 127), -127, 127).astype(np.int8)
    return base64.b64encode(q.tobytes()).decode("ascii")


def write_html(df, P, scores, concept_keys, mock: bool):
    N, D = P.shape
    passages = [{"id": r.anon_id, "q": r.q, "t": r.t} for r in df.itertuples()]
    concepts_meta = [{"key": k, "label": CONCEPTS[k]["label_pt"],
                      "desc": CONCEPTS[k]["desc"]} for k in concept_keys]

    # Conceito dominante calculado em FULL PRECISION no Python (autoritativo).
    # Não recalcular no JS a partir dos int8 — quantização flipa quase-empates.
    dom = scores.argmax(axis=1).astype(int).tolist()

    payload = {
        "N": N, "D": D,
        "passages": passages,
        "concepts": concepts_meta,
        "scores_b64": quantize_int8(scores),      # (N, K) in [-1,1] — p/ ranking/exibição
        "dom": dom,                                # (N,) índice do conceito dominante (autoritativo)
        "K": len(concept_keys),
        "vecs_b64": quantize_int8(P),             # (N, D) normalized — p/ 'semelhantes'
        "mock": mock,
    }
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    html = HTML_TEMPLATE.replace("__PAYLOAD__", data_json)
    OUT_HTML.write_text(html, encoding="utf-8")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Repertório de resistência — Pesquisa B · STDMSP</title>
<style>
  :root{--ink:#1a1a1a;--paper:#fafaf7;--accent:#b91c1c;--accent-soft:#fee2e2;
        --rule:#e5e5e0;--muted:#6b7280;--hit:#fff3bf;}
  *{box-sizing:border-box} body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
    color:var(--ink);background:var(--paper);margin:0;line-height:1.5;}
  header{background:#fff;border-bottom:1px solid var(--rule);padding:18px 20px;}
  .wrap{max-width:960px;margin:0 auto;padding:0 20px;}
  h1{font-size:20px;font-weight:600;margin:0 0 4px;}
  .sub{font-size:13px;color:var(--muted);margin:0;}
  .warn{background:var(--accent-soft);border:1px solid #fca5a5;color:#7f1d1d;border-radius:8px;
        padding:10px 14px;font-size:12.5px;margin:14px auto;max-width:960px;}
  .mock{background:#fef9c3;border:1px solid #fde047;color:#713f12;border-radius:8px;
        padding:8px 14px;font-size:12.5px;margin:10px auto;max-width:960px;}
  .concepts{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 6px;}
  .cbtn{font-size:13px;padding:8px 14px;border:1px solid var(--rule);border-radius:999px;background:#fff;
        cursor:pointer;color:#374151;}
  .cbtn.active{background:var(--ink);color:#fff;border-color:var(--ink);}
  .cdesc{font-size:12.5px;color:var(--muted);min-height:18px;margin:0 0 10px;}
  .ctrls{display:flex;gap:14px;align-items:center;flex-wrap:wrap;font-size:13px;color:#374151;}
  input[type=range]{vertical-align:middle;}
  select{padding:9px 11px;font-size:13px;border:1px solid var(--rule);border-radius:8px;background:#fff;}
  .meta{font-size:12.5px;color:var(--muted);margin:10px 0;}
  .card{background:#fff;border:1px solid var(--rule);border-radius:10px;padding:14px 16px;margin:10px 0;}
  .card .top{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin-bottom:6px;}
  .anon{font-weight:600;font-size:13px;color:var(--accent);font-variant-numeric:tabular-nums;}
  .qlab{font-size:12px;color:var(--muted);text-align:right;}
  .txt{font-size:14.5px;color:#1f2937;}
  .badges{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;}
  .badge{font-size:11px;padding:3px 8px;border-radius:999px;background:#f3f4f6;color:#374151;}
  .badge.dom{background:var(--accent-soft);color:#7f1d1d;font-weight:600;}
  .more{margin-top:8px;font-size:12px;color:var(--accent);cursor:pointer;border:0;background:none;padding:0;text-decoration:underline;}
  .empty{color:var(--muted);font-size:14px;padding:30px 0;text-align:center;}
  footer{border-top:1px solid var(--rule);padding:16px 0 40px;font-size:12px;color:var(--muted);}
  footer code{background:#f3f4f6;padding:1px 5px;border-radius:4px;}
</style>
</head>
<body>
<header><div class="wrap">
  <h1>Repertório de resistência — Pesquisa B</h1>
  <p class="sub">STDMSP · busca semântica por embeddings · 100% offline</p>
</div></header>

<div class="warn wrap"><strong>Confidencial.</strong> Contém depoimentos individuais sensíveis.
Mantenha local — não commite no git nem publique.</div>
<div id="mockbanner"></div>

<div class="wrap">
  <div class="concepts" id="concepts"></div>
  <p class="cdesc" id="cdesc"></p>
  <div class="ctrls">
    <label>Mínimo de similaridade
      <input id="thr" type="range" min="0" max="70" value="30"> <span id="thrv">0.30</span>
    </label>
    <select id="qfilter"><option value="">Todas as perguntas</option></select>
    <label><input type="checkbox" id="domonly"> só onde este conceito é dominante</label>
  </div>
  <p class="meta" id="meta">Escolha um conceito de resistência acima.</p>
  <div id="results"></div>
</div>

<footer class="wrap">
  <p><strong>Como funciona.</strong> Cada passagem é um vetor semântico (embeddings multilíngues, locais).
  Cada conceito é o vetor médio de frases-semente. A pontuação é a similaridade de cosseno entre passagem e conceito —
  captura sentido, não só palavras (ex.: "receio" aproxima de "medo"; "graças a Deus" aproxima de "fé").
  "Semelhantes" busca os vizinhos mais próximos de uma passagem. Nenhum dado sai do navegador.</p>
  <p>Conceitos e sementes definidos em <code>etl/embed_survey_b.py</code> (bloco CONCEPTS) — edite e rode de novo para ajustar.</p>
</footer>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
const N=D.N, DIM=D.D, K=D.K;

// ---- decode int8 base64 → Float32 (renormalizado) ----
function b64ToInt8(b64){ const bin=atob(b64); const a=new Int8Array(bin.length);
  for(let i=0;i<bin.length;i++) a[i]=bin.charCodeAt(i)<<24>>24; return a; }
const scoresI8 = b64ToInt8(D.scores_b64);   // N*K
const vecsI8   = b64ToInt8(D.vecs_b64);     // N*DIM

function scoreOf(i,k){ return scoresI8[i*K+k]/127; }
function vecOf(i){ const v=new Float32Array(DIM); let n=0;
  for(let d=0; d<DIM; d++){ const x=vecsI8[i*DIM+d]/127; v[d]=x; n+=x*x; }
  n=Math.sqrt(n)||1; for(let d=0; d<DIM; d++) v[d]/=n; return v; }

// conceito dominante — autoritativo, vindo do Python (full precision)
const dom = D.dom;

// ---- UI state ----
let activeK = 0;
const elC = document.getElementById('concepts');
D.concepts.forEach((c,k)=>{ const b=document.createElement('button'); b.className='cbtn'+(k===0?' active':'');
  b.textContent=c.label; b.onclick=()=>{activeK=k; document.querySelectorAll('.cbtn').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); document.getElementById('cdesc').textContent=c.desc; renderConcept();}; elC.appendChild(b); });
document.getElementById('cdesc').textContent = D.concepts[0].desc;

const sel=document.getElementById('qfilter');
[...new Set(D.passages.map(p=>p.q))].sort().forEach(q=>{const o=document.createElement('option');o.value=q;o.textContent=q;sel.appendChild(o);});

const thr=document.getElementById('thr'), thrv=document.getElementById('thrv');
thr.oninput=()=>{thrv.textContent=(thr.value/100).toFixed(2); renderConcept();};
sel.onchange=renderConcept; document.getElementById('domonly').onchange=renderConcept;

if(D.mock){ document.getElementById('mockbanner').innerHTML =
  '<div class="mock wrap"><strong>Modo MOCK.</strong> Vetores aleatórios (teste de pipeline). '+
  'Rode <code>python etl/embed_survey_b.py</code> sem <code>--mock</code> para os embeddings reais.</div>'; }

function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

function card(i, simLabel){
  const p=D.passages[i];
  const badges = D.concepts.map((c,k)=>{
    const s=scoreOf(i,k); const isDom=dom[i]===k;
    return '<span class="badge'+(isDom?' dom':'')+'">'+c.label.split(' ')[0]+' '+s.toFixed(2)+'</span>';
  }).join('');
  return '<div class="card"><div class="top"><span class="anon">'+p.id+'</span>'+
    '<span class="qlab">'+escapeHtml(p.q)+'</span></div>'+
    '<div class="txt">'+escapeHtml(p.t)+'</div>'+
    '<div class="badges">'+badges+'</div>'+
    (simLabel?'':'<button class="more" onclick="showSimilar('+i+')">semelhantes ↗</button>')+'</div>';
}

function renderConcept(){
  const t=thr.value/100, qf=sel.value, domOnly=document.getElementById('domonly').checked;
  const hits=[];
  for(let i=0;i<N;i++){
    if(qf && D.passages[i].q!==qf) continue;
    if(domOnly && dom[i]!==activeK) continue;
    const s=scoreOf(i,activeK); if(s>=t) hits.push({i,s});
  }
  hits.sort((a,b)=>b.s-a.s);
  const top=hits.slice(0,80);
  document.getElementById('meta').textContent =
    hits.length+' passagens ≥ '+t.toFixed(2)+' em "'+D.concepts[activeK].label+'"'+(qf?' · '+qf:'');
  document.getElementById('results').innerHTML =
    top.length? top.map(h=>card(h.i,false)).join('') :
    '<div class="empty">Nenhuma passagem acima do limiar. Abaixe o mínimo de similaridade.</div>';
}

window.showSimilar=function(i){
  const q=vecOf(i); const sims=[];
  for(let j=0;j<N;j++){ if(j===i) continue; const v=vecOf(j); let d=0; for(let x=0;x<DIM;x++) d+=q[x]*v[x]; sims.push({j,d}); }
  sims.sort((a,b)=>b.d-a.d);
  const top=sims.slice(0,12);
  document.getElementById('meta').innerHTML='Semelhantes a <strong>'+D.passages[i].id+'</strong>: “'+escapeHtml(D.passages[i].t.slice(0,80))+'…”';
  document.getElementById('results').innerHTML = card(i,true) +
    '<p class="meta">Vizinhas mais próximas ↓</p>' + top.map(s=>card(s.j,false)).join('');
  window.scrollTo({top:0,behavior:'smooth'});
};

renderConcept();
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
