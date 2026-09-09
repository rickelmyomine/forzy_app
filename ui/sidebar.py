import os

import streamlit as st

from auth.auth import usuario_atual, PERFIS, logout
from providers.db_mongo import LocalizacaoRepository, testar_conexao
from ui.navegacao import MENU_ITENS

OPCAO_TODAS_PLANTAS = "Todas as plantas"

# Menu compacto e com fontes maiores (o logo do grupo precisa caber na tela)
_CSS = """
<style>
  [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap: 0.45rem;}
  [data-testid="stSidebar"] hr {margin: 0.5rem 0;}
  [data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] {padding-top: 0.8rem; padding-bottom: 0.5rem;}
  [data-testid="stSidebar"] h1 {font-size: 1.35rem; margin-bottom: 0.3rem;}
  /* Navegação */
  [data-testid="stSidebar"] [role="radiogroup"] label p {font-size: 1.02rem; font-weight: 600;}
  [data-testid="stSidebar"] [role="radiogroup"] > label {padding: 0.12rem 0;}
  /* Rótulos e caixas de seleção */
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {font-size: 1rem;}
  [data-testid="stSidebar"] [data-baseweb="select"] div {font-size: 1rem;}
  [data-testid="stSidebar"] .stButton > button {font-size: 1rem; padding: 0.25rem 0.6rem;}
  [data-testid="stSidebar"] img {margin-bottom: 0.2rem;}
  /* Seletores da área principal um pouco maiores */
  [data-testid="stMain"] [data-baseweb="select"] div {font-size: 1rem;}
  [data-testid="stMain"] [data-testid="stWidgetLabel"] p {font-size: 0.98rem;}
</style>
"""


def _painel_conexoes():
    """Serviços a que o sistema se conecta, com bolinha verde/cinza."""
    from features.alertas import email_configurado, whatsapp_automatico_configurado
    import os as _os

    def _gemini_ok():
        try:
            if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
                return True
        except Exception:
            pass
        return bool(_os.environ.get("GEMINI_API_KEY"))

    servicos = [
        ("MongoDB Atlas", testar_conexao(), "banco de dados"),
        ("IA Gemini", _gemini_ok(), "chat e leitura de placa"),
        ("E-mail (Gmail)", email_configurado(), "alertas por e-mail"),
        ("WhatsApp", True if whatsapp_automatico_configurado() else "link",
         "automático (Twilio)" if whatsapp_automatico_configurado() else "envio por link"),
    ]
    linhas = []
    for nome, estado, detalhe in servicos:
        if estado is True:
            bola, cor = "🟢", "#7ee787"
        elif estado == "link":
            bola, cor = "🟡", "#e3c46a"
        else:
            bola, cor = "⚪", "#9aa0aa"
        linhas.append(
            f"<div style='display:flex;align-items:center;gap:6px;font-size:0.92rem;line-height:1.45'>"
            f"<span>{bola}</span><span style='color:{cor};font-weight:600'>{nome}</span>"
            f"<span style='opacity:.65;font-size:0.82rem'>· {detalhe}</span></div>"
        )
    st.sidebar.markdown("**Conexões do sistema**")
    st.sidebar.markdown("".join(linhas), unsafe_allow_html=True)



@st.cache_data(ttl=180, show_spinner=False)
def _resumo_previsao():
    """Quantas máquinas o modelo aponta em cada nível de risco agora."""
    from features.previsao import modelo_disponivel, prever, resumo_modelo
    from providers.db_mongo import TelemetriaRepository
    if not modelo_disponivel():
        return None
    tags = TelemetriaRepository.obter_tags_disponiveis()
    if not tags:
        return None
    niveis = {"Alto": 0, "Moderado": 0, "Baixo": 0}
    criticas = []
    for tag, ultimas in TelemetriaRepository.ultimas_n_por_tag(tuple(tags), 5).items():
        p = prever(ultimas) if ultimas else None
        if not p:
            continue
        niveis[p["nivel_risco"]] = niveis.get(p["nivel_risco"], 0) + 1
        if p["nivel_risco"] == "Alto":
            criticas.append(tag)
    return {"niveis": niveis, "alto": sorted(criticas), "meta": resumo_modelo()}


def render_sidebar():
    st.html(_CSS)
    st.sidebar.title("Gestão da Planta")

    # --- Usuário logado ---
    usuario = usuario_atual()
    if usuario:
        icone = "👔" if usuario["perfil"] == "gerente" else "🔧"
        st.sidebar.markdown(
            f"{icone} **{usuario['nome']}**  \n"
            f"<span style='font-size:0.85em;opacity:0.8'>{PERFIS.get(usuario['perfil'], usuario['perfil'])}</span>",
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Sair", use_container_width=True):
            logout()
            st.rerun()
    st.sidebar.markdown("---")

    # --- Navegação (Dados Brutos é a tela principal) ---
    destino = st.session_state.pop("menu_destino", None)
    if destino in MENU_ITENS:
        st.session_state["menu"] = destino
    if "menu" not in st.session_state:
        st.session_state["menu"] = MENU_ITENS[0]
    menu = st.sidebar.radio("Navegação", MENU_ITENS, key="menu")

    st.sidebar.markdown("---")

    # --- Planta ---
    plantas = [OPCAO_TODAS_PLANTAS] + list(LocalizacaoRepository.obter_plantas_e_areas().keys())
    planta = st.sidebar.selectbox("Planta", plantas, key="planta_sel")
    st.session_state['planta_selecionada'] = planta
    st.session_state['area_selecionada'] = None

    st.sidebar.markdown("---")
    _painel_conexoes()
    from features.preparacao import painel_progresso
    with st.sidebar:
        painel_progresso()
    st.sidebar.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
    if os.path.exists(os.path.join("assets", "logo_second_corp.png")):
        st.sidebar.image(os.path.join("assets", "logo_second_corp.png"), use_container_width=True)

    return menu
