"""
Gráficos Plotly padronizados para o dashboard (tema escuro do app).

Regras seguidas: uma escala por gráfico (nunca eixo duplo), cores fixas por
variável e por máquina (ordem fixa, no máximo 8 séries coloridas; acima
disso as máquinas viram linhas neutras e a média ganha a cor da variável),
faixa normal sombreada, hover unificado.
"""
import pandas as pd
import plotly.graph_objects as go

from features.limites import LIMITES, VARIAVEIS, CORES_VARIAVEL, CORES_FALHA, NOMES_FALHA, CORES_STATUS

PALETA_MAQUINAS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
COR_NEUTRA = "rgba(160,160,170,0.35)"
TEXTO = "#e8e6df"
GRADE = "rgba(255,255,255,0.08)"

LEGENDA_TOPO = dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, font=dict(size=11))

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXTO, size=12),
    margin=dict(l=40, r=20, t=45, b=60),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0, font=dict(size=11)),
    xaxis=dict(gridcolor=GRADE, zeroline=False),
    yaxis=dict(gridcolor=GRADE, zeroline=False),
)


def cores_por_maquina(tags):
    tags = sorted(tags)
    if len(tags) <= len(PALETA_MAQUINAS):
        return {t: PALETA_MAQUINAS[i] for i, t in enumerate(tags)}
    return {t: COR_NEUTRA for t in tags}


def _faixa_normal(fig, variavel):
    lim = LIMITES[variavel]
    fig.add_hrect(y0=lim["normal"][0], y1=lim["normal"][1], fillcolor="rgba(0,131,0,0.08)",
                  line_width=0, annotation_text="faixa normal", annotation_position="top left",
                  annotation_font_size=10, annotation_font_color="rgba(200,200,200,0.7)")
    fig.add_hline(y=lim["alerta"][1], line_dash="dot", line_color="rgba(201,133,0,0.6)", line_width=1)


MAX_PONTOS_LINHA = 500


