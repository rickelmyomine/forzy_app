"""
Consulta de Equipamentos — visão geral da planta e ficha completa por máquina:
foto, folha de dados simplificada, previsão de manutenção (modelo), documentos
(PDF do fabricante, site, manual), telemetria individual com dia/horário e
últimas manutenções. Tudo ligado ao Chat IA.
"""
import base64
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from features.graficos import serie_individual, barras_probabilidades, df_de_leituras, grafico_variavel, radar_maquinas, TIPOS_GRAFICO
from features.estilos import colorir_por_status, colorir_por_falha, abas
from features.textos import INTRO_CONSULTA, INTRO_TIPO_GRAFICO, intro_variavel
from features.prognostico import prever_data_manutencao
from features.imagens import b64_para_bytes
from features.limites import VARIAVEIS, NOMES_FALHA, classificar_status
from features.previsao import prever, prever_tendencia, modelo_disponivel
from providers.db_mongo import (
    EquipamentoRepository, TelemetriaRepository, ManutencaoRepository,
    PrevisaoRepository, MongoIndisponivelError,
)
from features.comparacao import (
    comparar_series, barras_comparacao, radar_comparacao, barras_falhas_comparacao,
    tabela_comparacao, texto_comparacao, grafico_comparacao, pizza_comparacao,
)
from ui.navegacao import ir_para_chat
from features.exportar import bloco_exportar

FUSO = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")

CAMPOS_FICHA = [
    ("Fabricante", "Fabricante"), ("Modelo", "Modelo"), ("Potencia", "Potência"), ("Tensao", "Tensão"),
    ("Corrente", "Corrente nominal"), ("RPM", "Rotação nominal"), ("NumeroSerie", "Nº de série"),
    ("Planta", "Planta"), ("Criticidade", "Criticidade"), ("AnoInstalacao", "Ano de instalação"),
]


@st.cache_data(ttl=300, show_spinner=False)
def _cadastro_leve():
    """Cadastro SEM as fotos (base64). Carregar as 20 fotos a cada recarregamento
    era o que deixava esta tela lenta — agora a foto vem só da máquina aberta."""
    return {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}


@st.cache_data(ttl=600, show_spinner=False, max_entries=30)
def _foto(tag):
    doc = EquipamentoRepository.buscar_por_tag(tag) or {}
    return doc.get("foto")


@st.cache_data(ttl=300, show_spinner=False)
def _previsoes_todas(tags):
    """Roda o modelo para todas as TAGs em uma só consulta ao banco."""
    if not modelo_disponivel():
        return {}
    lotes = TelemetriaRepository.ultimas_n_por_tag(tags, 5)
    resultado = {}
    for tag, ultimas in lotes.items():
        p = prever(ultimas) if ultimas else None
        if p:
            PrevisaoRepository.salvar(tag, p)
            resultado[tag] = p
    return resultado


@st.cache_data(ttl=120, show_spinner=False)
def _dados_visao_geral(tags):
    """Última leitura e última OS de cada máquina — 2 consultas no total."""
    ultimas = TelemetriaRepository.ultimas_leituras(tags)
    try:
        os_por_tag = ManutencaoRepository.ultimas_por_tag(tags)
    except MongoIndisponivelError:
        os_por_tag = {}
    return ultimas, os_por_tag


