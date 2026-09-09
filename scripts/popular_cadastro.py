"""
Grava o cadastro pré-pronto das 20 máquinas (MOT-001…MOT-020) no MongoDB:
dados reais das placas fotografadas (MOT-001/002/003, com foto), dados
ilustrativos para as demais, e a folha de dados WEG W22 (PDF) nos motores WEG.
Não apaga nada: só cria o que falta e completa campos vazios.

Uso:  python scripts/popular_cadastro.py            # completa sem sobrescrever
      python scripts/popular_cadastro.py --forcar   # sobrescreve os campos
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
    parser.add_argument("--forcar", action="store_true")
    args = parser.parse_args()
    _carregar_secrets_para_env()
    from features.cadastro_exemplo import popular_cadastro
    from providers.db_mongo import MongoIndisponivelError
    try:
        criados, atualizados = popular_cadastro(sobrescrever=args.forcar)
    except MongoIndisponivelError as e:
        print("ERRO:", e)
        sys.exit(1)
    print(f"✅ Cadastro: {criados} criado(s), {atualizados} atualizado(s).")


if __name__ == "__main__":
    main()
