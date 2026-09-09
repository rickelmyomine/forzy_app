"""
Dados Brutos (Telemetria) — tela principal.

Dashboards da telemetria de todas as máquinas: dia, faixa de horário
(00:00–23:59), máquinas, variável e TIPO de gráfico (linha, colunas, barras,
pizza, radar). Tabelas com alerta em amarelo e crítico em vermelho, textos
explicativos com a faixa ideal de cada variável, atalho para as máquinas
críticas, dashboard de falhas por motor e ranking dia/semana/mês/ano.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from features.estilos import colorir_por_status, colorir_por_falha, abas
from features.graficos import (
    serie_temporal, serie_individual, linha_do_tempo_falhas, barras_status, df_de_leituras,
    grafico_variavel, radar_maquinas, barras_normal_vs_falhas, pizza_tipos_falha, barras_ranking,
    falhas_por_hora, TIPOS_GRAFICO,
)
from features.comparacao import (
    comparar_series, barras_comparacao, radar_comparacao, barras_falhas_comparacao,
    tabela_comparacao, texto_comparacao, grafico_comparacao, pizza_comparacao,
)
from features.limites import VARIAVEIS, NOMES_FALHA, classificar_status
from features.textos import INTRO, INTRO_TIPO_GRAFICO, intro_variavel
from features.exportar import bloco_exportar
from providers.db_mongo import TelemetriaRepository, EquipamentoRepository, MongoIndisponivelError

FUSO = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")
OPCAO_TODAS = "Todas (unificado)"


@st.cache_data(ttl=180, show_spinner=False, max_entries=40)
def _carregar(inicio_utc, fim_utc, tags):
    return TelemetriaRepository.obter_intervalo(inicio_utc, fim_utc, tags=tags)


@st.cache_data(ttl=600, show_spinner=False)
def _periodo_disponivel():
    return TelemetriaRepository.periodo_disponivel()


@st.cache_data(ttl=600, show_spinner=False, max_entries=40)
def _resumo(inicio_utc, fim_utc, tags):
    return TelemetriaRepository.resumo_intervalo(inicio_utc, fim_utc, tags)


def _para_utc(dia, hora):
    return datetime.combine(dia, hora).replace(tzinfo=FUSO).astimezone(UTC).replace(tzinfo=None)


def _tags_da_planta():
    tags = TelemetriaRepository.obter_tags_disponiveis()
    planta = st.session_state.get("planta_selecionada")
    if planta and planta != "Todas as plantas":
        try:
            cad = {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}
            filtradas = [t for t in tags if cad.get(t, {}).get("Planta") in (planta, None)]
            if filtradas:
                tags = filtradas
        except MongoIndisponivelError:
            pass
    return tags


def _status_ultimas(ultimas):
    out = []
    for _, l in ultimas.iterrows():
        s, ic = classificar_status(l.get("Temperatura"), l.get("Vibracao"), l.get("Corrente"), l.get("RPM"),
                                   int(l.get("FalhaCodigo", 0)))
        out.append((l["TAG"], s, ic))
    return out


# ---------------------------------------------------------------------------
def _filtros():
    ini_disp, fim_disp = _periodo_disponivel()
    if fim_disp is None:
        st.warning("Sem histórico de telemetria no MongoDB. Aguarde a preparação automática (barra lateral).")
        return None
    fim_local = pd.Timestamp(fim_disp, tz="UTC").tz_convert(FUSO)
    ini_local = pd.Timestamp(ini_disp, tz="UTC").tz_convert(FUSO)
    tags_disp = _tags_da_planta()

    # Atalho "máquinas críticas" aplicado antes de desenhar o multiselect
    if st.session_state.pop("db_aplicar_criticas", None):
        crit = st.session_state.get("db_tags_criticas") or []
        st.session_state["db_tags"] = [t for t in crit if t in tags_disp] or tags_disp
        st.session_state["db_uma"] = "Todas as máquinas"
    if st.session_state.pop("db_aplicar_todas", None):
        st.session_state["db_tags"] = tags_disp
        st.session_state["db_uma"] = "Todas as máquinas"

    c1, c2, c3, c4, c5 = st.columns([1.0, 1.5, 1.3, 1.2, 1.1])
    dia = c1.date_input("Dia", value=fim_local.date(), min_value=ini_local.date(),
                        max_value=fim_local.date(), key="db_dia")
    faixa = c2.slider("Horário", value=(time(0, 0), time(23, 59)), format="HH:mm", key="db_hora",
                      step=timedelta(minutes=10))
    # Seleção de UMA máquina (ou todas); o multiselect abaixo serve para subconjuntos
    opcao_uma = c3.selectbox("Máquina", ["Todas as máquinas"] + tags_disp, key="db_uma",
                             help="Escolha uma máquina para ver só as leituras dela, ou 'Todas as máquinas'.")
    variavel = c4.selectbox("Variável", [OPCAO_TODAS] + [VARIAVEIS[v]["rotulo"] for v in VARIAVEIS], key="db_var")
    tipo = c5.selectbox("Tipo de gráfico", TIPOS_GRAFICO, key="db_tipo")
    if opcao_uma != "Todas as máquinas":
        tags = [opcao_uma]
    else:
        with st.expander("Selecionar um grupo de máquinas (opcional)"):
            tags = st.multiselect("Máquinas do grupo", tags_disp, default=tags_disp, key="db_tags",
                                  placeholder="Selecione as máquinas")

    ini, fim = _para_utc(dia, faixa[0]), _para_utc(dia, faixa[1])
    var_chave = next((k for k, v in VARIAVEIS.items() if v["rotulo"] == variavel), None)
    st.caption(f"Histórico disponível: {ini_local:%d/%m/%Y} a {fim_local:%d/%m/%Y %H:%M}. "
               f"Selecionado: {dia:%d/%m/%Y} {faixa[0]:%H:%M}–{faixa[1]:%H:%M}, {len(tags)} máquina(s). "
               f"{INTRO_TIPO_GRAFICO[tipo]}")
    return dia, ini, fim, tuple(sorted(tags)), var_chave, tipo, tags_disp


def _kpis(df, tags_disp):
    ultimas = df.sort_values("timestamp").groupby("TAG").tail(1)
    contagem = {"Normal": 0, "Alerta": 0, "Crítico": 0}
    criticas, alertas = [], []
    for tag, s, _ in _status_ultimas(ultimas):
        contagem[s] += 1
        if s == "Crítico":
            criticas.append(tag)
        elif s == "Alerta":
            alertas.append(tag)
    st.session_state["db_tags_criticas"] = criticas

    falhas = int((df["FalhaCodigo"] != 0).sum())
    k = st.columns([1, 1, 1, 1.3, 2])
    k[0].metric("Leituras", f"{len(df):,}".replace(",", "."))
    k[1].metric("Máquinas", df["TAG"].nunique())
    k[2].metric("Leituras em falha", falhas)
    with k[3]:
        st.metric("Máquinas críticas agora", contagem["Crítico"])
        if criticas:
            if st.button(f"🔴 Ver só as críticas ({', '.join(criticas)})", key="btn_crit", use_container_width=True):
                st.session_state["db_aplicar_criticas"] = True
                st.rerun()
        if len(st.session_state.get("db_tags", tags_disp)) < len(tags_disp) or st.session_state.get("db_uma", "Todas as máquinas") != "Todas as máquinas":
            if st.button("↩️ Voltar para todas as máquinas", key="btn_todas", use_container_width=True):
                st.session_state["db_aplicar_todas"] = True
                st.rerun()
    with k[4]:
        st.plotly_chart(barras_status(contagem, altura=200), use_container_width=True, config={"displayModeBar": False})
    st.caption(INTRO["kpis"] + " " + INTRO["criticas"])
    return ultimas, criticas, alertas


def _estado_atual(ultimas, criticas, alertas):
    titulo = "📋 Última leitura de cada máquina no período"
    if criticas or alertas:
        titulo += f" — 🔴 {len(criticas)} crítica(s), 🟡 {len(alertas)} em alerta"
    with st.expander(titulo, expanded=bool(criticas)):
        linhas = []
        for _, l in ultimas.sort_values("TAG").iterrows():
            s, ic = classificar_status(l.get("Temperatura"), l.get("Vibracao"), l.get("Corrente"), l.get("RPM"), int(l.get("FalhaCodigo", 0)))
            linhas.append({
                "Máquina": l["TAG"], "Status": f"{ic} {s}", "Horário": l["timestamp"].strftime("%d/%m %H:%M"),
                "Temperatura (°C)": round(l["Temperatura"], 1), "Vibração (mm/s)": round(l["Vibracao"], 2),
                "Corrente (A)": round(l["Corrente"], 1), "Rotação (RPM)": round(l["RPM"], 0),
                "Falha": NOMES_FALHA.get(int(l.get("FalhaCodigo", 0)), "-") if int(l.get("FalhaCodigo", 0)) else "-",
            })
        st.dataframe(colorir_por_status(pd.DataFrame(linhas)), use_container_width=True, hide_index=True)
        st.caption(INTRO["estado_atual"])


# ---------------------------------------------------------------------------
def _dashboard_unificado(df, tipo):
    st.subheader("Telemetria unificada")
    if tipo == "Radar":
        st.plotly_chart(radar_maquinas(df), use_container_width=True)
        st.caption(INTRO_TIPO_GRAFICO["Radar"] + " Máquinas mostradas: até 8 (as primeiras da seleção).")
        for v in VARIAVEIS:
            st.caption(intro_variavel(v))
        return
    pares = [("Temperatura", "Vibracao"), ("Corrente", "RPM")]
    for a, b in pares:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(grafico_variavel(df, a, tipo), use_container_width=True)
            st.caption(intro_variavel(a))
        with c2:
            st.plotly_chart(grafico_variavel(df, b, tipo), use_container_width=True)
            st.caption(intro_variavel(b))
    st.caption(INTRO["unificado"])


def _dashboard_individual(df, variavel, tipo):
    rotulo, unidade = VARIAVEIS[variavel]["rotulo"], VARIAVEIS[variavel]["unidade"]
    st.subheader(f"{rotulo} ({unidade})")
    st.plotly_chart(grafico_variavel(df, variavel, tipo, altura=400), use_container_width=True)
    st.caption(intro_variavel(variavel))

    est = df.groupby("TAG")[variavel].agg(["mean", "min", "max"]).round(2)
    est.columns = ["Média", "Mínimo", "Máximo"]
    est["Leituras em falha"] = df[df["FalhaCodigo"] != 0].groupby("TAG").size().reindex(est.index).fillna(0).astype(int)
    from features.limites import status_variavel
    est["Status (pior)"] = [status_variavel(variavel, v) for v in est["Máximo" if variavel != "RPM" else "Mínimo"]]
    est = est.sort_values("Máximo", ascending=(variavel == "RPM")).reset_index().rename(columns={"TAG": "Máquina"})

    c1, c2 = st.columns([1.2, 1])
    with c1:
        tag_sel = st.selectbox("Ver uma máquina isoladamente", ["(nenhuma)"] + sorted(df["TAG"].unique()), key="db_tag_ind")
        if tag_sel != "(nenhuma)":
            st.plotly_chart(serie_individual(df, variavel, tag_sel), use_container_width=True)
            st.caption(INTRO["individual"])
    with c2:
        st.markdown(f"**Resumo por máquina — {rotulo}**")
        st.dataframe(colorir_por_status(est, "Status (pior)"), use_container_width=True, hide_index=True, height=380)
        st.caption(INTRO["resumo_maquina"])


# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False, max_entries=20)
def _falhas_diarias(inicio_utc, fim_utc, tags):
    return TelemetriaRepository.falhas_por_dia(inicio_utc, fim_utc, tags)


def _ranking_periodos(dia, tags):
    """Máquina com mais leituras em falha no dia, semana, mês e ano.

    Uma única agregação (falhas por máquina e por dia) alimenta os quatro
    períodos — antes eram quatro consultas, a maior varrendo um ano inteiro.
    """
    st.subheader("🏆 Máquina com mais falhas por período")
    d0_ano = dia - timedelta(days=364)
    registros = _falhas_diarias(_para_utc(d0_ano, time(0, 0)), _para_utc(dia, time(23, 59)), tags)
    base = pd.DataFrame(registros)
    periodos = {
        "Dia": (dia, dia),
        "Semana": (dia - timedelta(days=6), dia),
        "Mês": (dia - timedelta(days=29), dia),
        "Ano": (d0_ano, dia),
    }
    cols = st.columns(4)
    series = {}
    for (nome, (d0, d1)), col in zip(periodos.items(), cols):
        if base.empty:
            serie = pd.Series(dtype=int)
        else:
            recorte = base[(base["dia"] >= d0.strftime("%Y-%m-%d")) & (base["dia"] <= d1.strftime("%Y-%m-%d"))]
            serie = recorte.groupby("TAG")["falhas"].sum().astype(int) if not recorte.empty else pd.Series(dtype=int)
        series[nome] = serie
        if serie.empty:
            col.metric(f"{nome}", "—", "sem falhas")
        else:
            top = serie.idxmax()
            col.metric(f"{nome} ({d0:%d/%m}–{d1:%d/%m})", top, f"{int(serie[top])} leituras em falha")
    st.caption(INTRO["ranking"])
    c1, c2 = st.columns(2)
    for (nome, serie), col in zip(list(series.items())[1:3], (c1, c2)):
        if not serie.empty:
            col.plotly_chart(barras_ranking(serie.sort_values(ascending=False).head(10), f"Top 10 — {nome}"),
                             use_container_width=True)
    st.caption("Ranking das 10 máquinas com mais leituras em falha na semana e no mês. "
               "Máquinas que aparecem nos dois rankings têm problema recorrente.")


def _dashboard_falhas(df, dia, tags, tipo):
    tags_falha = ["Todas as máquinas"] + sorted(df["TAG"].unique())
    c1, c2 = st.columns([1.5, 3])
    tag_f = c1.selectbox("Motor", tags_falha, key="db_falha_tag")
    df_f = df if tag_f == "Todas as máquinas" else df[df["TAG"] == tag_f]
    falhas = df_f[df_f["FalhaCodigo"] != 0].copy()

    por_tipo = falhas["FalhaCodigo"].value_counts()
    k = st.columns(5)
    k[0].metric("Normal 🟢", int((df_f["FalhaCodigo"] == 0).sum()))
    for i, cod in enumerate((1, 2, 3)):
        k[i + 1].metric(NOMES_FALHA[cod], int(por_tipo.get(cod, 0)))
    k[4].metric("Máquinas afetadas", falhas["TAG"].nunique())
    st.caption(INTRO["falhas_kpis"])

    if falhas.empty:
        st.success(f"🟢 Nenhuma leitura com falha no período selecionado ({tag_f}). Operação normal.")
    else:
        g1, g2 = st.columns([1.6, 1])
        with g1:
            if tag_f == "Todas as máquinas":
                st.plotly_chart(linha_do_tempo_falhas(falhas), use_container_width=True)
                st.caption(INTRO["falhas_timeline"])
            else:
                st.plotly_chart(serie_individual(df_f, "Temperatura", tag_f, altura=300), use_container_width=True)
                st.plotly_chart(serie_individual(df_f, "Vibracao", tag_f, altura=300), use_container_width=True)
                st.caption(INTRO["individual"])
        with g2:
            st.plotly_chart(pizza_tipos_falha(df_f), use_container_width=True)
            st.caption(INTRO["falhas_pizza"])
        g3, g4 = st.columns(2)
        with g3:
            st.plotly_chart(barras_normal_vs_falhas(df_f), use_container_width=True)
            st.caption(INTRO["falhas_barras"])
        with g4:
            st.plotly_chart(falhas_por_hora(df_f), use_container_width=True)
            st.caption("Em que horário do dia as falhas se concentram. Picos em horários de maior carga sugerem sobrecarga; picos na partida sugerem problema mecânico transitório.")

        # Episódios
        falhas = falhas.sort_values(["TAG", "timestamp"])
        falhas["gap"] = falhas.groupby("TAG")["timestamp"].diff().dt.total_seconds().div(60).fillna(0)
        falhas["novo"] = (falhas["gap"] > 30) | (falhas.groupby("TAG")["FalhaCodigo"].shift() != falhas["FalhaCodigo"])
        falhas["episodio"] = falhas.groupby("TAG")["novo"].cumsum()
        ep = falhas.groupby(["TAG", "episodio"]).agg(
            Tipo=("FalhaCodigo", "first"), Início=("timestamp", "min"), Fim=("timestamp", "max"),
            Leituras=("timestamp", "size"), **{"Temp. máx (°C)": ("Temperatura", "max"),
                                                "Vib. máx (mm/s)": ("Vibracao", "max"),
                                                "Corrente máx (A)": ("Corrente", "max"),
                                                "RPM mín": ("RPM", "min")}).reset_index()
        ep["Status"] = "Crítico"
        ep["Tipo"] = ep["Tipo"].map(NOMES_FALHA)
        ep["Dia"] = ep["Início"].dt.strftime("%d/%m/%Y")
        ep["Horário"] = ep["Início"].dt.strftime("%H:%M") + " – " + ep["Fim"].dt.strftime("%H:%M")
        ep = ep.sort_values("Início", ascending=False)
        st.markdown(f"**Episódios de falha ({len(ep)})**")
        st.dataframe(colorir_por_status(ep[["TAG", "Status", "Tipo", "Dia", "Horário", "Leituras", "Temp. máx (°C)",
                                            "Vib. máx (mm/s)", "Corrente máx (A)", "RPM mín"]].round(2)),
                     use_container_width=True, hide_index=True)
        st.caption(INTRO["falhas_episodios"])

    st.divider()
    _ranking_periodos(dia, tags if tag_f == "Todas as máquinas" else (tag_f,))


def _tabela(df, ini):
    t = df[["TAG", "timestamp", "Temperatura", "Vibracao", "Corrente", "RPM", "FalhaCodigo", "Status"]].copy()
    t["Status"] = [classificar_status(r.Temperatura, r.Vibracao, r.Corrente, r.RPM, int(r.FalhaCodigo))[0] for r in t.itertuples()]
    t["Falha"] = t["FalhaCodigo"].map(NOMES_FALHA)
    t = t.sort_values("timestamp", ascending=False).drop(columns=["FalhaCodigo"])
    t = t.rename(columns={"TAG": "Máquina", "timestamp": "Horário", "Vibracao": "Vibração"})
    st.dataframe(colorir_por_status(t.head(2000)), use_container_width=True, hide_index=True, height=420)
    st.caption(INTRO["tabela"] + (" (mostrando as 2.000 mais recentes)" if len(t) > 2000 else ""))
    st.download_button("⬇️ Baixar CSV do período", t.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"telemetria_{ini:%Y%m%d}.csv", mime="text/csv")


def _aba_comparar(dia, ini, fim, tags_disp):
    st.subheader("⚖️ Comparar duas máquinas")
    st.caption("Escolha duas máquinas para ver as leituras lado a lado, na mesma escala e no mesmo "
               "dia/horário selecionados acima. Útil para saber se um problema é da máquina ou do processo.")
    c1, c2, c3 = st.columns([1, 1, 1.2])
    tag_a = c1.selectbox("Máquina A", tags_disp, index=0, key="cmp_a")
    idx_b = 1 if len(tags_disp) > 1 else 0
    tag_b = c2.selectbox("Máquina B", tags_disp, index=idx_b, key="cmp_b")
    tipo = c3.selectbox("Tipo de gráfico", TIPOS_GRAFICO, key="cmp_tipo")
    if tag_a == tag_b:
        st.info("Escolha duas máquinas diferentes para comparar.")
        return
    par = tuple(sorted({tag_a, tag_b}))
    df = df_de_leituras(_carregar(ini, fim, par))
    if df.empty:
        st.info("Sem leituras no período para essas máquinas.")
        return

    resumo = tabela_comparacao(df, par)
    st.markdown(texto_comparacao(resumo))
    st.dataframe(colorir_por_status(resumo), use_container_width=True, hide_index=True)
    st.caption("Média, máximo e mínimo de cada variável no período, com o total de leituras em falha. "
               "Linha amarela = alerta, vermelha = crítico.")

    st.caption(INTRO_TIPO_GRAFICO.get(tipo, ""))
    if tipo == "Radar":
        st.plotly_chart(grafico_comparacao(df, "Temperatura", tipo, par, resumo, altura=420),
                        use_container_width=True)
        st.caption("Quanto maior a área, mais perto do limite de alerta. 100 % = no limite.")
    else:
        for a, b in (("Temperatura", "Vibracao"), ("Corrente", "RPM")):
            g1, g2 = st.columns(2)
            for col, v in ((g1, a), (g2, b)):
                with col:
                    st.plotly_chart(grafico_comparacao(df, v, tipo, par, resumo), use_container_width=True)
                    st.caption(intro_variavel(v))
                    st.caption(intro_variavel(v))
    st.plotly_chart(barras_falhas_comparacao(df, par), use_container_width=True)
    st.caption("Total de leituras normais (verde) e em falha de cada máquina no período.")


def render_dados():
    st.title("📊 Dados Brutos — Telemetria da Planta")
    st.caption("Leituras de temperatura, vibração, corrente e rotação de todas as máquinas, gravadas no MongoDB Atlas. "
               "Escolha o dia, o horário, as máquinas, a variável e o tipo de gráfico.")

    f = _filtros()
    if f is None:
        return
    dia, ini, fim, tags, variavel, tipo, tags_disp = f
    if not tags:
        st.info("Selecione ao menos uma máquina.")
        return

    with st.spinner("Carregando leituras..."):
        leituras = _carregar(ini, fim, tags)
    df = df_de_leituras(leituras)
    if df.empty:
        st.info("Nenhuma leitura no dia/horário selecionado.")
        return

    ultimas, criticas, alertas = _kpis(df, tags_disp)
    _estado_atual(ultimas, criticas, alertas)
    st.divider()

    aba = abas(["📈 Telemetria", "🚨 Falhas", "⚖️ Comparar", "🗂️ Tabela"], "aba_dados")
    if aba.endswith("Telemetria"):
        if variavel is None:
            _dashboard_unificado(df, tipo)
        else:
            _dashboard_individual(df, variavel, tipo)
    elif aba.endswith("Falhas"):
        _dashboard_falhas(df, dia, tags, tipo)
    elif aba.endswith("Comparar"):
        _aba_comparar(dia, ini, fim, tags_disp)
    else:
        _tabela(df, ini)

    bloco_exportar(
        df, contexto="telemetria", chave="exp_dados", referencia=dia,
        sufixo=(tags[0] if len(tags) == 1 else f"{len(tags)}maquinas"),
        origem_tela="Dados Brutos", maquinas=tags,
        descricao="Exporta as leituras do dia, horário e máquinas selecionados acima. "
                  "O arquivo fica guardado em Coleta de Dados → Biblioteca.")
