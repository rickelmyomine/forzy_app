"""
Remove do MongoDB qualquer máquina fora do escopo do projeto (MOT-001 a
MOT-020) — cadastro, telemetria, manutenções, previsões e alertas.

Uso:  python scripts/limpar_maquinas.py
"""
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _secrets():
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            s = tomllib.load(f)
        for k in ("MONGODB_URI", "MONGODB_DB_NAME"):
            if k in s and k not in os.environ:
                os.environ[k] = str(s[k])


def main():
    _secrets()
    from providers.db_mongo import remover_maquinas_fora_do_escopo, MAQUINAS_VALIDAS
    removidos = remover_maquinas_fora_do_escopo()
    if removidos:
        for col, n in removidos.items():
            print(f"  {col}: {n} documento(s) removido(s)")
    print(f"✅ Base limpa — apenas {MAQUINAS_VALIDAS[0]} a {MAQUINAS_VALIDAS[-1]}.")


if __name__ == "__main__":
    main()