def _visao_geral(cadastro, tags):
    st.subheader("Visão geral da planta")
    tags_t = tuple(sorted(tags))
    previsoes = _previsoes_todas(tags_t)
    ultimas, os_por_tag = _dados_visao_geral(tags_t)
    linhas = []
    for tag in tags:
        e = cadastro.get(tag, {})
        ult = ultimas.get(tag) or {}
        status, ic = classificar_status(ult.get("Temperatura"), ult.get("Vibracao"), ult.get("Corrente"),
                                        ult.get("RPM"), ult.get("FalhaCodigo", 0)) if ult else ("-", "")
        p = previsoes.get(tag)
        os_ = os_por_tag.get(tag)
        ultima_os = os_["data"].strftime("%d/%m/%Y") if os_ and hasattr(os_.get("data"), "strftime") else "-"
        linhas.append({
            "Máquina": tag, "Fabricante": e.get("Fabricante", "-"), "Modelo": e.get("Modelo", "-"),
            "Potência": e.get("Potencia", "-"), "Planta": e.get("Planta", "-"), "Crit.": (e.get("Criticidade") or "-")[:1],
            "Status atual": f"{ic} {status}",
            "Temp (°C)": ult.get("Temperatura"), "Vib (mm/s)": ult.get("Vibracao"),
            "Previsão": f"{p['classe_nome']} ({p['nivel_risco'].lower()})" if p else "-",
            "Risco": f"{p['risco']*100:.0f}%" if p else "-",
            "Última OS": ultima_os, "Foto": "📷",
        })
    df = pd.DataFrame(linhas)
    df["_nivel"] = [("Crítico" if "Crítico" in r["Status atual"] or "(alto)" in r["Previsão"] else
                     ("Alerta" if "Alerta" in r["Status atual"] or "(moderado)" in r["Previsão"] else "Normal")) for r in linhas]
    st.dataframe(colorir_por_status(df, "_nivel").hide(axis="columns", subset=["_nivel"]),
                 use_container_width=True, hide_index=True, height=min(60 + 36 * len(df), 480))
    st.caption(INTRO_CONSULTA["visao_geral"])

    if previsoes:
        alto = [t for t, p in previsoes.items() if p["nivel_risco"] == "Alto"]
        mod = [t for t, p in previsoes.items() if p["nivel_risco"] == "Moderado"]
        if alto:
            st.error(f"🔴 Risco alto pelo modelo: {', '.join(alto)} — priorizar inspeção.")
        if mod:
            st.warning(f"🟡 Risco moderado: {', '.join(mod)}.")
        if not alto and not mod:
            st.success("🟢 Nenhuma máquina com risco elevado segundo o modelo.")
    return previsoes


def _ficha(e, tag):
    col_foto, col_dados = st.columns([1, 1.4])
    with col_foto:
        foto = e.get("foto") or _foto(tag)
        if foto:
            st.image(b64_para_bytes(foto), use_container_width=True)
        else:
            st.info("Sem foto. Adicione em Cadastro Técnico → Editar / Foto.")
    with col_dados:
        st.markdown(f"### {tag} — {e.get('Fabricante', '')} {e.get('Modelo', '')}")
        c1, c2 = st.columns(2)
        for i, (chave, rotulo) in enumerate(CAMPOS_FICHA):
            valor = e.get(chave)
            (c1 if i % 2 == 0 else c2).markdown(f"**{rotulo}:** {valor if valor not in (None, '') else '-'}")
        if e.get("Observacoes"):
            st.markdown(f"**Observações:** {e['Observacoes']}")

        st.markdown("**Documentos**")
        d1, d2, d3 = st.columns(3)
        if e.get("datasheet_pdf"):
            d1.download_button("📄 Folha de dados (PDF)", base64.b64decode(e["datasheet_pdf"]),
                               file_name=e.get("datasheet_nome", f"{tag}_datasheet.pdf"), mime="application/pdf",
                               key=f"pdf_{tag}", use_container_width=True)
        else:
            d1.caption("Sem PDF do fabricante")
        if e.get("site_url"):
            d2.link_button("🌐 Site do fabricante", e["site_url"], use_container_width=True)
        if e.get("manual_url"):
            d3.link_button("📘 Manual", e["manual_url"], use_container_width=True)
        elif e.get("manual_pdf"):
            d3.download_button("📘 Manual (PDF)", base64.b64decode(e["manual_pdf"]),
                               file_name=e.get("manual_nome", f"{tag}_manual.pdf"), mime="application/pdf",
                               key=f"man_{tag}", use_container_width=True)


