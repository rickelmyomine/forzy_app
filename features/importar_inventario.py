"""
Importação de inventário vindo de outro sistema (CSV ou Excel).

Reconhece os nomes de coluna mais comuns, normaliza a TAG para o formato
MOT-0XX e grava no cadastro técnico sem apagar o que já existe.
"""
import re
from datetime import datetime, timezone

import pandas as pd

from providers.db_mongo import EquipamentoRepository

APELIDOS = {
    "TAG": ["tag", "maquina", "máquina", "motor", "motor_id", "equipamento", "ativo",
            "id", "codigo", "código", "asset"],
    "Fabricante": ["fabricante", "marca", "manufacturer", "brand"],
    "Modelo": ["modelo", "model", "tipo_modelo"],
    "Potencia": ["potencia", "potência", "potencia_kw", "kw", "cv", "power"],
    "Tensao": ["tensao", "tensão", "volts", "v", "voltage"],
    "Corrente": ["corrente", "corrente_a", "amperes", "amps", "current"],
    "RPM": ["rpm", "rotacao", "rotação", "rotacao_rpm", "velocidade", "speed"],
    "Frequencia": ["frequencia", "frequência", "hz"],
    "Carcaca": ["carcaca", "carcaça", "frame"],
    "GrauProtecao": ["grauprotecao", "grau_protecao", "ip", "protecao", "proteção"],
    "Isolacao": ["isolacao", "isolação", "classe_isolacao", "insulation"],
    "FatorServico": ["fatorservico", "fator_servico", "fs", "service_factor"],
    "Peso": ["peso", "weight", "massa"],
    "NumeroSerie": ["numeroserie", "numero_serie", "n_serie", "serie", "série", "serial",
                    "serial_number", "ns"],
    "Planta": ["planta", "unidade", "fabrica", "fábrica", "site", "plant"],
    "Localizacao": ["localizacao", "localização", "local", "setor", "area", "área", "linha"],
    "Criticidade": ["criticidade", "classe", "prioridade", "criticality"],
    "AnoInstalacao": ["ano", "anoinstalacao", "ano_instalacao", "instalado_em", "year"],
    "Observacoes": ["observacoes", "observações", "obs", "notas", "comentarios", "notes"],
}

CAMPOS_TEXTO = [c for c in APELIDOS if c != "TAG"]


def _normalizar(nome):
    txt = str(nome).strip().lower()
    txt = re.sub(r"[\s\-.]+", "_", txt)
    return txt.strip("_")


def mapear_colunas(df):
    """{coluna original: campo do sistema}"""
    mapa = {}
    usados = set()
    for col in df.columns:
        chave = _normalizar(col)
        for destino, apelidos in APELIDOS.items():
            if destino in usados:
                continue
            if chave in [_normalizar(a) for a in apelidos]:
                mapa[col] = destino
                usados.add(destino)
                break
    return mapa


def ler_planilha(arquivo):
    """Lê CSV ou Excel. Devolve (df, mapa_de_colunas, faltando_tag)."""
    nome = (getattr(arquivo, "name", "") or "").lower()
    if nome.endswith((".xlsx", ".xls")):
        df = pd.read_excel(arquivo)
    else:
        conteudo = arquivo.read() if hasattr(arquivo, "read") else arquivo
        if isinstance(conteudo, bytes):
            texto = conteudo.decode("utf-8-sig", errors="replace")
        else:
            texto = conteudo
        import io
        separador = ";" if texto.count(";") > texto.count(",") else ","
        df = pd.read_csv(io.StringIO(texto), sep=separador)
    df.columns = [str(c).strip() for c in df.columns]
    mapa = mapear_colunas(df)
    return df, mapa, "TAG" not in mapa.values()


def normalizar_tag(valor):
    """'7', 'mot 7', 'MOT-007', 'motor_07' → 'MOT-007'."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip().upper()
    if not texto:
        return None
    numeros = re.findall(r"\d+", texto)
    if numeros and re.fullmatch(r"(MOT(OR)?[\s_\-]*)?0*\d+", texto.replace(" ", "")):
        return f"MOT-{int(numeros[-1]):03d}"
    if re.fullmatch(r"MOT-\d{3}", texto):
        return texto
    return texto[:30]


def _limpar(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    texto = str(valor).strip()
    return texto or None


def importar(df, mapa, sobrescrever=False, usuario=None):
    """
    Grava as linhas no cadastro técnico.
    Retorna (criados, atualizados, ignorados).
    """
    coluna_tag = next((o for o, d in mapa.items() if d == "TAG"), None)
    if coluna_tag is None:
        return 0, 0, len(df)

    criados = atualizados = ignorados = 0
    agora = datetime.now(timezone.utc)
    for _, linha in df.iterrows():
        tag = normalizar_tag(linha.get(coluna_tag))
        if not tag:
            ignorados += 1
            continue
        dados = {}
        for origem, destino in mapa.items():
            if destino == "TAG":
                continue
            valor = _limpar(linha.get(origem))
            if valor is not None:
                dados[destino] = valor
        dados["importado_em"] = agora
        dados["importado_por"] = usuario or "-"
        dados["origem_cadastro"] = "inventario_importado"

        existente = EquipamentoRepository.buscar_por_tag(tag)
        if existente:
            if not sobrescrever:
                dados = {k: v for k, v in dados.items()
                         if k in ("importado_em", "importado_por", "origem_cadastro")
                         or not existente.get(k)}
            EquipamentoRepository.atualizar(tag, dados, usuario=usuario)
            atualizados += 1
        else:
            EquipamentoRepository.salvar({
                "TAG": tag, **dados,
                "cadastrado_por": usuario or "-", "cadastrado_em": agora,
            })
            criados += 1
    return criados, atualizados, ignorados
