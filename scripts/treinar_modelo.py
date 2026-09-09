"""
Treina o classificador de falhas a partir de scripts/Dados_Leituras_.csv
seguindo o pipeline da Sprint 2 (janela móvel de 5 leituras por motor,
divisão cronológica 80/20 por motor, classes balanceadas) e salva em
modelos/modelo_falhas.joblib + modelo_falhas_meta.json (métricas).

Uso:  python scripts/treinar_modelo.py
"""
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.previsao import SENSORES, JANELA, NOMES_CLASSE, CAMINHO_MODELO, CAMINHO_META, nomes_features  # noqa: E402

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Dados_Leituras_.csv")
MAPA = {"rotacao_rpm": "RPM", "vibracao_mm_s": "Vibracao", "temperatura_c": "Temperatura", "corrente_a": "Corrente"}


def main():
    df = pd.read_csv(CSV, sep=";", decimal=",", encoding="utf-8-sig").rename(columns=MAPA)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["motor_id", "timestamp"]).reset_index(drop=True)

    for s in SENSORES:
        g = df.groupby("motor_id")[s]
        df[f"{s}_roll_mean"] = g.transform(lambda x: x.rolling(JANELA, min_periods=1).mean())
        df[f"{s}_roll_std"] = g.transform(lambda x: x.rolling(JANELA, min_periods=1).std().fillna(0))

    feats = nomes_features()
    tr_idx, te_idx = [], []
    for _, grupo in df.groupby("motor_id"):
        n = int(len(grupo) * 0.8)
        tr_idx += grupo.index[:n].tolist()
        te_idx += grupo.index[n:].tolist()

    X_tr, y_tr = df.loc[tr_idx, feats].values, df.loc[tr_idx, "falha"].values
    X_te, y_te = df.loc[te_idx, feats].values, df.loc[te_idx, "falha"].values

    modelo = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=20,
        l2_regularization=0.1, class_weight="balanced", early_stopping=True,
        validation_fraction=0.1, random_state=42,
    )
    modelo.fit(X_tr, y_tr)
    pred = modelo.predict(X_te)
    acc = accuracy_score(y_te, pred)
    f1 = f1_score(y_te, pred, average="macro")
    print(classification_report(y_te, pred, target_names=[NOMES_CLASSE[k] for k in sorted(NOMES_CLASSE)]))
    print(f"Acurácia: {acc:.4f} | F1-macro: {f1:.4f}")

    os.makedirs(os.path.dirname(CAMINHO_MODELO), exist_ok=True)
    joblib.dump(modelo, CAMINHO_MODELO)
    meta = {
        "modelo": "HistGradientBoostingClassifier (sklearn)",
        "features": feats, "janela": JANELA, "classes": NOMES_CLASSE,
        "acuracia_teste": round(float(acc), 4), "f1_macro_teste": round(float(f1), 4),
        "n_treino": int(len(tr_idx)), "n_teste": int(len(te_idx)),
        "treinado_em": datetime.now(timezone.utc).isoformat(),
        "relatorio": classification_report(y_te, pred, output_dict=True),
    }
    with open(CAMINHO_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"✅ Modelo salvo em {CAMINHO_MODELO}")


if __name__ == "__main__":
    main()