def _previsao(tag, previsao):
    st.subheader("🔮 Previsão de manutenção (modelo de falhas)")
    if not modelo_disponivel():
        st.info("Modelo não encontrado. Rode `python scripts/treinar_modelo.py` para treinar a partir do CSV.")
        return
    if not previsao:
        st.info("Sem leituras suficientes para prever.")
        return
    cor = {"Baixo": "success", "Moderado": "warning", "Alto": "error"}[previsao["nivel_risco"]]
    getattr(st, cor)(
        f"**{previsao['classe_nome']}** — risco {previsao['nivel_risco'].lower()} "
        f"({previsao['risco']*100:.0f}% de probabilidade de falha) · confiança {previsao['confianca']*100:.0f}%"
    )
    c1, c2 = st.columns([1, 1.3])
    with c1:
        st.plotly_chart(barras_probabilidades(previsao["probabilidades"]), use_container_width=True,
                        config={"displayModeBar": False})
    with c2:
        st.markdown(f"**Recomendação:** {previsao['recomendacao']}")
        recentes = TelemetriaRepository.obter_ultimas_n(tag, 6)
        anteriores = TelemetriaRepository.obter_historico(tag, limite=36)[6:]
        tend = prever_tendencia(recentes, anteriores)
        if tend:
            st.markdown("**Tendência (última hora vs. 5 horas anteriores):** " + " · ".join(
                f"{VARIAVEIS[s]['rotulo']} {t['seta']} {t['recente']:g} {VARIAVEIS[s]['unidade']}"
                for s, t in tend.items()))
        st.caption(f"Modelo: {previsao['modelo']} · acurácia em teste {previsao['acuracia_teste'] or '-'} · "
                   f"F1-macro {previsao['f1_macro_teste'] or '-'} · janela de {previsao['janela_leituras']} leituras.")
    prog = prever_data_manutencao(tag)
    if prog:
        st.markdown(f"**📅 Prognóstico:** {prog['texto']}")
        if prog["motivos"]:
            st.markdown("**Por que o status atual:** " + "; ".join(prog["motivos"]))
    st.caption(INTRO_CONSULTA["previsao"] + " O prognóstico extrapola a tendência das últimas 6 h até o limite crítico e combina com o risco do modelo.")


def _telemetria_individual(tag):
    st.subheader("📈 Telemetria da máquina")
    ini_disp, fim_disp = TelemetriaRepository.periodo_disponivel()
    if fim_disp is None:
        st.info("Sem histórico.")
        return
    fim_local = pd.Timestamp(fim_disp, tz="UTC").tz_convert(FUSO)
    ini_local = pd.Timestamp(ini_disp, tz="UTC").tz_convert(FUSO)
    c1, c2, c3, c4 = st.columns([1, 1.6, 1.1, 1.0])
    dia = c1.date_input("Dia", value=fim_local.date(), min_value=ini_local.date(), max_value=fim_local.date(), key=f"ce_dia_{tag}")
    faixa = c2.slider("Horário", value=(time(0, 0), time(23, 59)), format="HH:mm", step=timedelta(minutes=10), key=f"ce_hora_{tag}")
    variavel = c3.selectbox("Variável", ["Todas"] + [VARIAVEIS[v]["rotulo"] for v in VARIAVEIS], key=f"ce_var_{tag}")
    tipo = c4.selectbox("Tipo de gráfico", TIPOS_GRAFICO, key=f"ce_tipo_{tag}")
    ini = datetime.combine(dia, faixa[0]).replace(tzinfo=FUSO).astimezone(UTC).replace(tzinfo=None)
    fim = datetime.combine(dia, faixa[1]).replace(tzinfo=FUSO).astimezone(UTC).replace(tzinfo=None)
    df = df_de_leituras(TelemetriaRepository.obter_intervalo(ini, fim, tags=[tag]))
    if df.empty:
        st.info("Nenhuma leitura nesse dia/horário.")
        return
    falhas = df[df["FalhaCodigo"] != 0]
    m = st.columns(5)
    m[0].metric("Leituras", len(df))
    m[1].metric("Temp. máx", f"{df['Temperatura'].max():.1f} °C")
    m[2].metric("Vib. máx", f"{df['Vibracao'].max():.2f} mm/s")
    m[3].metric("Corrente máx", f"{df['Corrente'].max():.1f} A")
    m[4].metric("Leituras em falha", len(falhas))
    def _fig(chave, altura):
        return serie_individual(df, chave, tag, altura=altura) if tipo == "Linha" else grafico_variavel(df, chave, tipo, altura=altura)
    st.caption(INTRO_TIPO_GRAFICO[tipo])
    if tipo == "Radar":
        st.plotly_chart(radar_maquinas(df, tags=[tag]), use_container_width=True)
        for v in VARIAVEIS:
            st.caption(intro_variavel(v))
    elif variavel == "Todas":
        for a, b in (("Temperatura", "Vibracao"), ("Corrente", "RPM")):
            g1, g2 = st.columns(2)
            with g1:
                st.plotly_chart(_fig(a, 280), use_container_width=True)
                st.caption(intro_variavel(a))
            with g2:
                st.plotly_chart(_fig(b, 280), use_container_width=True)
                st.caption(intro_variavel(b))
    else:
        chave = next(k for k, v in VARIAVEIS.items() if v["rotulo"] == variavel)
        st.plotly_chart(_fig(chave, 380), use_container_width=True)
        st.caption(intro_variavel(chave))
    st.caption(INTRO_CONSULTA["telemetria"])
    if not falhas.empty:
        st.markdown("**Falhas registradas no dia**")
        t = falhas[["timestamp", "FalhaCodigo", "Temperatura", "Vibracao", "Corrente", "RPM"]].copy()
        t["Tipo"] = t["FalhaCodigo"].map(NOMES_FALHA)
        t["Horário"] = t["timestamp"].dt.strftime("%d/%m %H:%M")
        st.dataframe(colorir_por_falha(t[["Horário", "Tipo", "Temperatura", "Vibracao", "Corrente", "RPM", "FalhaCodigo"]]
                                       .sort_values("Horário", ascending=False)).hide(axis="columns", subset=["FalhaCodigo"]),
                     use_container_width=True, hide_index=True, height=220)


