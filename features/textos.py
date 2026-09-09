"""
Textos explicativos exibidos abaixo de cada gráfico/tabela: para que serve,
como ler e qual a faixa ideal conforme o manual técnico e o histórico
analisado (limites em features/limites.py).
"""
from features.limites import LIMITES, VARIAVEIS

_EXPLICA_VARIAVEL = {
    "Temperatura": (
        "Temperatura da carcaça do motor. Indica sobrecarga, ventilação obstruída ou problema de isolação. "
        "Quanto mais tempo acima da faixa, maior o desgaste da isolação (cada 10 °C acima do nominal reduz a "
        "vida útil pela metade, regra do fabricante)."
    ),
    "Vibracao": (
        "Vibração global em mm/s (velocidade eficaz). É o principal sinal de desbalanceamento, desalinhamento, "
        "folga e desgaste de rolamento. Picos curtos na partida são normais; valores altos sustentados não."
    ),
    "Corrente": (
        "Corrente consumida. Sobe com a carga mecânica e com o superaquecimento; queda brusca pode indicar "
        "falta de fase ou carga desacoplada. Compare com a corrente nominal da placa da máquina."
    ),
    "RPM": (
        "Rotação do eixo. Queda de rotação com vibração e corrente altas é a assinatura de falha mecânica "
        "(rolamento travando, acoplamento danificado, carga presa)."
    ),
}


def faixa_ideal(variavel):
    lim = LIMITES[variavel]
    u = VARIAVEIS[variavel]["unidade"]
    n0, n1 = lim["normal"]
    a0, a1 = lim["alerta"]
    if variavel == "RPM":
        return (f"🟢 Normal: {n0:g}–{n1:g} {u} · 🟡 Alerta: {a0:g}–{n0:g} {u} (rotação caindo) · "
                f"🔴 Crítico: abaixo de {a0:g} {u} ou falha rotulada")
    return (f"🟢 Normal: {n0:g}–{n1:g} {u} · 🟡 Alerta: {n1:g}–{a1:g} {u} · "
            f"🔴 Crítico: acima de {a1:g} {u} ou falha rotulada")


def intro_variavel(variavel):
    rot = VARIAVEIS[variavel]["rotulo"]
    return (f"**{rot} — para que serve:** {_EXPLICA_VARIAVEL[variavel]}  \n"
            f"**Faixa ideal (conforme manual técnico e histórico analisado):** {faixa_ideal(variavel)}. "
            f"A área verde do gráfico marca a faixa normal e a linha pontilhada o limite de alerta; "
            f"cada máquina tem seus próprios valores de placa, mas as faixas de operação segura são as mesmas.")


INTRO_TIPO_GRAFICO = {
    "Linha": "Série no tempo: mostra a evolução de cada máquina ao longo do dia/horário selecionado. Ideal para ver tendências e picos.",
    "Colunas": "Colunas: valor médio (ou máximo) de cada máquina no período, colorido pelo status. Ideal para comparar máquinas entre si.",
    "Barras": "Barras horizontais: mesma leitura das colunas, ordenada da pior para a melhor máquina. Ideal para ranking.",
    "Pizza": "Pizza: proporção de leituras Normal / Alerta / Crítico no período. Ideal para ver o quanto do tempo a planta operou fora da faixa.",
    "Radar": "Radar: as 4 variáveis de cada máquina em escala relativa ao limite de alerta (100 % = no limite). Quanto maior a área, mais próxima do risco a máquina está. Ideal para comparar até 8 máquinas.",
}

INTRO = {
    "kpis": "Resumo do período selecionado: total de leituras, máquinas monitoradas, leituras rotuladas em falha e quantas máquinas estão em estado crítico na última leitura. Ideal: 0 críticas e leituras em falha próximas de zero.",
    "estado_atual": "Última leitura de cada máquina dentro do dia/horário escolhido, com o status consolidado (pior entre as 4 variáveis; falha rotulada é sempre crítico). Linhas amarelas = alerta, vermelhas = crítico.",
    "unificado": "Os quatro gráficos mostram, lado a lado, todas as máquinas selecionadas. Com mais de 8 máquinas as linhas ficam neutras e a linha colorida é a média da planta; passe o mouse para ver cada máquina.",
    "resumo_maquina": "Média, mínimo e máximo de cada máquina no período e quantas leituras em falha ela teve. Ordenado pelo máximo: as primeiras linhas são as que mais se afastaram da faixa ideal.",
    "individual": "Uma máquina isolada: as marcas × indicam leituras rotuladas em falha (cor por tipo). Use para investigar um episódio específico.",
    "falhas_kpis": "Quantidade de leituras rotuladas em cada tipo de falha no período e número de máquinas afetadas. Ideal: zero.",
    "falhas_timeline": "Cada quadrado é uma leitura em falha: eixo horizontal = horário, eixo vertical = máquina, cor = tipo. Sequências longas de quadrados são episódios sustentados — os mais preocupantes.",
    "falhas_barras": "Total de leituras por máquina: verde = operação normal, demais cores = tipo de falha. Máquinas com barra colorida grande são candidatas a inspeção.",
    "falhas_pizza": "Proporção dos tipos de falha no período. Superaquecimento pede verificação de ventilação/carga; desbalanceamento pede inspeção de vibração/rolamentos; falha mecânica pede parada e inspeção.",
    "falhas_episodios": "Um episódio é uma sequência contínua de leituras em falha da mesma máquina. Mostra dia, horário de início/fim, duração e os valores extremos registrados.",
    "ranking": "Máquina com mais leituras em falha no dia selecionado, na semana, no mês e no ano (contando todo o histórico do banco). Repetição da mesma máquina em vários períodos indica problema crônico — priorize na análise de frota.",
    "criticas": "Atalho: filtra o dashboard para mostrar só as máquinas que estão em estado crítico na última leitura.",
    "tabela": "Leituras brutas do período, do mais recente para o mais antigo. Linhas amarelas = alerta, vermelhas = crítico. Baixe em CSV para análise externa.",
}

INTRO_CONSULTA = {
    "visao_geral": "Todas as máquinas com status da última leitura, previsão do modelo de falhas e risco. Linhas amarelas = alerta, vermelhas = crítico ou risco alto. Clique na máquina abaixo para a ficha completa.",
    "previsao": "O modelo analisa as últimas 5 leituras (valores, média e variação) e estima a probabilidade de cada estado. Risco = 1 − P(normal): baixo < 20 %, moderado 20–50 %, alto > 50 %. É um sinal para priorizar inspeção, não um diagnóstico.",
    "telemetria": "Leituras da máquina no dia/horário escolhido, com as marcas × nos pontos em falha e a faixa ideal sombreada.",
    "manutencoes": "Últimas ordens de serviço registradas para esta máquina (tipo, status, categoria, serviço executado e técnico).",
}

INTRO_3D = (
    "O modelo reflete a última leitura: cor do motor = status (verde normal, amarelo alerta, vermelho crítico), "
    "velocidade de giro = RPM, tremor = vibração, brilho das aletas = temperatura."
)
