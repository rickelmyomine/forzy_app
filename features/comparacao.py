"""
Comparação de máquinas: gráficos e tabela lado a lado das leituras de duas
ou mais máquinas no mesmo período.
"""
import pandas as pd
import plotly.graph_objects as go

from features.graficos import LAYOUT_BASE, PALETA_MAQUINAS, GRADE, _faixa_normal, _reduzir
from features.limites import VARIAVEIS, LIMITES, NOMES_FALHA, CORES_STATUS, status_variavel


def cores(tags):
    return {t: PALETA_MAQUINAS[i % len(PALETA_MAQUINAS)] for i, t in enumerate(sorted(tags))}


def comparar_series(df, variavel, tags, altura=340):
    """Uma linha por máquina, mesma escala — comparação direta."""
    unidade = VARIAVEIS[variavel]["unidade"]
    cor = cores(tags)
    fig = go.Figure()
    for tag in sorted(tags):
        bruto = df[df["TAG"] == tag]
        if bruto.empty:
            continue
        d = _reduzir(bruto)
        fig.add_trace(go.Scatter(x=d["timestamp"], y=d[variavel], mode="lines", name=tag,
                                 line=dict(width=2, color=cor[tag]),
                                 hovertemplate=f"{tag}: %{{y:.2f}} {unidade}<extra></extra>"))
        falhas = bruto[bruto["FalhaCodigo"].fillna(0) != 0]
        if not falhas.empty:
            fig.add_trace(go.Scatter(x=falhas["timestamp"], y=falhas[variavel], mode="markers",
                                     name=f"{tag} · falha", marker=dict(size=6, color=cor[tag], symbol="x"),
                                     showlegend=False, hovertemplate=f"{tag}: falha<extra></extra>"))
    _faixa_normal(fig, variavel)
    fig.update_layout(**LAYOUT_BASE, height=altura, yaxis_title=unidade,
                      title=dict(text=f"{VARIAVEIS[variavel]['rotulo']} ({unidade}) — comparação", font=dict(size=14)))
    return fig


def barras_comparacao(resumo, variavel, agregacao="Máximo", altura=300, horizontal=False):
    """Barra por máquina com o valor agregado, colorida pelo status."""
    unidade = VARIAVEIS[variavel]["unidade"]
    rotulo = VARIAVEIS[variavel]["rotulo"]
    coluna = f"{rotulo} {agregacao.lower()}"
    if coluna not in resumo.columns:
        return go.Figure()
    serie = resumo.set_index("Máquina")[coluna]
    cor = [CORES_STATUS[status_variavel(variavel, v)] for v in serie.values]
    rotulos = [f"{v:.1f}" for v in serie.values]
    if horizontal:
        fig = go.Figure(go.Bar(x=serie.values, y=serie.index, orientation="h",
                               marker=dict(color=cor, line=dict(width=0)),
                               text=rotulos, textposition="outside",
                               hovertemplate="%{y}: %{x:.2f} " + unidade + "<extra></extra>"))
    else:
        fig = go.Figure(go.Bar(x=serie.index, y=serie.values, marker=dict(color=cor, line=dict(width=0)),
                               text=rotulos, textposition="outside",
                               hovertemplate="%{x}: %{y:.2f} " + unidade + "<extra></extra>"))
        _faixa_normal(fig, variavel)
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    eixo = {"xaxis_title": unidade} if horizontal else {"yaxis_title": unidade}
    fig.update_layout(**layout, height=altura, showlegend=False, bargap=0.35, **eixo,
                      title=dict(text=f"{rotulo} — {agregacao.lower()} no período", font=dict(size=14)))
    return fig


def pizza_comparacao(df, variavel, tags, altura=300):
    """Uma rosca por máquina: proporção de leituras Normal / Alerta / Crítico."""
    from plotly.subplots import make_subplots
    tags = sorted(tags)
    fig = make_subplots(rows=1, cols=len(tags), specs=[[{"type": "domain"}] * len(tags)],
                        subplot_titles=tags)
    for i, tag in enumerate(tags, start=1):
        d = df[df["TAG"] == tag]
        if d.empty:
            continue
        status = d[variavel].apply(lambda v: status_variavel(variavel, v))
        if "FalhaCodigo" in d.columns:
            status = status.where(d["FalhaCodigo"].fillna(0) == 0, "Crítico")
        cont = status.value_counts()
        ordem = [s for s in ("Normal", "Alerta", "Crítico") if s in cont.index]
        fig.add_trace(go.Pie(labels=ordem, values=[int(cont[s]) for s in ordem], hole=0.45, sort=False,
                             marker=dict(colors=[CORES_STATUS[s] for s in ordem],
                                         line=dict(color="#0a0c12", width=2)),
                             textinfo="percent", name=tag,
                             hovertemplate="%{label}: %{value} leituras (%{percent})<extra>" + tag + "</extra>"),
                      row=1, col=i)
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    fig.update_layout(**layout, height=altura, showlegend=True,
                      title=dict(text=f"{VARIAVEIS[variavel]['rotulo']} — leituras por status em cada máquina",
                                 font=dict(size=14)))
    return fig


def grafico_comparacao(df, variavel, tipo, tags, resumo=None, altura=320):
    """Mesmos tipos de gráfico dos Dados Brutos, aplicados à comparação."""
    if tipo == "Colunas":
        return barras_comparacao(resumo, variavel, altura=altura)
    if tipo == "Barras":
        return barras_comparacao(resumo, variavel, altura=altura, horizontal=True)
    if tipo == "Pizza":
        return pizza_comparacao(df, variavel, tags, altura=altura)
    if tipo == "Radar":
        return radar_comparacao(df, tags, altura=altura)
    return comparar_series(df, variavel, tags, altura=altura)