def _manutencoes(tag):
    st.subheader("🛠️ Últimas manutenções")
    try:
        docs = ManutencaoRepository.listar(tag=tag, limite=5)
    except MongoIndisponivelError as e:
        st.warning(str(e))
        return
    if not docs:
        st.caption("Nenhuma manutenção registrada para esta máquina.")
        return
    st.caption(INTRO_CONSULTA["manutencoes"])
    for d in docs:
        data = d.get("data")
        data_txt = data.strftime("%d/%m/%Y %H:%M") if hasattr(data, "strftime") else str(data)
        st.markdown(
            f"- **{data_txt}** · {d.get('tipo')} · {d.get('status')} · {d.get('categoria_nome', '')} — "
            f"{d.get('servico_executado') or d.get('descricao_problema') or ''} *(téc. {d.get('tecnico', '-')})*"
        )


@st.cache_data(ttl=120, show_spinner=False)
def _leituras_periodo(ini, fim, tags):
    return TelemetriaRepository.obter_intervalo(ini, fim, tags=tags)


def _comparar_maquinas(tags_disp, cadastro, previsoes):
    st.subheader("⚖️ Comparar máquinas")
    st.caption("Compare duas ou mais máquinas: leituras, falhas, previsão do modelo e dados de placa "
               "lado a lado. Útil para decidir prioridade de manutenção entre equipamentos parecidos.")
    c1, c2, c3 = st.columns([2.2, 1, 1])
    padrao = tags_disp[:2] if len(tags_disp) > 1 else tags_disp
    sel = c1.multiselect("Máquinas (2 ou mais)", tags_disp, default=padrao, key="cmp_cons_tags")
    periodo = c2.selectbox("Período", [1, 7, 30], index=1, format_func=lambda d: f"últimos {d} dia(s)", key="cmp_cons_dias")
    tipo = c3.selectbox("Tipo de gráfico", TIPOS_GRAFICO, key="cmp_cons_tipo")
    if len(sel) < 2:
        st.info("Escolha ao menos duas máquinas.")
        return
    fim = datetime.now(UTC).replace(tzinfo=None)
    ini = fim - timedelta(days=periodo)
    df = df_de_leituras(_leituras_periodo(ini, fim, tuple(sorted(sel))))
    if df.empty:
        st.info("Sem leituras no período.")
        return

    # Ficha resumida lado a lado
    cols = st.columns(len(sel))
    for col, tag in zip(cols, sorted(sel)):
        e = cadastro.get(tag, {})
        p = (previsoes or {}).get(tag)
        with col:
            with st.container(border=True):
                foto = e.get("foto") or _foto(tag)
                if foto:
                    st.image(b64_para_bytes(foto), use_container_width=True)
                st.markdown(f"**{tag}** · {e.get('Fabricante', '-')} {e.get('Modelo', '')}")
                st.caption(f"{e.get('Potencia', '-')} · {e.get('Tensao', '-')} · {e.get('Planta', '-')}")
                if p:
                    icone = {"Baixo": "🟢", "Moderado": "🟡", "Alto": "🔴"}[p["nivel_risco"]]
                    st.markdown(f"{icone} Previsão: **{p['classe_nome']}** ({p['risco'] * 100:.0f}% de risco)")

    resumo = tabela_comparacao(df, sel)
    st.markdown(texto_comparacao(resumo))
    st.dataframe(colorir_por_status(resumo), use_container_width=True, hide_index=True)
    st.caption("Média, máximo e mínimo de cada variável no período e leituras em falha. "
               "Linha amarela = alerta, vermelha = crítico.")

    if tipo == "Radar":
        st.plotly_chart(grafico_comparacao(df, "Temperatura", tipo, sel, resumo, altura=440),
                        use_container_width=True)
        st.caption("Quanto maior a área, mais perto do limite de alerta (100 % = no limite).")
    else:
        for a, b in (("Temperatura", "Vibracao"), ("Corrente", "RPM")):
            g1, g2 = st.columns(2)
            for col, v in ((g1, a), (g2, b)):
                with col:
                    st.plotly_chart(grafico_comparacao(df, v, tipo, sel, resumo), use_container_width=True)
                    st.caption(intro_variavel(v))
    st.plotly_chart(barras_falhas_comparacao(df, sel), use_container_width=True)
    st.caption("Leituras normais (verde) e em falha de cada máquina no período comparado.")

    bloco_exportar(df, contexto="comparacao", chave="exp_cmp_consulta",
                   sufixo="-".join(sorted(sel))[:40], origem_tela="Comparação de máquinas",
                   maquinas=sorted(sel),
                   descricao="Exporta as leituras das máquinas comparadas no período escolhido.")

    if st.button("🤖 Pedir à IA para comparar estas máquinas", key="cmp_ia"):
        ir_para_chat(None, f"Compare as máquinas {', '.join(sorted(sel))} nos últimos {periodo} dia(s): "
                           "telemetria, falhas, previsão do modelo e manutenções. Qual está pior e o que fazer primeiro?",
                     origem="comparacao")


