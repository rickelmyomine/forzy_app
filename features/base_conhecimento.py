"""
Base de conhecimento do Chat IA (RAG leve).

Fontes (pasta conhecimento/):
  - guia_motores_planta.md         limiares, estados de falha e plano de manutenção (app)
  - manual_tecnico.md              manual do sistema IO-Link + folha de dados WEG (Sprint 3/4)
  - corpus_sprint3_anomalias.txt   blocos PERGUNTA/RESPOSTA sobre detecção de anomalias
  - qa20_troubleshooting.json      20 perguntas com resposta de referência
  - relatorio_operacional_iolink.txt
  - RELATORIO_OPERACIONAL.md       estado da planta, indicadores e ações recomendadas
  - REQUISITOS.md                  requisitos funcionais, não funcionais, dados e modelo
  - GLOSSARIO.md                   termos técnicos, de manutenção e do sistema
  - CORPUS_ESTRUTURADO.md          blocos de diagnóstico (sintoma → causa → ação)

Chunking por seção (## no markdown, [BLOCO] no corpus, 1 par por QA).
Recuperação por TF-IDF + cosseno (scikit-learn) com fallback para sobreposição de termos.
"""
import json
import os
import re
import unicodedata

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conhecimento")

SINONIMOS = {
    "esquentando": "superaquecimento temperatura alta", "quente": "superaquecimento temperatura",
    "vibrando": "vibração desbalanceamento", "trepidando": "vibração desbalanceamento",
    "barulhento": "vibração ruído mecânica", "barulho": "ruído mecânica", "travado": "falha mecânica rotação",
    "parou": "falha mecânica parada corretiva", "rolamento": "mancal rolamento mecânica",
    "graxa": "lubrificação preventiva", "lubrificar": "lubrificação preventiva",
    "rpm": "rotação", "amperes": "corrente", "ampere": "corrente", "aquecimento": "superaquecimento",
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return texto


def expandir_consulta(q):
    ql = _normalizar(q)
    extras = [v for k, v in SINONIMOS.items() if k in ql]
    return q + (" " + " ".join(extras) if extras else "")


def _ler(nome):
    caminho = os.path.join(_DIR, nome)
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _chunks_markdown(texto, fonte):
    chunks = []
    for sec in re.split(r"\n(?=## )", texto):
        sec = sec.strip()
        if not sec.startswith("## "):
            continue
        titulo, _, corpo = sec.partition("\n")
        chunks.append({"fonte": fonte, "titulo": titulo.lstrip("#").strip(), "texto": corpo.strip()})
    return chunks


_CATEGORIAS_IGNORADAS = {"projeto", "comparacao com sprint 2", "proximos passos", "agente conversacional"}
_PALAVRAS_IGNORADAS = ("sprint", "fiap", "academic", "notebook")


def _limpar_texto(t):
    t = re.sub(r"\(?\bSprint \d\)?", "", t)
    t = t.replace("do projeto Forzy", "do sistema").replace("projeto Forzy", "sistema de monitoramento")
    return re.sub(r"\s{2,}", " ", t).strip()


def _chunks_corpus(texto, fonte):
    chunks = []
    for bloco in re.split(r"\[BLOCO \d+\]", texto)[1:]:
        cat = re.search(r"CATEGORIA:\s*(.+)", bloco)
        if cat and cat.group(1).strip().lower() in _CATEGORIAS_IGNORADAS:
            continue
        if any(pal in bloco.lower() for pal in _PALAVRAS_IGNORADAS):
            continue
        perg = re.search(r"PERGUNTA:\s*(.+?)\nRESPOSTA:", bloco, re.S)
        resp = re.search(r"RESPOSTA:\s*(.+?)(?:\n-{10,}|$)", bloco, re.S)
        if perg and resp:
            chunks.append({
                "fonte": fonte, "titulo": f"{(cat.group(1).strip() if cat else 'Geral')}: {_limpar_texto(' '.join(perg.group(1).split()))}",
                "texto": _limpar_texto(" ".join(resp.group(1).split())),
            })
    return chunks


def _chunks_qa(texto, fonte):
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return []
    return [{"fonte": fonte, "titulo": d["pergunta"], "texto": d["resposta_referencia"]} for d in dados]


_cache = {"chunks": None, "vetorizador": None, "matriz": None}


def carregar_chunks():
    if _cache["chunks"] is not None:
        return _cache["chunks"]
    chunks = []
    t = _ler("guia_motores_planta.md")
    if t:
        chunks += _chunks_markdown(t, "Guia de Telemetria e Falhas dos Motores")
    t = _ler("manual_tecnico.md")
    if t:
        chunks += _chunks_markdown(t, "Manual Técnico do Sistema de Monitoramento / Folha de dados WEG")
    t = _ler("corpus_sprint3_anomalias.txt")
    if t:
        chunks += _chunks_corpus(t, "Base de conhecimento — detecção de anomalias")
    t = _ler("qa20_troubleshooting.json")
    if t:
        chunks += _chunks_qa(t, "Perguntas e respostas de troubleshooting")
    t = _ler("RELATORIO_OPERACIONAL.md")
    if t:
        chunks += _chunks_markdown(t, "Relatório Operacional da planta")
    t = _ler("REQUISITOS.md")
    if t:
        chunks += _chunks_markdown(t, "Requisitos do sistema")
    t = _ler("GLOSSARIO.md")
    if t:
        chunks += _chunks_markdown(t, "Glossário")
    t = _ler("CORPUS_ESTRUTURADO.md")
    if t:
        chunks += _chunks_markdown(t, "Corpus estruturado — diagnóstico e manutenção")
    t = _ler("relatorio_operacional_iolink.txt")
    if t:
        chunks.append({"fonte": "Relatório operacional IO-Link", "titulo": "Relatório de estado operacional 19/05/2026", "texto": t.strip()})
    for i, c in enumerate(chunks):
        c["id"] = i
    _cache["chunks"] = chunks
    return chunks


def _indexar():
    chunks = carregar_chunks()
    if _cache["matriz"] is not None or not chunks:
        return
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        docs = [_normalizar(f"{c['titulo']} {c['titulo']} {c['texto']}") for c in chunks]
        vet = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        _cache["matriz"] = vet.fit_transform(docs)
        _cache["vetorizador"] = vet
    except Exception:
        _cache["vetorizador"] = None


def buscar(consulta, k=4, boost_categoria=None):
    """
    Retorna os k chunks mais relevantes para a consulta:
    [{'id','fonte','titulo','texto','score'}].
    `boost_categoria` (ex.: 'superaquecimento') dá prioridade a seções cujo
    título contenha o termo — re-ranking por estado operacional (RF03.3).
    """
    chunks = carregar_chunks()
    if not chunks:
        return []
    _indexar()
    q = _normalizar(expandir_consulta(consulta))
    scores = []
    if _cache["vetorizador"] is not None:
        from sklearn.metrics.pairwise import cosine_similarity
        vq = _cache["vetorizador"].transform([q])
        sims = cosine_similarity(vq, _cache["matriz"])[0]
        scores = list(sims)
    else:
        termos = set(re.findall(r"[a-z0-9]{3,}", q))
        for c in chunks:
            bag = set(re.findall(r"[a-z0-9]{3,}", _normalizar(c["titulo"] + " " + c["texto"])))
            scores.append(len(termos & bag) / (len(termos) or 1))
    if boost_categoria:
        bc = _normalizar(boost_categoria)
        scores = [s + (0.15 if bc in _normalizar(c["titulo"]) else 0) for s, c in zip(scores, chunks)]
    ordem = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:k]
    return [{**chunks[i], "score": float(scores[i])} for i in ordem if scores[i] > 0]


def formatar_para_contexto(resultados, max_chars=900):
    linhas = []
    for r in resultados:
        texto = r["texto"] if len(r["texto"]) <= max_chars else r["texto"][:max_chars] + "…"
        linhas.append(f"[Fonte: {r['fonte']} — {r['titulo']}]\n{texto}")
    return "\n\n".join(linhas)