def radar_comparacao(df, tags, altura=400):
    """Radar das 4 variáveis em % do limite de alerta (100 % = no limite)."""
    eixos = ["Temperatura", "Vibracao", "Corrente", "RPM"]
    rotulos = [VARIAVEIS[v]["rotulo"] for v in eixos]
    cor = cores(tags)
    fig = go.Figure()
    for tag in sorted(tags):
        d = df[df["TAG"] == tag]
        if d.empty:
            continue
        vals = []
        for v in eixos:
            lim = LIMITES[v]
            if v == "RPM":
                queda = max(0.0, lim["normal"][1] - float(d[v].mean()))
                vals.append(100 * queda / (lim["normal"][1] - lim["alerta"][0]))
            else:
                vals.append(100 * float(d[v].max()) / lim["alerta"][1])
        fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=rotulos + rotulos[:1], fill="toself",
                                      name=tag, line=dict(color=cor[tag], width=2), opacity=0.7,
                                      hovertemplate=tag + " · %{theta}: %{r:.0f}% do limite<extra></extra>"))
    fig.add_trace(go.Scatterpolar(r=[100] * 5, theta=rotulos + rotulos[:1], name="Limite de alerta",
                                  line=dict(color="rgba(201,133,0,0.9)", dash="dot", width=1.5), hoverinfo="skip"))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    fig.update_layout(**layout, height=altura,
                      polar=dict(bgcolor="rgba(0,0,0,0)",
                                 radialaxis=dict(range=[0, 140], gridcolor=GRADE, ticksuffix="%"),
                                 angularaxis=dict(gridcolor=GRADE)),
                      title=dict(text="Radar comparativo — proximidade do limite de alerta", font=dict(size=14)))
    return fig


def barras_falhas_comparacao(df, tags, altura=300):
    fig = go.Figure()
    from features.limites import CORES_FALHA
    tabela = df.groupby(["TAG", "FalhaCodigo"]).size().unstack(fill_value=0)
    for cod in sorted(tabela.columns):
        fig.add_trace(go.Bar(x=tabela.index, y=tabela[cod], name=NOMES_FALHA.get(int(cod), str(cod)),
                             marker=dict(color=CORES_FALHA.get(int(cod), "#e66767"), line=dict(width=0)),
                             hovertemplate="%{x}: %{y} leituras<extra>" + NOMES_FALHA.get(int(cod), str(cod)) + "</extra>"))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "x"
    fig.update_layout(**layout, barmode="stack", height=altura, bargap=0.35, yaxis_title="leituras",
                      title=dict(text="Normal × falhas por máquina no período", font=dict(size=14)))
    return fig


def tabela_comparacao(df, tags):
    """Resumo estatístico por máquina, uma linha por máquina."""
    linhas = []
    for tag in sorted(tags):
        d = df[df["TAG"] == tag]
        if d.empty:
            continue
        n = len(d)
        falhas = int((d["FalhaCodigo"] != 0).sum())
        linha = {"Máquina": tag, "Leituras": n}
        for v in ("Temperatura", "Vibracao", "Corrente", "RPM"):
            rot = VARIAVEIS[v]["rotulo"]
            linha[f"{rot} média"] = round(float(d[v].mean()), 2)
            linha[f"{rot} máximo"] = round(float(d[v].max()), 2)
            linha[f"{rot} mínimo"] = round(float(d[v].min()), 2)
        linha["Leituras em falha"] = falhas
        linha["% em falha"] = round(100 * falhas / n, 1) if n else 0.0
        pior = "Normal"
        ordem = {"Normal": 0, "Alerta": 1, "Crítico": 2}
        for v in ("Temperatura", "Vibracao", "Corrente", "RPM"):
            valor = float(d[v].min() if v == "RPM" else d[v].max())
            s = status_variavel(v, valor)
            if ordem[s] > ordem[pior]:
                pior = s
        linha["Status"] = "Crítico" if falhas else pior
        linhas.append(linha)
    return pd.DataFrame(linhas)


def texto_comparacao(resumo):
    """Frase com a leitura do comparativo (quem está pior em cada variável)."""
    if resumo is None or resumo.empty or len(resumo) < 2:
        return ""
    partes = []
    for v, coluna, sentido in (("Temperatura", "Temperatura máximo", "mais quente"),
                               ("Vibracao", "Vibração máximo", "que mais vibra"),
                               ("Corrente", "Corrente máximo", "de maior corrente"),
                               ("RPM", "Rotação mínimo", "de menor rotação")):
        if coluna not in resumo.columns:
            continue
        if v == "RPM":
            linha = resumo.loc[resumo[coluna].idxmin()]
        else:
            linha = resumo.loc[resumo[coluna].idxmax()]
        partes.append(f"**{linha['Máquina']}** é a {sentido} ({linha[coluna]} {VARIAVEIS[v]['unidade']})")
    pior_falha = resumo.loc[resumo["Leituras em falha"].idxmax()]
    if pior_falha["Leituras em falha"]:
        partes.append(f"**{pior_falha['Máquina']}** teve mais leituras em falha ({int(pior_falha['Leituras em falha'])})")
    return "No período comparado: " + "; ".join(partes) + "."
