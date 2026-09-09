"""
Migra os 20 motores importados do Motor.xlsx (sem TAG) para o formato do
app: adiciona TAG = MOT-0XX a partir do motor_id e os campos Fabricante,
Modelo, Potencia, AnoInstalacao. Não apaga nada. Pode rodar mais de uma vez.

Uso (com MONGODB_URI e MONGODB_DB_NAME configurados):
    python scripts/migrar_cadastro.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.db_mongo import EquipamentoRepository, MongoIndisponivelError  # noqa: E402


def main():
    try:
        pendentes = EquipamentoRepository.contar_sem_tag()
        print(f"Documentos sem TAG: {pendentes}")
        n = EquipamentoRepository.migrar_cadastro_legado()
        print(f"✅ {n} equipamento(s) migrado(s). TAGs agora: {EquipamentoRepository.listar_tags()}")
    except MongoIndisponivelError as e:
        print("ERRO:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
