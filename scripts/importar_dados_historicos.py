"""
Script de importação dos dados históricos (Excel exportado como CSV) para
o MongoDB Atlas do projeto.

Uso:
    1. Coloque os arquivos Dados_Leituras_.csv e Dados_Tipos_de_Falha_.csv
       na mesma pasta deste script (ou ajuste os caminhos abaixo).
    2. Configure a variável de ambiente MONGODB_URI com a connection string
       do Atlas (a mesma usada no Compass / no secrets.toml do app):

         Windows (PowerShell):
             $env:MONGODB_URI="mongodb+srv://usuario:senha@seu-cluster.mongodb.net/"
         Linux/Mac:
             export MONGODB_URI="mongodb+srv://usuario:senha@seu-cluster.mongodb.net/"

    3. Rode: python scripts/importar_dados_historicos.py

O script é seguro para rodar mais de uma vez: ele limpa as coleções antes
de reimportar, então não duplica dados.
"""
import os
import sys

import pandas as pd
from pymongo import MongoClient

CAMINHO_LEITURAS = os.path.join(os.path.dirname(__file__), "Dados_Leituras_.csv")
CAMINHO_FALHAS = os.path.join(os.path.dirname(__file__), "Dados_Tipos_de_Falha_.csv")

DB_NAME = os.environ.get("MONGODB_DB_NAME", "forzy_challenge")
COLECAO_HISTORICO = "telemetria_historico"
COLECAO_FALHAS = "tipos_falha"


def classificar_status(temperatura, codigo_falha):
    """Mesma lógica de classificação usada no restante do app."""
    if codigo_falha != 0:
        return "Crítico", "🔴"
    if temperatura < 60:
        return "Normal", "🟢"
    elif temperatura < 75:
        return "Alerta", "🟡"
    else:
        return "Crítico", "🔴"


def tag_do_motor(motor_id):
    return f"MOT-{int(motor_id):03d}"


def main():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERRO: defina a variável de ambiente MONGODB_URI antes de rodar este script.")
        sys.exit(1)

    if not os.path.exists(CAMINHO_LEITURAS) or not os.path.exists(CAMINHO_FALHAS):
        print(f"ERRO: coloque Dados_Leituras_.csv e Dados_Tipos_de_Falha_.csv em: {os.path.dirname(__file__)}")
        sys.exit(1)

    print("Conectando ao MongoDB Atlas...")
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    db = client[DB_NAME]
    print(f"Conectado! Usando database '{DB_NAME}'.")

    # --- 1. Tipos de falha (tabela de referência pequena) ---
    print("Lendo Dados_Tipos_de_Falha_.csv...")
    df_falhas = pd.read_csv(CAMINHO_FALHAS, sep=";", encoding="utf-8-sig")
    df_falhas = df_falhas.rename(columns={"codigo": "codigo", "nome": "nome", "descricao": "descricao"})
    registros_falhas = df_falhas.to_dict("records")

    db[COLECAO_FALHAS].delete_many({})
    db[COLECAO_FALHAS].insert_many(registros_falhas)
    print(f"  -> {len(registros_falhas)} tipos de falha importados.")

    # --- 2. Leituras de telemetria (dataset grande) ---
    print("Lendo Dados_Leituras_.csv (pode levar alguns segundos)...")
    df = pd.read_csv(CAMINHO_LEITURAS, sep=";", decimal=",", encoding="utf-8-sig")
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print(f"  -> {len(df)} leituras encontradas para {df['motor_id'].nunique()} motores.")

    registros = []
    for _, linha in df.iterrows():
        status, indicador = classificar_status(linha["temperatura_c"], linha["falha"])
        registros.append({
            "TAG": tag_do_motor(linha["motor_id"]),
            "Temperatura": float(linha["temperatura_c"]),
            "Vibracao": float(linha["vibracao_mm_s"]),
            "Corrente": float(linha["corrente_a"]),
            "RPM": float(linha["rotacao_rpm"]),
            "FalhaCodigo": int(linha["falha"]),
            "Status": status,
            "Indicador": indicador,
            "timestamp": linha["timestamp"].to_pydatetime(),
        })

    print("Limpando histórico anterior (se houver) e inserindo os novos dados...")
    db[COLECAO_HISTORICO].delete_many({})

    # Insere em lotes para não sobrecarregar a conexão de uma vez só
    TAMANHO_LOTE = 2000
    for inicio in range(0, len(registros), TAMANHO_LOTE):
        lote = registros[inicio:inicio + TAMANHO_LOTE]
        db[COLECAO_HISTORICO].insert_many(lote)
        print(f"  -> {min(inicio + TAMANHO_LOTE, len(registros))}/{len(registros)} leituras importadas...")

    # Índices para consultas rápidas por TAG e por data
    db[COLECAO_HISTORICO].create_index([("TAG", 1), ("timestamp", -1)])

    print("\n✅ Importação concluída com sucesso!")
    print(f"   Coleção '{COLECAO_HISTORICO}': {db[COLECAO_HISTORICO].count_documents({})} documentos")
    print(f"   Coleção '{COLECAO_FALHAS}': {db[COLECAO_FALHAS].count_documents({})} documentos")


if __name__ == "__main__":
    main()