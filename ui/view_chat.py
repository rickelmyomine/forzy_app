"""
Chat IA (Análise).

- Dúvidas frequentes (50 perguntas): respondidas na hora só com os dados das
  leituras, cadastro, previsões, manutenções e funcionários (sem IA externa).
- Perguntas livres: a IA recebe a varredura completa do sistema (cadastro,
  telemetria, falhas, previsões, manutenções, análise de frota, documentação)
  e pode buscar na internet (Google Search) o que não estiver nos dados,
  citando as fontes.
"""
import os

import streamlit as st
from google import genai
from google.genai import types

from features.contexto_ia import montar_contexto
from features.perguntas_prontas import CARDAPIO, responder_pronta
from providers.db_mongo import EquipamentoRepository, TelemetriaRepository, MongoIndisponivelError

MODELOS_DISPONIVEIS = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]


def _obter_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def _extrair_fontes_web(resp):
    """Links usados pela busca na internet (grounding), se houver."""
    urls = []
    try:
        cand = resp.candidates[0]
        meta = getattr(cand, "grounding_metadata", None)
        for ch in (getattr(meta, "grounding_chunks", None) or []):
            web = getattr(ch, "web", None)
            if web and getattr(web, "uri", None):
                urls.append((getattr(web, "title", None) or web.uri, web.uri))
    except Exception:
        pass
    return urls


def _chamar_gemini(client, modelo, contexto, pergunta, usar_internet=True):
    """
    generate_content com busca na internet (grounding). Se a busca não for
    aceita pela chave/modelo, repete sem ela. Retorna (texto, fontes_web).
    """
    historico = st.session_state.get("chat_gemini_history", [])[-6:]
    conversa = "\n".join(f"{'Usuário' if m['role'] == 'user' else 'Assistente'}: {m['content'][:800]}" for m in historico)
    prompt = (f"Conversa até aqui:\n{conversa}\n\nPergunta atual: {pergunta}") if conversa else pergunta

    erros = []
    configs = []
    if usar_internet:
        configs.append(types.GenerateContentConfig(
            system_instruction=contexto, temperature=0.3,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ))
    configs.append(types.GenerateContentConfig(system_instruction=contexto, temperature=0.3))
    for cfg in configs:
        try:
            resp = client.models.generate_content(model=modelo, contents=prompt, config=cfg)
            return resp.text, _extrair_fontes_web(resp)
        except Exception as e:
            erros.append(str(e)[:200])
    # Último recurso: Interactions API
    try:
        inter = client.interactions.create(model=modelo, input=prompt, system_instruction=contexto)
        return inter.output_text, []
    except Exception as e:
        erros.append(str(e)[:200])
    raise RuntimeError(" | ".join(erros))


def _adicionar(role, content, fontes=None, fontes_web=None, direto=False):
    st.session_state["chat_gemini_history"].append(
        {"role": role, "content": content, "fontes": fontes or [], "fontes_web": fontes_web or [], "direto": direto}
    )


def _mostrar_mensagem(msg):
    with st.chat_message(msg["role"]):
        if msg.get("direto"):
            st.caption("📊 Resposta imediata calculada com os dados do sistema")
        st.markdown(msg["content"])
        if msg.get("fontes") or msg.get("fontes_web"):
            with st.expander("📚 Fontes consultadas"):
                for f in msg.get("fontes", []):
                    st.markdown(f"- **{f['fonte']}** — {f['titulo']}")
                for titulo, url in msg.get("fontes_web", []):
                    st.markdown(f"- 🌐 [{titulo}]({url})")


