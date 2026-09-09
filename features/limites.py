"""
Limites operacionais de referência e classificação de status.

Os valores vêm do NORMAL_REF definido na Sprint 2 (Forzy_sprint2_ML_agente,
Seção 9.1) e da distribuição real do dataset Dados_Leituras_.csv
(temperatura normal média 68,5 °C; vibração normal média 2,7 mm/s).

Observação: a versão anterior do app classificava temperatura >= 60 °C como
"Alerta", o que marcava quase todas as leituras normais do dataset como
alerta. Os limiares abaixo são coerentes com o dataset e com o notebook.
"""

VARIAVEIS = {
    "Temperatura": {"rotulo": "Temperatura", "unidade": "°C", "campo_csv": "temperatura_c"},
    "Vibracao": {"rotulo": "Vibração", "unidade": "mm/s", "campo_csv": "vibracao_mm_s"},
    "Corrente": {"rotulo": "Corrente", "unidade": "A", "campo_csv": "corrente_a"},
    "RPM": {"rotulo": "Rotação", "unidade": "RPM", "campo_csv": "rotacao_rpm"},
}

# faixa normal (min, max), faixa de alerta (min, max) — fora disso é crítico
LIMITES = {
    "Temperatura": {"normal": (50.0, 80.0), "alerta": (45.0, 88.0)},
    "Vibracao": {"normal": (0.0, 4.5), "alerta": (0.0, 6.0)},
    "Corrente": {"normal": (9.0, 15.0), "alerta": (8.0, 17.0)},
    "RPM": {"normal": (1680.0, 1880.0), "alerta": (1600.0, 1950.0)},
}

NOMES_FALHA = {0: "Normal", 1: "Desbalanceamento", 2: "Superaquecimento", 3: "Falha mecânica"}

CORES_STATUS = {"Normal": "#008300", "Alerta": "#c98500", "Crítico": "#e66767"}
ICONES_STATUS = {"Normal": "🟢", "Alerta": "🟡", "Crítico": "🔴"}

# Paleta por variável (validada para fundo escuro)
CORES_VARIAVEL = {
    "Temperatura": "#d95926",  # laranja
    "Vibracao": "#9085e9",     # violeta
    "Corrente": "#199e70",     # aqua
    "RPM": "#3987e5",          # azul
}
CORES_FALHA = {0: "#008300", 1: "#9085e9", 2: "#d95926", 3: "#e66767"}


def status_variavel(nome, valor):
    """Retorna Normal / Alerta / Crítico para uma variável isolada."""
    if valor is None:
        return "Normal"
    lim = LIMITES[nome]
    if lim["normal"][0] <= valor <= lim["normal"][1]:
        return "Normal"
    if lim["alerta"][0] <= valor <= lim["alerta"][1]:
        return "Alerta"
    return "Crítico"


def classificar_status(temperatura=None, vibracao=None, corrente=None, rpm=None, codigo_falha=0):
    """
    Status consolidado da leitura. Falha rotulada (codigo != 0) é sempre Crítico;
    caso contrário, o pior status entre as variáveis.
    Retorna (status, indicador).
    """
    if codigo_falha not in (None, 0):
        return "Crítico", ICONES_STATUS["Crítico"]
    ordem = {"Normal": 0, "Alerta": 1, "Crítico": 2}
    pior = "Normal"
    for nome, valor in (("Temperatura", temperatura), ("Vibracao", vibracao),
                        ("Corrente", corrente), ("RPM", rpm)):
        s = status_variavel(nome, valor)
        if ordem[s] > ordem[pior]:
            pior = s
    return pior, ICONES_STATUS[pior]


def descricao_limites():
    """Texto curto com as faixas, usado no contexto do Chat IA e em tooltips."""
    linhas = []
    for nome, lim in LIMITES.items():
        u = VARIAVEIS[nome]["unidade"]
        linhas.append(
            f"- {VARIAVEIS[nome]['rotulo']}: normal {lim['normal'][0]:g}–{lim['normal'][1]:g} {u}; "
            f"alerta até {lim['alerta'][1]:g} {u}; acima disso crítico"
        )
    return "\n".join(linhas)