def render_consulta():
    st.title("🔎 Consulta de Equipamentos")
    try:
        cadastro = _cadastro_leve()
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    tags_tele = TelemetriaRepository.obter_tags_disponiveis()
    tags = sorted(set(cadastro) | set(tags_tele))
    planta = st.session_state.get("planta_selecionada")
    if planta and planta != "Todas as plantas":
        filtradas = [t for t in tags if cadastro.get(t, {}).get("Planta") in (planta, None)]
        tags = filtradas or tags
    if not tags:
        st.info("Nenhum equipamento. Use Cadastro Técnico → Cadastro de exemplo (gerente) ou cadastre manualmente.")
        return

    aba = abas(["🏭 Visão geral e ficha", "⚖️ Comparar máquinas"], "aba_consulta")
    if aba.endswith("Comparar máquinas"):
        previsoes_cmp = _previsoes_todas(tuple(sorted(tags)))
        _comparar_maquinas(tags, cadastro, previsoes_cmp)
    else:
        _render_geral(cadastro, tags)


def _render_geral(cadastro, tags):
    previsoes = _visao_geral(cadastro, tags)
    st.divider()

    tag_padrao = st.session_state.get("consulta_tag")
    idx = tags.index(tag_padrao) if tag_padrao in tags else 0
    tag = st.selectbox("Selecione a máquina para ver a ficha completa", tags, index=idx, key="consulta_tag_sel")
    st.session_state["consulta_tag"] = tag
    e = cadastro.get(tag)
    if not e:
        st.warning(f"{tag} tem telemetria mas ainda não está no cadastro técnico.")
        e = {"TAG": tag}

    b1, b15, b2 = st.columns([1, 1, 2])
    if b15.button("📨 Enviar alerta desta máquina", use_container_width=True):
        st.session_state["al_tag"] = tag
        from ui.navegacao import ir_para, MENU_FUNCIONARIOS
        ir_para(MENU_FUNCIONARIOS)
    if b1.button("🤖 Analisar esta máquina com a IA", type="primary", use_container_width=True):
        ir_para_chat(tag, f"Faça uma análise completa do {tag}: estado atual, histórico de falhas, "
                          f"previsão do modelo e manutenções registradas. O que devo fazer?")
    b2.caption("Abre o Chat IA com o contexto desta máquina (cadastro, telemetria, falhas, previsão e manutenções).")

    _ficha(e, tag)
    st.divider()
    _previsao(tag, previsoes.get(tag) if previsoes else None)
    st.divider()
    _telemetria_individual(tag)
    st.divider()
    _manutencoes(tag)

    fim = datetime.now(UTC).replace(tzinfo=None)
    df_exp = df_de_leituras(_leituras_periodo(fim - timedelta(days=30), fim, (tag,)))
    bloco_exportar(df_exp, contexto="equipamento", chave="exp_consulta", sufixo=tag,
                   origem_tela="Consulta de Equipamentos", maquinas=[tag],
                   descricao=f"Exporta os últimos 30 dias de leituras do {tag}. "
                             "O arquivo fica guardado em Coleta de Dados → Biblioteca.")