def render_chat():
    st.title("🤖 Assistente de Análise (IA)")
    st.caption(f"{len(CARDAPIO)} dúvidas frequentes são respondidas na hora com os dados das leituras. "
               "Perguntas livres passam pela IA, que varre todo o sistema (cadastro, telemetria, falhas, "
               "previsões, manutenções, documentação) e a internet.")

    st.session_state.setdefault("chat_gemini_history", [])

    # --- Foco e modelo ---
    try:
        tags = sorted(set(EquipamentoRepository.listar_tags()) | set(TelemetriaRepository.obter_tags_disponiveis()))
    except MongoIndisponivelError:
        tags = TelemetriaRepository.obter_tags_disponiveis()
    opcoes_foco = ["Toda a planta"] + tags
    foco_pendente = st.session_state.pop("chat_tag_foco", None)
    if foco_pendente in tags:
        st.session_state["chat_foco_sel"] = foco_pendente

    col_foco, col_modelo, col_net, col_reset = st.columns([1.4, 1.4, 1, 1])
    foco = col_foco.selectbox("Foco da análise", opcoes_foco, key="chat_foco_sel")
    modelo_escolhido = col_modelo.selectbox("Modelo de IA", MODELOS_DISPONIVEIS, index=0, key="chat_modelo")
    usar_internet = col_net.toggle("Buscar na internet", value=True, key="chat_internet",
                                   help="Para perguntas livres, a IA também pesquisa na internet (manuais, fabricantes, normas).")
    with col_reset:
        st.write("")
        if st.button("🗑️ Limpar conversa", use_container_width=True):
            for k in ("chat_gemini_history", "chat_fontes"):
                st.session_state.pop(k, None)
            st.rerun()
    tag_foco = None if foco == "Toda a planta" else foco

    # --- Dúvidas frequentes ---
    with st.expander(f"❓ Dúvidas frequentes — {len(CARDAPIO)} perguntas com resposta imediata dos dados",
                     expanded=not st.session_state["chat_gemini_history"]):
        c1, c2 = st.columns([4, 1])
        busca = st.text_input("Buscar pergunta", key="chat_busca", placeholder="ex.: superaquecimento, manutenção, previsão...")
        indices = [i for i, (q, _) in enumerate(CARDAPIO)
                   if not busca.strip() or busca.strip().lower() in q.lower()]
        if not indices:
            st.caption("Nenhuma pergunta encontrada — digite sua pergunta no campo abaixo do histórico.")
            indices = list(range(len(CARDAPIO)))
        idx = c1.selectbox("Escolha a pergunta", indices, format_func=lambda i: f"{i + 1}. {CARDAPIO[i][0]}", key="chat_cardapio")
        c2.write("")
        c2.write("")
        if c2.button("Responder agora", type="primary", use_container_width=True):
            pergunta, _ = CARDAPIO[idx]
            with st.spinner("Calculando com os dados..."):
                resposta = responder_pronta(idx)
            _adicionar("user", pergunta)
            _adicionar("assistant", resposta, direto=True)
            st.rerun()
        st.caption("Estas respostas não usam a IA externa: são calculadas diretamente da telemetria, do cadastro, "
                   "do modelo de previsão, das manutenções e dos funcionários gravados no MongoDB. "
                   "Para qualquer outra pergunta, digite no campo abaixo — aí a IA varre o sistema e a internet.")

    # --- Histórico ---
    for msg in st.session_state["chat_gemini_history"]:
        _mostrar_mensagem(msg)

    # --- Pergunta livre ---
    pergunta = st.chat_input("Pergunta livre: a IA varre todo o sistema e a internet...")
    pendente = st.session_state.pop("chat_pergunta_pendente", None)
    origem = st.session_state.pop("chat_origem", None)
    if pendente and not pergunta:
        pergunta = pendente
    if not pergunta:
        return

    api_key = _obter_api_key()
    _adicionar("user", pergunta)
    with st.chat_message("user"):
        st.markdown(pergunta)

    if not api_key:
        texto = ("Chave da API do Gemini não encontrada. Configure `GEMINI_API_KEY` no `.streamlit/secrets.toml`. "
                 "Enquanto isso, use o cardápio de perguntas prontas acima.")
        with st.chat_message("assistant"):
            st.error(texto)
        _adicionar("assistant", texto)
        return

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=90_000))
    with st.chat_message("assistant"):
        with st.spinner("Varrendo o sistema" + (" e a internet..." if usar_internet else "...")):
            fontes, fontes_web = [], []
            try:
                contexto, fontes = montar_contexto(
                    pergunta, planta=st.session_state.get("planta_selecionada"), tag_foco=tag_foco, origem=origem,
                )
                texto, fontes_web = _chamar_gemini(client, modelo_escolhido, contexto, pergunta, usar_internet)
            except Exception as e:
                texto = f"⚠️ Não foi possível obter resposta da IA. Detalhe técnico: {e}"
        st.markdown(texto)
        if fontes or fontes_web:
            with st.expander("📚 Fontes consultadas"):
                for f in fontes:
                    st.markdown(f"- **{f['fonte']}** — {f['titulo']}")
                for titulo, url in fontes_web:
                    st.markdown(f"- 🌐 [{titulo}]({url})")
    _adicionar("assistant", texto, fontes=[{"fonte": f["fonte"], "titulo": f["titulo"]} for f in fontes], fontes_web=fontes_web)
