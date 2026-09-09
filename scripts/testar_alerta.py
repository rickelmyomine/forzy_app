"""
Script de teste: insere uma leitura CRÍTICA falsa, com o horário de
agora, para você ver o scripts/monitor_alertas.py disparar o e-mail de
alerta de verdade (é útil porque, com o dataset importado, a última
leitura de todos os motores já é "Normal" — então o monitor nunca teria
nada novo pra alertar sem isso).

Uso:
    1. Configure MONGODB_URI e MONGODB_DB_NAME (mesmas variáveis do app).
    2. Deixe o scripts/monitor_alertas.py rodando em outro terminal.
    3. Rode: python scripts/testar_alerta.py
    4. Espere até 60s (ou o valor de MONITOR_INTERVALO_SEGUNDOS) — o
       e-mail deve chegar na próxima verificação do monitor.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.db_mongo import _obter_db, MongoIndisponivelError  # noqa: E402

TAG_TESTE = os.environ.get("TAG_TESTE", "MOT-001")


def main():
    db = _obter_db()
    if db is None:
        print("ERRO: não foi possível conectar ao MongoDB. Confira MONGODB_URI / MONGODB_DB_NAME.")
        sys.exit(1)

    leitura_falsa = {
        "TAG": TAG_TESTE,
        "Temperatura": 92.5,
        "Vibracao": 4.8,
        "Corrente": 22.3,
        "RPM": 1650,
        "FalhaCodigo": 2,  # Superaquecimento
        "Status": "Crítico",
        "Indicador": "🔴",
        "timestamp": datetime.now(timezone.utc),
    }

    db["telemetria_historico"].insert_one(leitura_falsa)
    print(f"✅ Leitura de teste inserida para {TAG_TESTE} (Crítico / Superaquecimento).")
    print("   Agora espere o próximo ciclo do scripts/monitor_alertas.py (até 60s).")


if __name__ == "__main__":
    main()