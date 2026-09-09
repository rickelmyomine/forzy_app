"""
Autenticação simples por usuário/senha definidos no `.streamlit/secrets.toml`.

Formato esperado no secrets.toml:

    [usuarios.gerente]
    senha  = "forzy2026"
    nome   = "Gerente de Manutenção"
    perfil = "gerente"

    [usuarios.tecnico1]
    senha  = "tec123"
    nome   = "Técnico 1"
    perfil = "tecnico"

Perfis:
    gerente  -> acesso total (edita/exclui cadastros e manutenções, migra dados)
    tecnico  -> registra manutenções e fotos, cadastra equipamentos, vê dashboards
"""
import hmac
import os

import streamlit as st

PERFIS = {
    "gerente": "Gerente de Manutenção",
    "tecnico": "Técnico de Manutenção",
}

# Usuários de emergência caso o secrets.toml não tenha a seção [usuarios]
# (somente para não travar o app em desenvolvimento; troque em produção).
_USUARIOS_PADRAO = {
    "gerente": {"senha": "1234", "nome": "Gerente de Manutenção", "perfil": "gerente"},
    "tecnico1": {"senha": "1234", "nome": "Técnico 1", "perfil": "tecnico"},
    "tecnico2": {"senha": "1234", "nome": "Técnico 2", "perfil": "tecnico"},
}


def _carregar_usuarios():
    try:
        if "usuarios" in st.secrets:
            usuarios = {k: dict(v) for k, v in st.secrets["usuarios"].items()}
            if usuarios:
                return usuarios
    except Exception:
        pass
    return _USUARIOS_PADRAO


def autenticar(usuario, senha):
    """Retorna o dicionário do usuário se as credenciais conferem, senão None."""
    usuarios = _carregar_usuarios()
    dados = usuarios.get((usuario or "").strip().lower())
    if not dados:
        return None
    senha_ok = hmac.compare_digest(str(dados.get("senha", "")), str(senha or ""))
    if not senha_ok:
        return None
    return {
        "usuario": usuario.strip().lower(),
        "nome": dados.get("nome", usuario),
        "perfil": dados.get("perfil", "tecnico"),
    }


def usuario_atual():
    return st.session_state.get("usuario_logado")


def perfil_atual():
    u = usuario_atual()
    return u["perfil"] if u else None


def nome_usuario_atual():
    u = usuario_atual()
    return u["nome"] if u else "Sistema"


def esta_logado():
    return usuario_atual() is not None


def eh_gerente():
    return perfil_atual() == "gerente"


def logout():
    for chave in ("usuario_logado", "chat_gemini_history", "chat_gemini_last_interaction_id", "intro_pendente", "intro_inicio"):
        st.session_state.pop(chave, None)


def render_login():
    """Tela de login em página inteira. Retorna True quando o usuário entrou."""
    if esta_logado():
        return True

    col_esq, col_centro, col_dir = st.columns([1, 1.4, 1])
    with col_centro:
        if os.path.exists(os.path.join("assets", "logo_second_corp.png")):
            st.image(os.path.join("assets", "logo_second_corp.png"), use_container_width=True)
        st.markdown("### 🔐 Acesso ao Sistema de Gestão da Planta")
        st.caption("Telemetria, manutenção preditiva e gestão de ativos")

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="gerente, tecnico1, tecnico2")
            senha = st.text_input("Senha", type="password")
            telefone = st.text_input("Telefone (DDD) *", placeholder="(DD) 123456789",
                                     help="Telefone de quem está acessando — usado para os alertas de WhatsApp desta sessão.")
            entrar = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if entrar:
            dados = autenticar(usuario, senha)
            if dados:
                dados["telefone"] = (telefone or "").strip()
                st.session_state["usuario_logado"] = dados
                st.session_state["intro_pendente"] = True
                st.session_state.pop("intro_inicio", None)
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")

        with st.expander("Perfis de acesso", expanded=True):
            st.markdown(
                "- **Gerente da manutenção** (`gerente`) — acesso total: cadastro de funcionários e de "
                "equipamentos, manutenções, exclusões, envio de alertas e migração de dados.\n"
                "- **Técnico de manutenção** (`tecnico1`, `tecnico2`) — registra manutenções e fotos, "
                "cadastra equipamentos, faz coleta de dados, acompanha os dashboards e usa o Chat IA."
            )
        st.caption("Desenvolvido por Second Corporation")
    return False
