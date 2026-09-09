import streamlit as st

def init_state():
    # O cadastro de equipamentos agora é persistido no MongoDB Atlas
    # (ver providers/db_mongo.py), não precisa mais de mock em memória.

    # --- Estados da Sprint de Visualização ---
    if 'planta_selecionada' not in st.session_state:
        st.session_state['planta_selecionada'] = None
    if 'area_selecionada' not in st.session_state:
        st.session_state['area_selecionada'] = None