"""
Cadastro pré-pronto das 20 máquinas (MOT-001 a MOT-020).

MOT-001, MOT-002 e MOT-003 usam os dados reais lidos das placas fotografadas
(assets/mot-00X.jpg). As demais seguem o fabricante/modelo/potência que já
estavam no cadastro importado do Motor.xlsx, com dados de placa de referência. Motores WEG W22 recebem a folha de
dados real do fabricante (assets/WEG_W22_datasheet.pdf).
"""
import base64
import os
from datetime import datetime, timezone

from providers.db_mongo import EquipamentoRepository

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

SITES = {
    "WEG": "https://www.weg.net/institutional/BR/pt/",
    "Siemens": "https://www.siemens.com/br/pt/produtos/acionamentos/motores.html",
    "ABB": "https://new.abb.com/motors-generators",
    "Toshiba": "https://www.toshiba.com/tic/motors-drives",
}

# TAG: (Fabricante, Modelo, Potencia, Tensao, Corrente, RPM, NumeroSerie, Planta, Criticidade, Ano, Observacoes, foto, pdf)
MAQUINAS = {
    "MOT-001": ("WEG", "W22 Premium", "2,2 kW (3,0 cv)", "220/380 V", "8,25/4,78 A", "1745", "1059634764",
                "Planta Matriz - SP", "A - Alta", 2021,
                "Trifásico, carcaça L90L, 60 Hz, FS 1,25, isolação F, IP55, rendimento 87,5 %, 26 kg. "
                "Rolamentos 6205-ZZ / 6204-ZZ, graxa Mobil Polyrex EM. Marcação de campo: M273.",
                "mot-001.jpg", True),
    "MOT-002": ("WEG", "W22 Gaiola 2 velocidades", "0,46/0,75 kW (0,63/1,0 cv)", "220 V", "3,77/3,04 A", "870/1750",
                "1129176649", "Planta Matriz - SP", "B - Média", 2026,
                "Trifásico Dahlander, carcaça 90L, 60 Hz, FS 1,00, isolação F, IP55, 28 kg. Com freio eletromagnético "
                "220–240 V. Rolamentos 6205-ZZ / 6204-ZZ, graxa à base de poliureia. Fabricação 09/06/2026.",
                "mot-002.jpg", True),
    "MOT-003": ("WEG", "Motor de indução trifásico mod. 71", "0,33 cv", "220/380 V", "1,8/1,0 A", "1100", "",
                "Planta Matriz - SP", "C - Baixa", 2005,
                "Motor antigo (NBR 7094), 60 Hz, FS 1,35, isolação B, IP54, Ip/In 3,1. Carcaça com oxidação superficial; "
                "avaliar substituição em caso de falha.",
                "mot-003.jpg", False),
}

_LEGADO = {
    4: ("WEG", "W22", 7.5, 2018), 5: ("Siemens", "1LE0", 11, 2022), 6: ("ABB", "M3BP", 18.5, 2025),
    7: ("WEG", "W22", 15, 2020), 8: ("WEG", "W22", 7.5, 2019), 9: ("Siemens", "1LE0", 7.5, 2021),
    10: ("Toshiba", "EQP-Global", 11, 2020), 11: ("ABB", "M3BP", 15, 2019), 12: ("WEG", "W22", 18.5, 2025),
    13: ("Siemens", "1LE0", 15, 2020), 14: ("ABB", "M3BP", 11, 2018), 15: ("Toshiba", "EQP-Global", 7.5, 2022),
    16: ("WEG", "W22", 22, 2019), 17: ("Siemens", "1LE0", 18.5, 2021), 18: ("ABB", "M3BP", 22, 2018),
    19: ("Toshiba", "EQP-Global", 22, 2021), 20: ("WEG", "W22", 11, 2021),
}

