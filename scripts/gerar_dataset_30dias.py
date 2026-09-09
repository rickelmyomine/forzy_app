"""
Gera e importa no MongoDB Atlas a telemetria sintética dos últimos 30 dias
para as 20 máquinas (MOT-001 a MOT-020), uma leitura a cada 10 minutos
(~86 mil documentos). Os documentos recebem origem="sintetico_30d"; rodar de
novo apaga só esses e regenera — as leituras importadas do CSV permanecem.

Uso (com MONGODB_URI / MONGODB_DB_NAME configurados ou no secrets.toml):
    python scripts/gerar_dataset_30dias.py            # 30 dias
    python scripts/gerar_dataset_30dias.py --dias 7   # outro período
"""
import argparse
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _carregar_secrets_para_env():
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            s = tomllib.load(f)
        for k in ("MONGODB_URI", "MONGODB_DB_NAME"):
            if k in s and k not in os.environ:
                os.environ[k] = str(s[k])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=30)
    parser.add_argument("--passo", type=int, default=10, help="minutos entre leituras")
    args = parser.parse_args()

    _carregar_secrets_para_env()
    from features.gerador_dados import gerar_leituras, periodo_ultimos_dias
    from providers.db_mongo import TelemetriaRepository, MongoIndisponivelError

    inicio, fim = periodo_ultimos_dias(args.dias)
    tags = [f"MOT-{i:03d}" for i in range(1, 21)]
    print(f"Gerando {args.dias} dias ({inicio:%d/%m %H:%M} → {fim:%d/%m %H:%M}) para {len(tags)} máquinas...")
    registros = gerar_leituras(tags, inicio, fim, passo_minutos=args.passo)
    print(f"  -> {len(registros)} leituras geradas. Enviando ao MongoDB...")
    try:
        n = TelemetriaRepository.substituir_sinteticos(registros)
    except MongoIndisponivelError as e:
        print("ERRO:", e)
        sys.exit(1)
    print(f"✅ {n} leituras importadas em telemetria_historico (origem=sintetico_30d).")


if __name__ == "__main__":
    main()
