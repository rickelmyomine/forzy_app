import re
from datetime import datetime, timezone

from providers.db_mongo import EquipamentoRepository, MongoIndisponivelError

PADRAO_TAG = r"^[A-Z]{3}-\d{3}$"


def validar_tag(tag):
    return bool(re.match(PADRAO_TAG, (tag or "").strip().upper()))


def cadastrar_equipamento(tag, modelo, fabricante, potencia, tensao, extras=None, usuario=None):
    """
    Função responsável por validar a entrada (segurança) e salvar via repositório.
    `extras` recebe os demais campos da placa/localização (Corrente, RPM,
    Carcaca, Planta, Area, foto, ...).
    """
    tag = (tag or "").strip().upper()
    if not validar_tag(tag):
        return False, "Formato de TAG inválido. Use o padrão industrial (Ex: MOT-001, BMB-123)."

    try:
        if EquipamentoRepository.tag_existe(tag):
            return False, f"A TAG {tag} já está cadastrada no sistema."

        novo_equipamento = {
            "TAG": tag,
            "Modelo": modelo,
            "Fabricante": fabricante,
            "Potencia": potencia,
            "Tensao": tensao,
            "cadastrado_em": datetime.now(timezone.utc),
        }
        if usuario:
            novo_equipamento["cadastrado_por"] = usuario
        if extras:
            for k, v in extras.items():
                if v not in (None, ""):
                    novo_equipamento[k] = v

        EquipamentoRepository.salvar(novo_equipamento)
    except MongoIndisponivelError as e:
        return False, str(e)

    return True, "Equipamento cadastrado com sucesso!"
