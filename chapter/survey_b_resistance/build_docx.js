const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun,
        Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
        AlignmentType } = require('/tmp/node_modules/docx');

const RED = "b91c1c", SLATE = "475569", INK = "1a252f", MUTE = "6b7280", OCHRE = "a16207";
const img = fs.readFileSync("filiacao_voz_substitution.png");

function quote(text, anon, color){
  return new Paragraph({
    spacing:{ after: 140 },
    children:[
      new TextRun({ text:"“"+text+"”", italics:true, size:20, color:INK }),
      new TextRun({ text:"  ["+anon+"]", size:16, color:color, bold:true }),
    ],
  });
}
function cell(width, headTxt, headColor, quotes){
  return new TableCell({
    width:{ size:width, type:WidthType.DXA },
    margins:{ top:120, bottom:120, left:160, right:160 },
    shading:{ type:ShadingType.CLEAR, fill: headColor==RED ? "fdecec" : "eef1f4" },
    children:[
      new Paragraph({ spacing:{ after:120 },
        children:[ new TextRun({ text:headTxt, bold:true, size:22, color:headColor }) ] }),
      ...quotes,
    ],
  });
}

const doc = new Document({
  styles:{ default:{ document:{ run:{ font:"Georgia", size:22, color:INK } } } },
  sections:[{
    properties:{ page:{ margin:{ top:1000, bottom:1000, left:1100, right:1100 } } },
    children:[
      new Paragraph({ heading:HeadingLevel.HEADING_1,
        children:[ new TextRun({ text:"O sindicato como infraestrutura da voz", color:INK }) ] }),
      new Paragraph({ spacing:{ after:80 },
        children:[ new TextRun({ text:"Repertórios de resistência individual na Pesquisa B (STDMSP, n=241) — achado preliminar",
          italics:true, size:20, color:MUTE }) ] }),

      new Paragraph({ spacing:{ before:120, after:160 }, children:[ new TextRun({
        text:"Entre seis formas de resistência individual medidas nos depoimentos abertos — saída, voz, "+
        "evitação, lealdade, espiritualidade e solidariedade —, apenas uma se reorganiza de forma "+
        "sistemática por uma variável estrutural, e essa variável é a filiação sindical. Entre as "+
        "filiadas, a VOZ é o registro dominante em 31% dos casos; entre as não-filiadas, cai para 12%. "+
        "Simetricamente, a ESPIRITUALIDADE domina 26% das não-filiadas contra apenas 11% das filiadas. "+
        "As duas células são imagens espelhadas — a assinatura de uma substituição.", size:22 }) ] }),

      new Paragraph({ alignment:AlignmentType.CENTER, spacing:{ after:60 },
        children:[ new ImageRun({ type:"png", data:img,
          transformation:{ width:600, height:271 } }) ] }),
      new Paragraph({ alignment:AlignmentType.CENTER, spacing:{ after:200 },
        children:[ new TextRun({ text:"Figura X. Registro de resistência dominante por filiação sindical. "+
          "Diferença de intensidade (row-centered) significativa em Voz (p=0,002) e Espiritualidade (p=0,037), Mann-Whitney.",
          italics:true, size:16, color:MUTE }) ] }),

      new Paragraph({ spacing:{ after:120 }, children:[ new TextRun({
        text:"A leitura das passagens confirma e aprofunda o padrão: não se trata apenas de mais voz, "+
        "mas de uma voz de natureza distinta.", size:22, bold:true, color:INK }) ] }),

      new Table({
        width:{ size:9360, type:WidthType.DXA },
        columnWidths:[4680,4680],
        borders:{ top:{style:BorderStyle.SINGLE,size:4,color:"d0d0d0"},
          bottom:{style:BorderStyle.SINGLE,size:4,color:"d0d0d0"},
          left:{style:BorderStyle.SINGLE,size:4,color:"d0d0d0"},
          right:{style:BorderStyle.SINGLE,size:4,color:"d0d0d0"},
          insideHorizontal:{style:BorderStyle.SINGLE,size:4,color:"d0d0d0"},
          insideVertical:{style:BorderStyle.SINGLE,size:4,color:"d0d0d0"} },
        rows:[ new TableRow({ children:[
          cell(4680, "Filiadas — voz aprendida, baseada em direitos", RED, [
            quote("Aprendi neste sindicato a exigir os meus direitos.","B-140",RED),
            quote("Aprendi a exigir os meus direitos e pronto.","B-076",RED),
            quote("Quando fui procurar meus direitos, orientada por colegas.","B-227",RED),
            quote("Minha colega que era sócia me trouxe. Meu sindicato entrou com um processo.","B-003",RED),
          ]),
          cell(4680, "Não filiadas — voz individual, improvisada, instável", SLATE, [
            quote("Agora eu reclamo, antes eu ficava calada.","B-226",SLATE),
            quote("Corrijo no ato… Caso se repita, eu caio fora e arrumo outro posto.","B-090",SLATE),
            quote("Precisava implorar meu salário.","B-007",SLATE),
            quote("A patroa, retruquei as ofensas.","B-230",SLATE),
          ]),
        ] }) ],
      }),

      new Paragraph({ spacing:{ before:200, after:140 }, children:[ new TextRun({
        text:"A voz das filiadas é enquadrada em direitos, coletivamente mediada e — de modo notável — "+
        "narrada como algo aprendido no sindicato (“aprendi neste sindicato a exigir os meus direitos”). "+
        "A voz das não-filiadas é um ato solitário e frágil, que frequentemente escorrega para a saída "+
        "(“caio fora e arrumo outro posto”) ou para a súplica (“precisava implorar meu salário”). O sindicato, "+
        "portanto, não aumenta apenas a quantidade de voz: converte reação privada e transcendente (fé, "+
        "paciência) num repertório aprendido, respaldado por direitos e sustentado coletivamente.", size:22 }) ] }),

      new Paragraph({ spacing:{ before:120 }, border:{ top:{ style:BorderStyle.SINGLE, size:4, color:"d0d0d0", space:8 } },
        children:[ new TextRun({
        text:"Nota metodológica. Repertório medido por embeddings semânticos multilíngues de 5.099 passagens "+
        "abertas (paraphrase-multilingual-mpnet); cada registro definido por frases-semente e pontuado por "+
        "similaridade de cosseno. Registro dominante = maior intensidade média por respondente; significância "+
        "sobre a intensidade centrada na própria respondente (remove confundidor de expressividade), teste de "+
        "Mann-Whitney. Filiação: Q32 da Pesquisa B (Sim n=72; Não n=159). Achado exploratório — associação, "+
        "não causa; a filiação pode selecionar mulheres já mais orientadas à voz. n pequeno; validado por "+
        "leitura qualitativa das passagens.", italics:true, size:16, color:MUTE }) ] }),
    ],
  }],
});

Packer.toBuffer(doc).then(b=>{ fs.writeFileSync("achado_filiacao_voz.docx", b);
  console.log("wrote achado_filiacao_voz.docx", b.length, "bytes"); });
