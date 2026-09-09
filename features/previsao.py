"""
Modelo de previsão de falhas — integração do classificador da Sprint 2 ao app.

Pipeline igual ao notebook Forzy_sprint2_ML_agente (Seção 4): 4 sensores +
média/desvio móvel em janela de 5 leituras. Diferenças em relação ao notebook:
- sem as features de cadastro (fabricante_enc, modelo_enc, potencia_kw), que
  não existem no cadastro do MongoDB;
- classificador HistGradientBoosting (scikit-learn), equivalente ao LightGBM
  (mesma família de gradient boosting por histogramas) e instalável sem
  compilação no Python 3.13/3.14; class_weight="balanced" no lugar do SMOTE.

O modelo treinado fica em modelos/modelo_falhas.joblib (scripts/treinar_modelo.py).
"""
import json
import os

import numpy as np

SENSORES = ["RPM", "Vibracao", "Temperatura", "Corrente"]
JANELA = 5
NOMES_CLASSE = {0: "Normal", 1: "Desbalanceamento", 2: "Superaquecimento", 3: "Falha mecânica"}

_DIR_MODELOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modelos")
CAMINHO_MODELO = os.path.join(_DIR_MODELOS, "modelo_falhas.joblib")
CAMINHO_META = os.path.join(_DIR_MODELOS, "modelo_falhas_meta.json")

RECOMENDACOES = {
    0: "Operação dentro do padrão. Manter plano de manutenção preventiva (inspeção mensal, revisão trimestral).",
    1: "Indício de desbalanceamento: programar inspeção de vibração, verificar alinhamento, fixação e estado dos rolamentos. "
       "Se a vibração passar de 6 mm/s de forma sustentada, abrir OS corretiva.",
    2: "Indício de superaquecimento: verificar ventilação/aletas, carga aplicada e corrente por fase. "
       "Temperatura sustentada acima de 88 °C exige parada e manutenção corretiva.",
    3: "Indício de falha mecânica: queda de rotação com vibração e corrente altas. Isolar o equipamento com segurança, "
       "inspecionar acoplamento, rolamentos e transmissão; registrar leituras no momento da parada.",
}


def nomes_features():
    return SENSORES + [f"{s}_roll_mean" for s in SENSORES] + [f"{s}_roll_std" for s in SENSORES]


def montar_features_janela(leituras):
    """
    Recebe uma lista de leituras (dicts com RPM, Vibracao, Temperatura, Corrente),
    da mais antiga para a mais recente, e monta o vetor de features da última.
    """
    ultimas = [l for l in leituras if all(l.get(s) is not None for s in SENSORES)][-JANELA:]
    if not ultimas:
        return None
    atual = ultimas[-1]
    vetor = [float(atual[s]) for s in SENSORES]
    for s in SENSORES:
        serie = np.array([float(l[s]) for l in ultimas])
        vetor.append(float(serie.mean()))
    for s in SENSORES:
        serie = np.array([float(l[s]) for l in ultimas])
        vetor.append(float(serie.std(ddof=1)) if len(serie) > 1 else 0.0)
    return np.array(vetor).reshape(1, -1)


_cache = {"modelo": None, "meta": None}


def carregar_modelo():
    if _cache["modelo"] is None:
        if not os.path.exists(CAMINHO_MODELO):
            return None, None
        import joblib
        try:
            _cache["modelo"] = joblib.load(CAMINHO_MODELO)
        except Exception:
            # versão incompatível do scikit-learn: rode scripts/treinar_modelo.py
            return None, None
        if os.path.exists(CAMINHO_META):
            with open(CAMINHO_META, encoding="utf-8") as f:
                _cache["meta"] = json.load(f)
    return _cache["modelo"], _cache["meta"]


def modelo_disponivel():
    return os.path.exists(CAMINHO_MODELO)


def prever(leituras):
    """
    Retorna dict com classe prevista, confiança, probabilidades por classe,
    score de risco (1 - P(normal)) e recomendação — ou None sem modelo/dados.
    """
    modelo, meta = carregar_modelo()
    if modelo is None:
        return None
    X = montar_features_janela(leituras)
    if X is None:
        return None
    probs = modelo.predict_proba(X)[0]
    classes = list(modelo.classes_)
    prob_por_classe = {int(c): float(p) for c, p in zip(classes, probs)}
    classe = int(classes[int(np.argmax(probs))])
    risco = 1.0 - prob_por_classe.get(0, 0.0)
    if risco < 0.2:
        nivel = "Baixo"
    elif risco < 0.5:
        nivel = "Moderado"
    else:
        nivel = "Alto"
    return {
        "classe": classe,
        "classe_nome": NOMES_CLASSE.get(classe, str(classe)),
        "confianca": float(probs.max()),
        "probabilidades": {NOMES_CLASSE[k]: round(v, 4) for k, v in sorted(prob_por_classe.items())},
        "risco": round(risco, 4),
        "nivel_risco": nivel,
        "recomendacao": RECOMENDACOES.get(classe, ""),
        "janela_leituras": min(len(leituras), JANELA),
        "modelo": (meta or {}).get("modelo", "HistGradientBoosting"),
        "acuracia_teste": (meta or {}).get("acuracia_teste"),
        "f1_macro_teste": (meta or {}).get("f1_macro_teste"),
    }


def prever_tendencia(leituras_recentes, leituras_anteriores):
    """
    Compara a média das leituras recentes com as anteriores para descrever a
    tendência de cada variável (↑ ↓ →). Ambas as listas: dicts de leituras.
    """
    tend = {}
    for s in SENSORES:
        rec = [float(l[s]) for l in leituras_recentes if l.get(s) is not None]
        ant = [float(l[s]) for l in leituras_anteriores if l.get(s) is not None]
        if not rec or not ant:
            continue
        m_rec, m_ant = np.mean(rec), np.mean(ant)
        delta = m_rec - m_ant
        rel = delta / m_ant if m_ant else 0
        seta = "→"
        if rel > 0.05:
            seta = "↑"
        elif rel < -0.05:
            seta = "↓"
        tend[s] = {"recente": round(m_rec, 2), "anterior": round(m_ant, 2), "delta": round(delta, 2), "seta": seta}
    return tend


def resumo_modelo():
    """Metadados do modelo treinado (algoritmo, acurácia, F1) para exibir na tela."""
    try:
        import json as _json
        with open(CAMINHO_META, encoding="utf-8") as f:
            meta = _json.load(f)
        return {
            "algoritmo": meta.get("modelo", "-"),
            "acuracia": meta.get("acuracia_teste"),
            "f1_macro": meta.get("f1_macro_teste"),
            "features": len(meta.get("features") or []),
            "janela": meta.get("janela"),
            "classes": meta.get("classes", {}),
            "treinado_em": meta.get("treinado_em"),
        }
    except Exception:
        return {}
