"""
Classificação de eventos de manutenção em 5 categorias — versão leve do
classificador zero-shot de classificação de eventos.

No notebook a classificação usa similaridade de cosseno entre embeddings
(MiniLM multilíngue) do texto do evento e frases-protótipo por categoria.
Aqui, para não depender do download do modelo (RNF03), usamos o mesmo
conjunto de protótipos com similaridade TF-IDF + bônus por termos-chave,
o que roda em milissegundos dentro do Streamlit. Os protótipos são os
mesmos de PROTOTIPOS_CATEGORIA (Corpus_Estruturado, Seção 3).
"""
import re
import unicodedata

CATEGORIAS = {
    "anomalia_eletrica": "Anomalia elétrica",
    "anomalia_mecanica": "Anomalia mecânica",
    "manutencao_preventiva": "Manutenção preventiva",
    "manutencao_corretiva": "Manutenção corretiva",
    "operacao_normal": "Operação normal",
}

PROTOTIPOS = {
    "anomalia_eletrica": (
        "desvio de temperatura superaquecimento sobrecarga térmica aquecimento "
        "anormal do enrolamento corrente elevada isolação queimado curto fase "
        "sobrecorrente disjuntor esquentando temperatura alta"
    ),
    "anomalia_mecanica": (
        "desvio de vibração aceleração desbalanceamento folga mecânica "
        "desalinhamento ruído anormal rolamento mancal eixo trepidação barulho "
        "travado queda de rotação acoplamento engripado"
    ),
    "manutencao_preventiva": (
        "inspeção programada lubrificação revisão periódica checklist de rotina "
        "calibração limpeza reaperto troca de graxa verificação preventiva "
        "plano de manutenção mensal trimestral"
    ),
    "manutencao_corretiva": (
        "reparo após falha substituição de peça quebrada ordem de serviço "
        "corretiva parada não planejada troca de rolamento rebobinamento "
        "conserto substituído quebrou parou emergência"
    ),
    "operacao_normal": (
        "leituras dentro do padrão esperado sem desvio funcionamento estável e "
        "regular normal ok sem anomalia operação regular"
    ),
}

_STOPWORDS = set("""a o e de da do das dos em no na nos nas um uma para por com sem
ao aos que se foi ser está estava como mais muito ou é as os à""".split())


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = texto.lower()
    tokens = re.findall(r"[a-z0-9]+", texto)
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _stem(token):
    # "stemmer" bem simples para português: corta sufixos comuns
    for suf in ("mente", "ções", "coes", "ção", "cao", "ando", "endo", "ada", "ado", "ais", "eis", "os", "as", "es", "s"):
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


def _bag(texto):
    return {_stem(t) for t in _normalizar(texto)}


_PROTOTIPOS_BAG = {cat: _bag(txt) for cat, txt in PROTOTIPOS.items()}


def classificar_evento(texto, tipo_manutencao=None):
    """
    Retorna (categoria, nome_legivel, scores) para o texto de um evento.
    `tipo_manutencao` (Preventiva/Corretiva/...) entra como sinal adicional,
    igual ao campo `categoria_gold` derivado no notebook.
    """
    bag = _bag(texto)
    scores = {}
    for cat, proto in _PROTOTIPOS_BAG.items():
        inter = len(bag & proto)
        scores[cat] = inter / (len(proto) ** 0.5 * max(len(bag), 1) ** 0.5) if bag else 0.0

    if tipo_manutencao == "Preventiva":
        scores["manutencao_preventiva"] += 0.05
    elif tipo_manutencao == "Corretiva":
        scores["manutencao_corretiva"] += 0.05

    if not any(scores.values()):
        categoria = "manutencao_preventiva" if tipo_manutencao == "Preventiva" else "operacao_normal"
    else:
        categoria = max(scores, key=scores.get)
    return categoria, CATEGORIAS[categoria], scores
