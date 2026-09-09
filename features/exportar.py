"""
Geração de datasets em CSV a partir de qualquer tela.

Um único componente (`bloco_exportar`) desenha, no fim da página, o botão de
gerar o arquivo. Ao gerar, o dataset é:
  1. oferecido para download, com o nome começando por ANO-MÊS-DIA;
  2. registrado na biblioteca (Coleta de Dados → Biblioteca), para que possa
     ser reencontrado e baixado de novo sem refazer a consulta.
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from providers.db_mongo import DatasetRepository

COLUNAS_PADRAO = ["TAG", "timestamp", "Temperatura", "Vibracao", "Corrente", "RPM",
                  "FalhaCodigo", "Status", "origem"]

ROTULOS = {"TAG": "Maquina", "timestamp": "DataHora", "Vibracao": "Vibracao_mm_s",
           "Temperatura": "Temperatura_C", "Corrente": "Corrente_A", "RPM": "Rotacao_RPM",
           "FalhaCodigo": "Falha_Codigo", "Status": "Estado", "origem": "Origem"}


def nome_dataset(contexto="telemetria", referencia=None, sufixo=None):
    """Nome do arquivo começando por ano-mês-dia: 2026-09-08_telemetria_MOT-001.csv"""
    ref = referencia or datetime.now()
    data = ref.strftime("%Y-%m-%d")
    partes = [data, contexto]
    if sufixo:
        partes.append(str(sufixo))
    return "_".join(p for p in partes if p) + ".csv"


def preparar_csv(df, colunas=None):
    """DataFrame → texto CSV (ponto e vírgula, vírgula decimal, cabeçalho legível)."""
    if df is None or df.empty:
        return ""
    colunas = [c for c in (colunas or COLUNAS_PADRAO) if c in df.columns] or list(df.columns)
    saida = df[colunas].copy()
    if "timestamp" in saida.columns:
        saida["timestamp"] = pd.to_datetime(saida["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    saida = saida.rename(columns=ROTULOS)
    return saida.to_csv(index=False, sep=";", decimal=",")


def bloco_exportar(df, contexto, chave, referencia=None, sufixo=None, colunas=None,
                   descricao=None, origem_tela=None, maquinas=None):
    """
    Desenha o bloco 'Gerar dataset' no fim de uma página.

    df         DataFrame com as leituras já filtradas pela tela
    contexto   parte do nome do arquivo (ex.: 'telemetria', 'comparacao')
    chave      prefixo único das chaves dos widgets desta tela
    """
    st.divider()
    st.subheader("📦 Gerar dataset (CSV)")
    st.caption(descricao or "Exporta exatamente o que está sendo exibido acima. O arquivo fica também "
                            "guardado em **Coleta de Dados → Biblioteca**, para baixar de novo quando quiser.")
    if df is None or df.empty:
        st.info("Sem leituras para exportar no filtro atual.")
        return

    nome = nome_dataset(contexto, referencia, sufixo)
    c1, c2 = st.columns([2, 1])
    c1.markdown(f"**{len(df):,}** leituras · arquivo `{nome}`".replace(",", "."))

    if c2.button("📦 Gerar dataset", key=f"{chave}_gerar", type="primary", use_container_width=True):
        csv_texto = preparar_csv(df, colunas)
        st.session_state[f"{chave}_csv"] = csv_texto
        st.session_state[f"{chave}_nome"] = nome
        try:
            from auth.auth import nome_usuario_atual
            usuario = nome_usuario_atual()
        except Exception:
            usuario = "-"
        tags = sorted(set(maquinas or (df["TAG"].unique() if "TAG" in df.columns else [])))
        DatasetRepository.registrar(nome, csv_texto, {
            "origem_tela": origem_tela or contexto,
            "maquinas": list(tags),
            "qtd_maquinas": len(tags),
            "gerado_por": usuario,
        })
        st.success(f"Dataset gerado e guardado na biblioteca: **{nome}**")

    csv_pronto = st.session_state.get(f"{chave}_csv")
    if csv_pronto:
        st.download_button(f"⬇️ Baixar {st.session_state.get(f'{chave}_nome', nome)}",
                           csv_pronto.encode("utf-8-sig"),
                           file_name=st.session_state.get(f"{chave}_nome", nome),
                           mime="text/csv", key=f"{chave}_baixar", use_container_width=True)
