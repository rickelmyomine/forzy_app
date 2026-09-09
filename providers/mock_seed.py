"""
Popular o MongoDB em memória (modo FORZY_USE_MOCK_DB=1) com dados no mesmo
formato do Atlas do projeto, para desenvolvimento sem acesso à nuvem.
"""
import os
from datetime import datetime

import pandas as pd


def popular(client, db_name):
    db = client[db_name]
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

    # tipos de falha
    caminho_falhas = os.path.join(base, "Dados_Tipos_de_Falha_.csv")
    if os.path.exists(caminho_falhas):
        df = pd.read_csv(caminho_falhas, sep=";", encoding="utf-8-sig")
        db["tipos_falha"].insert_many(df.to_dict("records"))

    # telemetria sintética (últimos N dias, mesmo gerador do script oficial)
    # A telemetria de 30 dias é gerada pela preparação automática do app
    # (features/preparacao.py), igual ao que acontece no Atlas na 1ª execução.

    # cadastro no formato legado (Motor.xlsx) + 1 no formato do app
    legados = [
        (1, "Siemens", "1LE0", 22, 2019), (2, "ABB", "M3BP", 22, 2020), (3, "Toshiba", "EQP-Global", 15, 2025),
        (4, "WEG", "W22", 7.5, 2018), (5, "Siemens", "1LE0", 11, 2022), (6, "ABB", "M3BP", 18.5, 2025),
        (7, "WEG", "W22", 15, 2020), (8, "WEG", "W22", 7.5, 2019), (9, "Siemens", "1LE0", 7.5, 2021),
        (10, "Toshiba", "EQP-Global", 11, 2020), (11, "ABB", "M3BP", 15, 2019), (12, "WEG", "W22", 18.5, 2025),
        (13, "Siemens", "1LE0", 15, 2020), (14, "ABB", "M3BP", 11, 2018), (15, "Toshiba", "EQP-Global", 7.5, 2022),
        (16, "WEG", "W22", 22, 2019), (17, "Siemens", "1LE0", 18.5, 2021), (18, "ABB", "M3BP", 22, 2018),
        (19, "Toshiba", "EQP-Global", 22, 2021), (20, "WEG", "W22", 11, 2021),
    ]
    db["cadastro_equipamentos"].insert_many([
        {"motor_id": i, "fabricante": f, "modelo": m, "potencia_kw": p, "ano_instalacao": a}
        for i, f, m, p, a in legados
    ])
    db["cadastro_equipamentos"].insert_one(
        {"TAG": "MOT-021", "Modelo": "W22 Plus", "Fabricante": "WEG Equipamentos", "Potencia": "10 cv", "Tensao": "380 V"}
    )
