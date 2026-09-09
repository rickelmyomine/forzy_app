"""
Vídeo de apresentação (Second Corporation) exibido logo após o login,
ocupando a tela inteira por 10 segundos, antes de abrir o app.

O navegador não permite entrar em tela cheia sem um gesto do usuário, então:
- o vídeo é exibido em tela cheia "visual" (ocupa toda a janela, sem barra
  lateral, sem cabeçalho e sem margens);
- há o botão "⛶ Tela cheia real" para o modo fullscreen do navegador.
"""
import os
import time

import streamlit as st
import streamlit.components.v1 as components

VIDEO = os.path.join("assets", "second_corporation.mp4")
DURACAO = 10

_CSS = """
<style>
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {display: none !important;}
  .stApp {background: #06080f;}
  .block-container, [data-testid="stMainBlockContainer"] {padding: 0 !important; max-width: 100% !important;}
  [data-testid="stMain"] {overflow: hidden;}
  video, video[data-testid="stVideo"] {
      width: 100vw !important; height: 92vh !important; max-height: 92vh;
      object-fit: contain; background: #06080f; display: block;
  }
  .intro-rodape {
      position: fixed; bottom: 18px; left: 0; right: 0; z-index: 999;
      display: flex; gap: 12px; justify-content: center; align-items: center;
      font-family: 'Segoe UI', sans-serif; color: #cfd4e2; font-size: 0.95rem;
  }
  .intro-rodape .stButton > button {padding: 0.25rem 1.1rem;}
</style>
"""

_JS_FULLSCREEN = """
<script>
  const doc = window.parent && window.parent.document ? window.parent.document : null;
  if (doc) {
    const v = doc.querySelector('video');
    if (v) {
      v.muted = false;
      const play = v.play();
      if (play && play.catch) { play.catch(() => { v.muted = true; v.play().catch(() => {}); }); }
    }
  }
</script>
"""


def intro_pendente():
    return st.session_state.get("intro_pendente", False) and os.path.exists(VIDEO)


@st.fragment(run_every=1)
def _rodape():
    inicio = st.session_state.get("intro_inicio") or time.time()
    restante = max(0, DURACAO - int(time.time() - inicio))
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.markdown(f"Abrindo o sistema em **{restante} s**…")
    if c2.button("⛶ Tela cheia", key="btn_fs_intro", use_container_width=True):
        components.html(
            """<script>
                 const doc = window.parent.document;
                 const v = doc.querySelector('video');
                 if (v && v.requestFullscreen) { v.requestFullscreen(); }
               </script>""", height=0)
    pular = c3.button("Pular ▶", key="btn_pular_intro", use_container_width=True)
    if restante <= 0 or pular:
        st.session_state["intro_pendente"] = False
        st.rerun(scope="app")


def render_intro():
    st.session_state.setdefault("intro_inicio", time.time())
    st.html(_CSS)
    st.video(VIDEO, autoplay=True, muted=False)
    components.html(_JS_FULLSCREEN, height=0)
    _rodape()
