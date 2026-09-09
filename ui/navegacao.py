"""Navegação entre telas via session_state (integração com o Chat IA)."""
import streamlit as st

MENU_DADOS = "Dados Brutos (Telemetria)"
MENU_CONSULTA = "Consulta de Equipamentos"
MENU_FROTA = "Análise de Riscos (IA)"
MENU_CADASTRO = "Cadastro Técnico"
MENU_MANUTENCAO = "Manutenções"
MENU_FUNCIONARIOS = "Cadastro de Funcionários"
MENU_COLETA = "Coleta de Dados"
MENU_CHAT = "🤖 Chat IA (Análise)"
MENU_3D = "Visualização 3D"

MENU_ITENS = [MENU_DADOS, MENU_CONSULTA, MENU_FROTA, MENU_CADASTRO, MENU_MANUTENCAO,
              MENU_FUNCIONARIOS, MENU_COLETA, MENU_3D, MENU_CHAT]


def ir_para(menu):
    st.session_state["menu_destino"] = menu
    st.rerun()


def ir_para_chat(tag=None, pergunta=None, origem=None):
    """Abre o Chat IA já focado em uma máquina e com uma pergunta sugerida."""
    if tag:
        st.session_state["chat_tag_foco"] = tag
    if pergunta:
        st.session_state["chat_pergunta_pendente"] = pergunta
    if origem:
        st.session_state["chat_origem"] = origem
    ir_para(MENU_CHAT)


def botao_ia(tag, pergunta, chave, rotulo="🤖 Perguntar à IA", origem=None, destaque=False):
    """destaque=True deixa o botão grande, em largura total e com cor primária."""
    if st.button(rotulo, key=chave,
                 type="primary" if destaque else "secondary",
                 use_container_width=destaque):
        ir_para_chat(tag, pergunta, origem)