def _reduzir(d):
    """Reduz a densidade de pontos do gráfico sem mudar o formato da curva."""
    if len(d) <= MAX_PONTOS_LINHA:
        return d
    passo = max(1, len(d) // MAX_PONTOS_LINHA)
    return d.iloc[::passo]


def serie_temporal(df, variavel, titulo=None, altura=320, mostrar_media=True):
    """
    df: colunas TAG, timestamp, <variavel>. Uma linha por máquina.
    """
    fig = go.Figure()
    if df.empty:
        fig.update_layout(**LAYOUT_BASE, height=altura, title=titulo or VARIAVEIS[variavel]["rotulo"])
        return fig
    tags = sorted(df["TAG"].unique())
    cores = cores_por_maquina(tags)
    muitas = len(tags) > len(PALETA_MAQUINAS)
    unidade = VARIAVEIS[variavel]["unidade"]

    for tag in tags:
        d = _reduzir(df[df["TAG"] == tag])
        fig.add_trace(go.Scatter(
            x=d["timestamp"], y=d[variavel], mode="lines", name=tag,
            line=dict(width=1.2 if muitas else 2, color=cores[tag]),
            hovertemplate=f"{tag}: %{{y:.2f}} {unidade}<extra></extra>",
            showlegend=not muitas,
        ))
    if mostrar_media and (muitas or len(tags) > 1):
        media = _reduzir(df.groupby("timestamp")[variavel].mean().reset_index())
        fig.add_trace(go.Scatter(
            x=media["timestamp"], y=media[variavel], mode="lines",
            name=f"Média ({len(tags)} máquinas)",
            line=dict(width=2.5, color=CORES_VARIAVEL[variavel]),
            hovertemplate=f"Média: %{{y:.2f}} {unidade}<extra></extra>",
        ))
    _faixa_normal(fig, variavel)
    fig.update_layout(**LAYOUT_BASE, height=altura,
                      title=dict(text=titulo or f"{VARIAVEIS[variavel]['rotulo']} ({unidade})", font=dict(size=14)),
                      yaxis_title=unidade)
    return fig


def serie_individual(df, variavel, tag, altura=340):
    """Uma máquina, uma variável, com pontos de falha destacados."""
    fig = go.Figure()
    d = _reduzir(df[df["TAG"] == tag])
    unidade = VARIAVEIS[variavel]["unidade"]
    fig.add_trace(go.Scatter(
        x=d["timestamp"], y=d[variavel], mode="lines", name=tag,
        line=dict(width=2, color=CORES_VARIAVEL[variavel]),
        hovertemplate=f"%{{y:.2f}} {unidade}<extra></extra>",
    ))
    if "FalhaCodigo" in d.columns:
        falhas = d[d["FalhaCodigo"].fillna(0) != 0]
        for cod, grupo in falhas.groupby("FalhaCodigo"):
            fig.add_trace(go.Scatter(
                x=grupo["timestamp"], y=grupo[variavel], mode="markers",
                name=NOMES_FALHA.get(int(cod), str(cod)),
                marker=dict(size=7, color=CORES_FALHA.get(int(cod), "#e66767"), symbol="x"),
                hovertemplate=f"{NOMES_FALHA.get(int(cod), cod)}<extra></extra>",
            ))
    _faixa_normal(fig, variavel)
    fig.update_layout(**LAYOUT_BASE, height=altura,
                      title=dict(text=f"{tag} — {VARIAVEIS[variavel]['rotulo']} ({unidade})", font=dict(size=14)),
                      yaxis_title=unidade)
    return fig


def linha_do_tempo_falhas(df_falhas, altura=380):
    """Eixo x tempo, eixo y máquina, cor = tipo de falha."""
    fig = go.Figure()
    if df_falhas.empty:
        fig.update_layout(**LAYOUT_BASE, height=altura)
        return fig
    tags = sorted(df_falhas["TAG"].unique())
    for cod in sorted(df_falhas["FalhaCodigo"].unique()):
        d = df_falhas[df_falhas["FalhaCodigo"] == cod]
        fig.add_trace(go.Scatter(
            x=d["timestamp"], y=d["TAG"], mode="markers", name=NOMES_FALHA.get(int(cod), str(cod)),
            marker=dict(size=8, color=CORES_FALHA.get(int(cod), "#e66767"), symbol="square"),
            customdata=d[["Temperatura", "Vibracao", "Corrente", "RPM"]].values,
            hovertemplate="%{y} · %{x|%d/%m %H:%M}<br>T %{customdata[0]:.1f}°C · V %{customdata[1]:.2f} mm/s · "
                          "I %{customdata[2]:.1f} A · %{customdata[3]:.0f} RPM<extra></extra>",
        ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    layout["yaxis"] = dict(categoryorder="array", categoryarray=tags[::-1], gridcolor=GRADE)
    fig.update_layout(**layout, height=max(altura, 24 * len(tags) + 120),
                      title=dict(text="Linha do tempo das falhas (dia e horário)", font=dict(size=14)))
    return fig


def barras_falhas_por_maquina(df_falhas, altura=320):
    fig = go.Figure()
    if df_falhas.empty:
        fig.update_layout(**LAYOUT_BASE, height=altura)
        return fig
    tabela = df_falhas.groupby(["TAG", "FalhaCodigo"]).size().unstack(fill_value=0)
    tabela = tabela.loc[tabela.sum(axis=1).sort_values(ascending=False).index]
    for cod in tabela.columns:
        fig.add_trace(go.Bar(
            x=tabela.index, y=tabela[cod], name=NOMES_FALHA.get(int(cod), str(cod)),
            marker=dict(color=CORES_FALHA.get(int(cod), "#e66767"), line=dict(width=0)),
            hovertemplate="%{x}: %{y} leituras<extra>" + NOMES_FALHA.get(int(cod), str(cod)) + "</extra>",
        ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "x"
    layout["legend"] = LEGENDA_TOPO
    layout["margin"] = dict(l=40, r=20, t=70, b=60)
    fig.update_layout(**layout, barmode="stack", bargap=0.35, height=altura,
                      title=dict(text="Leituras em falha por máquina e tipo", font=dict(size=14), y=0.98),
                      yaxis_title="leituras")
    return fig


def barras_status(contagem, altura=220):
    """contagem: dict {Normal: n, Alerta: n, Crítico: n}."""
    ordem = ["Normal", "Alerta", "Crítico"]
    fig = go.Figure(go.Bar(
        x=ordem, y=[contagem.get(k, 0) for k in ordem],
        marker=dict(color=[CORES_STATUS[k] for k in ordem], line=dict(width=0)),
        text=[contagem.get(k, 0) for k in ordem], textposition="outside",
        hovertemplate="%{x}: %{y} máquinas<extra></extra>",
    ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "x"
    layout["margin"] = dict(l=30, r=10, t=30, b=30)
    fig.update_layout(**layout, height=altura, showlegend=False,
                      title=dict(text="Estado atual das máquinas", font=dict(size=13)))
    return fig


def barras_probabilidades(probs, altura=220):
    """probs: dict {classe_nome: p}."""
    nomes = list(probs.keys())
    cores = {"Normal": "#008300", "Desbalanceamento": "#9085e9", "Superaquecimento": "#d95926", "Falha mecânica": "#e66767"}
    fig = go.Figure(go.Bar(
        x=[probs[n] * 100 for n in nomes], y=nomes, orientation="h",
        marker=dict(color=[cores.get(n, "#888") for n in nomes], line=dict(width=0)),
        text=[f"{probs[n]*100:.0f}%" for n in nomes], textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "y"
    layout["margin"] = dict(l=10, r=40, t=30, b=20)
    layout["xaxis"] = dict(range=[0, 115], visible=False)
    fig.update_layout(**layout, height=altura, showlegend=False,
                      title=dict(text="Probabilidade por classe (modelo)", font=dict(size=13)))
    return fig


def df_de_leituras(leituras):
    if not leituras:
        return pd.DataFrame(columns=["TAG", "timestamp", "Temperatura", "Vibracao", "Corrente", "RPM", "FalhaCodigo", "Status"])
    df = pd.DataFrame(leituras)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    for c in ("Temperatura", "Vibracao", "Corrente", "RPM"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "FalhaCodigo" not in df.columns:
        df["FalhaCodigo"] = 0
    df["FalhaCodigo"] = df["FalhaCodigo"].fillna(0).astype(int)
    return df.sort_values("timestamp")


# ---------------------------------------------------------------------------
# Tipos alternativos de gráfico (Colunas / Barras / Pizza / Radar)
# ---------------------------------------------------------------------------
TIPOS_GRAFICO = ["Linha", "Colunas", "Barras", "Pizza", "Radar"]


def _status_valor(variavel, valor):
    from features.limites import status_variavel
    return status_variavel(variavel, valor)


def colunas_por_maquina(df, variavel, agregacao="max", altura=340, horizontal=False):
    """Uma coluna por máquina com o valor agregado no período, cor pelo status."""
    unidade = VARIAVEIS[variavel]["unidade"]
    serie = df.groupby("TAG")[variavel].agg(agregacao).sort_values(ascending=horizontal)
    cores = [CORES_STATUS[_status_valor(variavel, v)] for v in serie.values]
    fig = go.Figure(go.Bar(
        x=serie.values if horizontal else serie.index,
        y=serie.index if horizontal else serie.values,
        orientation="h" if horizontal else "v",
        marker=dict(color=cores, line=dict(width=0)),
        text=[f"{v:.1f}" for v in serie.values], textposition="outside",
        hovertemplate="%{y}: %{x:.2f} " + unidade + "<extra></extra>" if horizontal
        else "%{x}: %{y:.2f} " + unidade + "<extra></extra>",
    ))
    lim = LIMITES[variavel]
    if horizontal:
        fig.add_vrect(x0=lim["normal"][0], x1=lim["normal"][1], fillcolor="rgba(0,131,0,0.10)", line_width=0)
        fig.add_vline(x=lim["alerta"][1] if variavel != "RPM" else lim["alerta"][0], line_dash="dot",
                      line_color="rgba(201,133,0,0.7)")
    else:
        _faixa_normal(fig, variavel)
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    fig.update_layout(**layout, height=max(altura, 22 * len(serie) + 100) if horizontal else altura,
                      showlegend=False, bargap=0.3,
                      title=dict(text=f"{VARIAVEIS[variavel]['rotulo']} — {'máximo' if agregacao == 'max' else 'média'} por máquina ({unidade})", font=dict(size=14)),
                      **({"xaxis_title": unidade} if horizontal else {"yaxis_title": unidade}))
    return fig


def pizza_status(df, variavel, altura=340):
    """Proporção de leituras Normal / Alerta / Crítico para uma variável."""
    from features.limites import status_variavel
    status = df[variavel].apply(lambda v: status_variavel(variavel, v))
    if "FalhaCodigo" in df.columns:
        status = status.where(df["FalhaCodigo"].fillna(0) == 0, "Crítico")
    cont = status.value_counts()
    ordem = [s for s in ("Normal", "Alerta", "Crítico") if s in cont.index]
    fig = go.Figure(go.Pie(
        labels=ordem, values=[int(cont[s]) for s in ordem], hole=0.45, sort=False,
        marker=dict(colors=[CORES_STATUS[s] for s in ordem], line=dict(color="#0a0c12", width=2)),
        textinfo="label+percent", hovertemplate="%{label}: %{value} leituras (%{percent})<extra></extra>",
    ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    fig.update_layout(**layout, height=altura, showlegend=False,
                      title=dict(text=f"{VARIAVEIS[variavel]['rotulo']} — leituras por status", font=dict(size=14)))
    return fig


def radar_maquinas(df, tags=None, altura=420):
    """Radar: 4 variáveis por máquina em % do limite de alerta (100 % = no limite)."""
    tags = sorted(tags or df["TAG"].unique())[:8]
    cores = cores_por_maquina(tags)
    eixos = ["Temperatura", "Vibracao", "Corrente", "RPM"]
    rotulos = [VARIAVEIS[v]["rotulo"] for v in eixos]
    fig = go.Figure()
    for tag in tags:
        d = df[df["TAG"] == tag]
        if d.empty:
            continue
        vals = []
        for v in eixos:
            lim = LIMITES[v]
            if v == "RPM":
                # quanto menor a rotação, mais perto do limite: usa a queda em relação ao normal
                queda = max(0.0, lim["normal"][1] - float(d[v].mean()))
                vals.append(100 * queda / (lim["normal"][1] - lim["alerta"][0]))
            else:
                vals.append(100 * float(d[v].max()) / lim["alerta"][1])
        fig.add_trace(go.Scatterpolar(
            r=vals + vals[:1], theta=rotulos + rotulos[:1], fill="toself", name=tag,
            line=dict(color=cores[tag], width=2), opacity=0.75,
            hovertemplate=tag + " · %{theta}: %{r:.0f}% do limite<extra></extra>",
        ))
    fig.add_trace(go.Scatterpolar(r=[100] * 5, theta=rotulos + rotulos[:1], name="Limite de alerta",
                                  line=dict(color="rgba(201,133,0,0.9)", dash="dot", width=1.5), hoverinfo="skip"))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    fig.update_layout(**layout, height=altura,
                      polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, 140], gridcolor=GRADE, ticksuffix="%"),
                                 angularaxis=dict(gridcolor=GRADE)),
                      title=dict(text="Radar — proximidade do limite de alerta (100 % = no limite)", font=dict(size=14)))
    return fig


def grafico_variavel(df, variavel, tipo, altura=340):
    """Despacha pelo tipo escolhido pelo usuário."""
    if tipo == "Colunas":
        return colunas_por_maquina(df, variavel, altura=altura)
    if tipo == "Barras":
        return colunas_por_maquina(df, variavel, altura=altura, horizontal=True)
    if tipo == "Pizza":
        return pizza_status(df, variavel, altura=altura)
    if tipo == "Radar":
        return radar_maquinas(df, altura=altura)
    return serie_temporal(df, variavel, altura=altura)


# ---------------------------------------------------------------------------
# Falhas — com verde para operação normal
# ---------------------------------------------------------------------------
def barras_normal_vs_falhas(df, altura=340):
    """Por máquina: leituras normais (verde) empilhadas com cada tipo de falha."""
    tabela = df.groupby(["TAG", "FalhaCodigo"]).size().unstack(fill_value=0)
    if 0 not in tabela.columns:
        tabela[0] = 0
    tabela = tabela.loc[(tabela.drop(columns=0).sum(axis=1)).sort_values(ascending=False).index]
    fig = go.Figure()
    for cod in [0] + [c for c in sorted(tabela.columns) if c != 0]:
        fig.add_trace(go.Bar(
            x=tabela.index, y=tabela[cod], name=NOMES_FALHA.get(int(cod), str(cod)),
            marker=dict(color=CORES_FALHA.get(int(cod), "#e66767"), line=dict(width=0)),
            hovertemplate="%{x}: %{y} leituras<extra>" + NOMES_FALHA.get(int(cod), str(cod)) + "</extra>",
        ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "x"
    layout["legend"] = LEGENDA_TOPO
    layout["margin"] = dict(l=40, r=20, t=70, b=60)
    fig.update_layout(**layout, barmode="stack", bargap=0.35, height=altura, yaxis_title="leituras",
                      title=dict(text="Leituras por máquina: normal (verde) × tipos de falha", font=dict(size=14), y=0.98))
    return fig


def pizza_tipos_falha(df, altura=340, incluir_normal=True):
    cont = df["FalhaCodigo"].fillna(0).astype(int).value_counts()
    codigos = [c for c in (0, 1, 2, 3) if c in cont.index and (incluir_normal or c != 0)]
    fig = go.Figure(go.Pie(
        labels=[NOMES_FALHA[c] for c in codigos], values=[int(cont[c]) for c in codigos], hole=0.45, sort=False,
        marker=dict(colors=[CORES_FALHA[c] for c in codigos], line=dict(color="#0a0c12", width=2)),
        textinfo="label+percent", textposition="inside", insidetextorientation="horizontal",
        hovertemplate="%{label}: %{value} leituras (%{percent})<extra></extra>",
    ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    layout["legend"] = LEGENDA_TOPO
    fig.update_layout(**layout, height=altura, showlegend=True,
                      title=dict(text="Proporção normal × tipos de falha" if incluir_normal else "Proporção dos tipos de falha", font=dict(size=14)))
    return fig


def barras_ranking(serie, titulo, altura=300, cor="#e66767", unidade="leituras em falha"):
    """Ranking horizontal (ex.: máquinas com mais falhas)."""
    serie = serie.sort_values(ascending=True)
    fig = go.Figure(go.Bar(
        x=serie.values, y=serie.index, orientation="h",
        marker=dict(color=cor, line=dict(width=0)), text=serie.values, textposition="outside",
        hovertemplate="%{y}: %{x} " + unidade + "<extra></extra>",
    ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    fig.update_layout(**layout, height=max(altura, 24 * len(serie) + 90), showlegend=False,
                      title=dict(text=titulo, font=dict(size=14)), xaxis_title=unidade)
    return fig


def falhas_por_hora(df, altura=300):
    """Leituras em falha por hora do dia (todas as máquinas), cor por tipo."""
    f = df[df["FalhaCodigo"] != 0].copy()
    fig = go.Figure()
    if f.empty:
        fig.update_layout(**LAYOUT_BASE, height=altura)
        return fig
    f["hora"] = f["timestamp"].dt.hour
    tab = f.groupby(["hora", "FalhaCodigo"]).size().unstack(fill_value=0).reindex(range(24), fill_value=0)
    for cod in tab.columns:
        fig.add_trace(go.Bar(x=[f"{h:02d}h" for h in tab.index], y=tab[cod], name=NOMES_FALHA.get(int(cod)),
                             marker=dict(color=CORES_FALHA.get(int(cod)), line=dict(width=0)),
                             hovertemplate="%{x}: %{y}<extra>" + NOMES_FALHA.get(int(cod)) + "</extra>"))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "x"
    layout["legend"] = LEGENDA_TOPO
    layout["margin"] = dict(l=40, r=20, t=70, b=60)
    fig.update_layout(**layout, barmode="stack", height=altura, bargap=0.2, yaxis_title="leituras em falha",
                      title=dict(text="Falhas por horário do dia", font=dict(size=14), y=0.98))
    return fig


# ---------------------------------------------------------------------------
# Manutenções — gráficos com legenda e rótulos de eixo
# ---------------------------------------------------------------------------
CORES_TIPO_OS = {
    "Preventiva": "#199e70",
    "Preditiva": "#3987e5",
    "Corretiva": "#e66767",
    "Inspeção": "#9085e9",
    "Melhoria": "#c98500",
}


def _cor_tipo(nome, i=0):
    return CORES_TIPO_OS.get(nome, PALETA_MAQUINAS[i % len(PALETA_MAQUINAS)])


def manutencoes_por_mes(tabela, altura=360):
    """Barras empilhadas por mês, uma cor por tipo de manutenção, com legenda."""
    def _mes_br(m):
        t = str(m)
        return f"{t[5:7]}/{t[:4]}" if len(t) >= 7 and t[4] == "-" else t

    rotulos = [_mes_br(m) for m in tabela.index]
    fig = go.Figure()
    for i, tipo in enumerate(tabela.columns):
        fig.add_trace(go.Bar(
            x=rotulos, y=tabela[tipo], name=str(tipo),
            marker=dict(color=_cor_tipo(str(tipo), i), line=dict(width=0)),
            hovertemplate="%{x} · " + str(tipo) + ": %{y} OS<extra></extra>",
        ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "x unified"
    layout["legend"] = dict(title="Tipo de manutenção", orientation="h",
                            yanchor="top", y=-0.22, xanchor="center", x=0.5, font=dict(size=11))
    layout["xaxis"] = dict(LAYOUT_BASE["xaxis"], title="Mês", type="category")
    layout["yaxis"] = dict(LAYOUT_BASE["yaxis"], title="Ordens de serviço")
    layout["margin"] = dict(t=54, b=90, l=60, r=20)
    fig.update_layout(**layout, barmode="stack", height=altura + 40, bargap=0.4,
                      title=dict(text="Manutenções por mês e por tipo", font=dict(size=14)))
    return fig


def barras_rotuladas(serie, titulo, eixo_x, eixo_y, cores=None, altura=340, horizontal=False,
                     nome_legenda=None):
    """Barra simples com título, rótulos de eixo, valores nas barras e legenda."""
    valores = [float(v) for v in serie.values]
    rotulos = [str(i) for i in serie.index]
    cor = cores or [PALETA_MAQUINAS[i % len(PALETA_MAQUINAS)] for i in range(len(valores))]
    texto = [f"{v:g}" for v in valores]
    if horizontal:
        traco = go.Bar(x=valores, y=rotulos, orientation="h", marker=dict(color=cor, line=dict(width=0)),
                       text=texto, textposition="outside", name=nome_legenda or titulo,
                       hovertemplate="%{y}: %{x:g}<extra></extra>")
    else:
        traco = go.Bar(x=rotulos, y=valores, marker=dict(color=cor, line=dict(width=0)),
                       text=texto, textposition="outside", name=nome_legenda or titulo,
                       hovertemplate="%{x}: %{y:g}<extra></extra>")
    fig = go.Figure(traco)
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    layout["legend"] = dict(orientation="h", yanchor="top", y=-0.28, xanchor="center", x=0.5,
                            font=dict(size=11))
    if horizontal:
        layout["xaxis"] = dict(LAYOUT_BASE["xaxis"], title=eixo_y)
        layout["yaxis"] = dict(LAYOUT_BASE["yaxis"], title=eixo_x, type="category")
    else:
        layout["xaxis"] = dict(LAYOUT_BASE["xaxis"], title=eixo_x, type="category")
        layout["yaxis"] = dict(LAYOUT_BASE["yaxis"], title=eixo_y)
    layout["margin"] = dict(t=54, b=110, l=64, r=20)
    fig.update_layout(**layout, height=altura + 30, bargap=0.3, showlegend=bool(nome_legenda),
                      title=dict(text=titulo, font=dict(size=14)))
    return fig


def pizza_tipos_os(serie, altura=340):
    """Distribuição das OS por tipo, com legenda nomeada."""
    nomes = [str(i) for i in serie.index]
    fig = go.Figure(go.Pie(
        labels=nomes, values=[int(v) for v in serie.values], hole=0.45, sort=False,
        marker=dict(colors=[_cor_tipo(n, i) for i, n in enumerate(nomes)],
                    line=dict(color="#0a0c12", width=2)),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} OS (%{percent})<extra></extra>",
    ))
    layout = dict(LAYOUT_BASE)
    layout["hovermode"] = "closest"
    layout["legend"] = dict(title="Tipo de manutenção", orientation="h",
                            yanchor="top", y=-0.05, xanchor="center", x=0.5, font=dict(size=11))
    layout["margin"] = dict(t=54, b=70, l=20, r=20)
    fig.update_layout(**layout, height=altura + 30, showlegend=True,
                      title=dict(text="Participação de cada tipo de manutenção", font=dict(size=14)))
    return fig
