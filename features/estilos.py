"""
Estilos de tabela: linhas em amarelo (Alerta) e vermelho (Crítico).
Usado com st.dataframe(styler).
"""
import pandas as pd

COR_ALERTA = "background-color: rgba(201,133,0,0.35); color: #fff3d6"
COR_CRITICO = "background-color: rgba(230,103,103,0.40); color: #ffe2e2"
COR_NORMAL = ""


def _cor_por_status(valor):
    v = str(valor)
    if "Crítico" in v or "Critico" in v:
        return COR_CRITICO
    if "Alerta" in v:
        return COR_ALERTA
    return COR_NORMAL


def colorir_por_status(df, coluna="Status"):
    """Retorna um Styler que pinta a linha inteira conforme a coluna de status."""
    if df is None or df.empty or coluna not in df.columns:
        return df

    def _linha(row):
        estilo = _cor_por_status(row[coluna])
        return [estilo] * len(row)

    return df.style.apply(_linha, axis=1).format(precision=2)


def colorir_por_falha(df, coluna="FalhaCodigo"):
    """Linhas com código de falha != 0 em vermelho."""
    if df is None or df.empty or coluna not in df.columns:
        return df

    def _linha(row):
        try:
            cod = int(row[coluna])
        except (TypeError, ValueError):
            cod = 0
        return [COR_CRITICO if cod else COR_NORMAL] * len(row)

    return df.style.apply(_linha, axis=1).format(precision=2)


def colorir_por_nivel(df, coluna):
    """Coluna com valores Baixo/Moderado/Alto ou percentuais de risco."""
    if df is None or df.empty or coluna not in df.columns:
        return df

    def _linha(row):
        v = str(row[coluna]).lower()
        if "alto" in v or "crítico" in v or "substituir" in v:
            e = COR_CRITICO
        elif "moderado" in v or "alerta" in v or "revisar" in v:
            e = COR_ALERTA
        else:
            e = COR_NORMAL
        return [e] * len(row)

    return df.style.apply(_linha, axis=1).format(precision=2)


# ---------------------------------------------------------------------------
# Abas "preguiçosas": ao contrário de st.tabs (que executa o conteúdo de TODAS
# as abas a cada recarregamento), aqui só a aba escolhida é calculada.
# Isso reduz muito o tempo de carregamento das telas pesadas.
def abas(rotulos, chave, padrao=0):
    """Seletor com aparência de abas. Devolve o rótulo escolhido."""
    import streamlit as st
    st.html("""
    <style>
    div[data-testid="stButtonGroup"] button{
        font-size:1.02rem !important; padding:.42rem 1.05rem !important; font-weight:600 !important;}
    div[data-testid="stButtonGroup"]{margin-bottom:.35rem;}
    </style>""")
    escolha = st.segmented_control(
        " ", rotulos, key=chave, default=rotulos[padrao], label_visibility="collapsed")
    return escolha or rotulos[padrao]
