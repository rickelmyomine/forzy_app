import streamlit as st

st.set_page_config(
    page_title="Forzy — Manutenção Preditiva",
    page_icon="logo forzy.png",
    layout="wide"
)

from auth.auth import render_login
from ui.intro import intro_pendente, render_intro
from state.state_manager import init_state
from ui.sidebar import render_sidebar
from ui.navegacao import (
    MENU_DADOS, MENU_CONSULTA, MENU_FROTA, MENU_CADASTRO, MENU_MANUTENCAO,
    MENU_FUNCIONARIOS, MENU_COLETA, MENU_CHAT, MENU_3D,
)
from ui.view_frota import render_frota
from ui.view_funcionarios import render_funcionarios
from ui.view_coleta import render_coleta
from ui.view_dados import render_dados
from ui.view_consulta import render_consulta
from ui.view_cadastro import render_cadastro
from ui.view_manutencao import render_manutencao
from ui.view_chat import render_chat
from ui.View_view3d import render_view3d

init_state()

# --- Login obrigatório (gerente / técnicos definidos no secrets.toml) ---
if not render_login():
    st.stop()

# --- Primeira execução: grava telemetria (30 dias), cadastro e modelo se faltarem
#     (começa em segundo plano já durante o vídeo de apresentação) ---
from features.preparacao import garantir_dados_prontos
garantir_dados_prontos()

# --- Vídeo de apresentação (10 s) logo após o login ---
if intro_pendente():
    render_intro()
    st.stop()

# --- Alerta automático: crítico sustentado por 30 min avisa o gerente ---
from features.alertas import verificar_periodicamente
verificar_periodicamente()

# --- QR Code: /?tag=MOT-007 abre direto na máquina lida ---
_tag_qr = (st.query_params.get("tag") or "").strip().upper()
if _tag_qr and not st.session_state.get("qr_aplicado"):
    st.session_state["qr_aplicado"] = _tag_qr
    st.session_state["consulta_tag"] = _tag_qr
    st.session_state["view3d_tag"] = _tag_qr
    st.session_state["man_tag"] = _tag_qr
    st.session_state["menu"] = MENU_CONSULTA
    st.toast(f"QR Code lido: abrindo {_tag_qr}")

menu_selecionado = render_sidebar()

if menu_selecionado == MENU_DADOS:
    render_dados()

elif menu_selecionado == MENU_CONSULTA:
    render_consulta()

elif menu_selecionado == MENU_FROTA:
    render_frota()

elif menu_selecionado == MENU_CADASTRO:
    st.title("📝 Cadastro Técnico de Equipamento")
    render_cadastro()

elif menu_selecionado == MENU_MANUTENCAO:
    render_manutencao()

elif menu_selecionado == MENU_FUNCIONARIOS:
    render_funcionarios()

elif menu_selecionado == MENU_COLETA:
    render_coleta()

elif menu_selecionado == MENU_CHAT:
    render_chat()

elif menu_selecionado == MENU_3D:
    render_view3d()