# corrente nominal aproximada em 380 V (A) por potência (kW)
_CORRENTE_380 = {7.5: "15,2 A", 11: "21,5 A", 15: "28,7 A", 18.5: "35,0 A", 22: "41,5 A"}
_CRITICIDADE = {7.5: "C - Baixa", 11: "B - Média", 15: "B - Média", 18.5: "A - Alta", 22: "A - Alta"}


def _ler_b64(nome):
    caminho = os.path.join(_ASSETS, nome)
    if not os.path.exists(caminho):
        return None
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _documento(tag, dados, foto_nome, com_pdf):
    fab, mod, pot, ten, cor, rpm, serie, planta, crit, ano, obs = dados
    doc = {
        "TAG": tag, "Fabricante": fab, "Modelo": mod, "Potencia": pot, "Tensao": ten, "Corrente": cor,
        "RPM": rpm, "NumeroSerie": serie, "Planta": planta, "Criticidade": crit, "AnoInstalacao": ano,
        "Observacoes": obs, "site_url": SITES.get(fab, ""),
        "cadastrado_por": "Cadastro de exemplo", "cadastrado_em": datetime.now(timezone.utc),
    }
    if foto_nome:
        from features.imagens import comprimir_para_b64
        caminho = os.path.join(_ASSETS, foto_nome)
        if os.path.exists(caminho):
            with open(caminho, "rb") as f:
                b64, mime, _ = comprimir_para_b64(f.read())
            doc.update({"foto": b64, "foto_mime": mime, "foto_atualizada_em": datetime.now(timezone.utc)})
    if com_pdf:
        pdf = _ler_b64("WEG_W22_datasheet.pdf")
        if pdf:
            doc.update({"datasheet_pdf": pdf, "datasheet_nome": "WEG_W22_datasheet.pdf"})
    return doc


def documentos_exemplo():
    docs = []
    for tag, dados in MAQUINAS.items():
        docs.append(_documento(tag, dados[:11], dados[11], dados[12]))
    for mid, (fab, mod, kw, ano) in _LEGADO.items():
        tag = f"MOT-{mid:03d}"
        planta = "Planta Matriz - SP" if mid <= 10 else "Planta Filial - MG"
        obs = f"Motor trifásico {kw:g} kW, 4 polos, 60 Hz, IP55, isolação F. Dados de placa de referência."
        dados = (fab, mod, f"{kw:g} kW", "380 V", _CORRENTE_380.get(kw, ""), "1750",
                 f"{fab[:2].upper()}{mid:03d}{ano}", planta, _CRITICIDADE.get(kw, "B - Média"), ano, obs)
        docs.append(_documento(tag, dados, None, fab == "WEG"))
    return docs


def popular_cadastro(sobrescrever=False):
    """
    Grava/atualiza as 20 máquinas. Sem `sobrescrever`, preserva campos já
    preenchidos (só completa o que falta — inclusive foto e PDF).
    Retorna (criados, atualizados).
    """
    EquipamentoRepository.migrar_cadastro_legado()
    criados = atualizados = 0
    for doc in documentos_exemplo():
        tag = doc["TAG"]
        atual = EquipamentoRepository.buscar_por_tag(tag)
        if atual is None:
            EquipamentoRepository.salvar(doc)
            criados += 1
        else:
            # MOT-001/002/003 vêm das placas reais fotografadas: seus dados de
            # placa sempre prevalecem sobre o cadastro legado (Motor.xlsx).
            if sobrescrever or tag in MAQUINAS:
                campos = {k: v for k, v in doc.items() if k != "TAG"}
                if not sobrescrever:
                    for k in ("Planta", "Criticidade", "cadastrado_por", "cadastrado_em"):
                        if atual.get(k):
                            campos.pop(k, None)
            else:
                campos = {k: v for k, v in doc.items() if k != "TAG" and not atual.get(k)}
            if campos:
                EquipamentoRepository.atualizar(tag, campos, usuario="Cadastro de exemplo")
                atualizados += 1
    return criados, atualizados
