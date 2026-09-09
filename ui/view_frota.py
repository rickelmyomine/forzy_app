"""
Análise de Riscos (IA) — identifica as máquinas com mais manutenções, mais
leituras críticas e mais alertas; calcula a saúde de cada uma e recomenda
manter / revisar-atualizar / substituir, com atalho para o site do fabricante
e análise detalhada pela IA.
"""
import pandas as pd
import streamlit as st

from features.estilos import colorir_por_nivel
from features.frota import tabela_frota, resumo_frota_texto
from features.graficos import barras_ranking, radar_maquinas, df_de_leituras
from providers.db_mongo import TelemetriaRepository
from ui.navegacao import ir_para_chat


@st.cache_data(ttl=600, show_spinner=False)
def _frota(dias, planta):
    return tabela_frota(dias)


def render_frota():
    st.title("⚠️ Análise de Riscos (IA)")
    st.caption("Quais máquinas mais dão trabalho: manutenções, leituras críticas e alertas no período, "
               "pontuação de saúde e recomendação de manter, revisar/atualizar ou substituir.")

    c1, c2 = st.columns([1, 3])
    dias = c1.selectbox("Período analisado", [7, 30, 90], index=1, format_func=lambda d: f"últimos {d} dias", key="frota_dias")
    with st.spinner("Analisando os riscos..."):
        df = _frota(dias, st.session_state.get("planta_selecionada"))
    if df.empty:
        st.info("Sem dados suficientes.")
        return

    planta = st.session_state.get("planta_selecionada")
    if planta and planta != "Todas as plantas":
        from providers.db_mongo import EquipamentoRepository
        cad = {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}
        df = df[df["Máquina"].map(lambda t: cad.get(t, {}).get("Planta") in (planta, None))]

    subst = df[df["Recomendação"].str.startswith("Substituir")]["Máquina"].tolist()
    revisar = df[df["Recomendação"].str.startswith("Revisar")]["Máquina"].tolist()
    k = st.columns(4)
    k[0].metric("Máquinas analisadas", len(df))
    k[1].metric("Saúde média das máquinas", f"{df['Saúde'].mean():.0f}/100")
    k[2].metric("Revisar / atualizar", len(revisar))
    k[3].metric("Substituir", len(subst))
    if subst:
        st.error(f"🔴 Candidatas a substituição: {', '.join(subst)} — excesso de falhas e corretivas para a idade. "
                 "Compare o custo de nova manutenção com a compra de um motor novo no site do fabricante.")
    if revisar:
        st.warning(f"🟡 Revisar / atualizar: {', '.join(revisar)} — programar revisão completa (rolamentos, alinhamento, ventilação, isolação).")
    st.caption("Saúde parte de 100 e desconta: % de leituras em falha, % em alerta, manutenções corretivas, horas paradas, "
               "idade acima de 10 anos e risco do modelo. Abaixo de 60 → revisar; abaixo de 40 (ou muitas falhas + corretivas + idade) → substituir.")

    st.divider()
    st.subheader("Ranking")
    st.dataframe(colorir_por_nivel(df.drop(columns=["Site"]), "Recomendação"),
                 use_container_width=True, hide_index=True, height=min(60 + 36 * len(df), 520))
    st.caption("Ordenado da pior para a melhor saúde. Linhas vermelhas = substituir, amarelas = revisar/atualizar. "
               "Leituras críticas/alerta contam a última leitura de cada intervalo de 10–30 min no período.")

    g1, g2, g3 = st.columns(3)
    g1.plotly_chart(barras_ranking(df.set_index("Máquina")["Manutenções"].head(10), "Mais manutenções", cor="#9085e9", unidade="OS"), use_container_width=True)
    g1.caption("Máquinas com mais ordens de serviço no período (preventivas + corretivas). Muitas OS com poucas horas paradas = manutenção bem feita; muitas corretivas = problema crônico.")
    g2.plotly_chart(barras_ranking(df.set_index("Máquina")["Leituras críticas"].head(10), "Mais leituras críticas", cor="#e66767", unidade="leituras"), use_container_width=True)
    g2.caption("Leituras em estado crítico (falha rotulada ou variável acima do limite crítico). Ideal: zero.")
    g3.plotly_chart(barras_ranking(df.set_index("Máquina")["Leituras em alerta"].head(10), "Mais alertas", cor="#c98500", unidade="leituras"), use_container_width=True)
    g3.caption("Leituras em alerta (entre a faixa normal e o limite crítico). Alerta frequente antecede a falha — bom momento para a preventiva.")

    # Radar das piores
    piores = df.head(6)["Máquina"].tolist()
    from datetime import datetime, timedelta, timezone
    agora = datetime.now(timezone.utc)
    leit = TelemetriaRepository.obter_intervalo(agora - timedelta(days=1), agora, tags=piores)
    dfl = df_de_leituras(leit)
    if not dfl.empty:
        st.plotly_chart(radar_maquinas(dfl, tags=piores), use_container_width=True)
        st.caption("Radar das 6 piores máquinas nas últimas 24 h: quanto maior a área, mais perto do limite de alerta em cada variável (100 % = no limite).")

    st.divider()
    st.subheader("Recomendação da IA")
    sel = st.multiselect("Máquinas para a IA analisar", df["Máquina"].tolist(), default=(subst + revisar)[:5] or df["Máquina"].head(3).tolist(), key="frota_sel")
    if st.button("🤖 Pedir à IA: trocar, atualizar ou comprar nova?", type="primary"):
        pergunta = (f"Com base no ranking de riscos dos últimos {dias} dias, analise as máquinas {', '.join(sel)}: "
                    "para cada uma diga se deve ser mantida, revisada/atualizada ou substituída por uma nova, "
                    "justifique com manutenções, leituras críticas, alertas, idade e risco do modelo, estime a urgência "
                    "e, quando recomendar substituição, sugira consultar o site do fabricante (informe o link do cadastro).")
        st.session_state["chat_frota_resumo"] = resumo_frota_texto(df[df["Máquina"].isin(sel)] if sel else df, top=10)
        ir_para_chat(None, pergunta, origem="analise_de_frota")
    st.caption("A IA recebe este ranking, o cadastro, a telemetria e as manutenções de cada máquina e responde citando as fontes.")

    with st.expander("🌐 Sites dos fabricantes"):
        for _, r in df.drop_duplicates("Fabricante").iterrows():
            if r["Site"]:
                st.markdown(f"- **{r['Fabricante']}** — {r['Site']}")
