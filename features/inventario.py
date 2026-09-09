"""
Inventário dos motores: tabela consolidada do cadastro técnico e exportação
em planilha (CSV) e em relatório (PDF).
"""
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd

from providers.db_mongo import EquipamentoRepository, TelemetriaRepository, ManutencaoRepository

COLUNAS = [
    ("TAG", "Máquina"),
    ("Fabricante", "Fabricante"),
    ("Modelo", "Modelo"),
    ("Potencia", "Potência"),
    ("Tensao", "Tensão"),
    ("Corrente", "Corrente nominal"),
    ("RPM", "Rotação nominal"),
    ("Frequencia", "Frequência"),
    ("Carcaca", "Carcaça"),
    ("GrauProtecao", "Grau de proteção"),
    ("Isolacao", "Isolação"),
    ("FatorServico", "Fator de serviço"),
    ("Peso", "Peso"),
    ("NumeroSerie", "Número de série"),
    ("Planta", "Planta"),
    ("Localizacao", "Localização"),
    ("Criticidade", "Criticidade"),
    ("AnoInstalacao", "Ano de instalação"),
    ("Observacoes", "Observações"),
]


def tabela_inventario(incluir_estado=True):
    """DataFrame do inventário: dados de placa + estado atual + última OS."""
    equipamentos = [e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")]
    if not equipamentos:
        return pd.DataFrame()
    tags = tuple(sorted(e["TAG"] for e in equipamentos))

    ultimas, os_por_tag = {}, {}
    if incluir_estado:
        try:
            ultimas = TelemetriaRepository.ultimas_leituras(tags)
        except Exception:
            ultimas = {}
        try:
            os_por_tag = ManutencaoRepository.ultimas_por_tag(tags)
        except Exception:
            os_por_tag = {}

    from features.limites import classificar_status
    linhas = []
    for e in sorted(equipamentos, key=lambda x: x["TAG"]):
        linha = {rotulo: e.get(campo) for campo, rotulo in COLUNAS}
        if incluir_estado:
            ult = ultimas.get(e["TAG"]) or {}
            if ult:
                status, _ = classificar_status(ult.get("Temperatura"), ult.get("Vibracao"),
                                               ult.get("Corrente"), ult.get("RPM"),
                                               ult.get("FalhaCodigo", 0))
                linha["Estado atual"] = status
                linha["Temperatura (°C)"] = round(float(ult["Temperatura"]), 1) if ult.get("Temperatura") is not None else None
                linha["Vibração (mm/s)"] = round(float(ult["Vibracao"]), 2) if ult.get("Vibracao") is not None else None
            else:
                linha["Estado atual"] = "sem leitura"
                linha["Temperatura (°C)"] = None
                linha["Vibração (mm/s)"] = None
            os_ = os_por_tag.get(e["TAG"])
            d = (os_ or {}).get("data")
            linha["Última manutenção"] = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else "-"
            linha["Tem foto"] = "sim" if e.get("foto") or e.get("foto_mime") else "não"
        linhas.append(linha)
    return pd.DataFrame(linhas)


def csv_inventario(df=None):
    """Planilha CSV do inventário (ponto e vírgula, vírgula decimal — abre no Excel)."""
    df = tabela_inventario() if df is None else df
    if df is None or df.empty:
        return ""
    return df.to_csv(index=False, sep=";", decimal=",")


def nome_arquivo(extensao="csv"):
    return f"{datetime.now():%Y-%m-%d}_inventario_motores.{extensao}"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def pdf_inventario(df=None, titulo="Inventário de Motores Elétricos", subtitulo=None):
    """Relatório em PDF: capa com resumo e uma tabela por bloco de colunas."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    df = tabela_inventario() if df is None else df
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=titulo, author="Forzy")
    estilos = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=estilos["Heading1"], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=estilos["Normal"], fontSize=9, textColor=colors.grey)
    cel = ParagraphStyle("cel", parent=estilos["Normal"], fontSize=7, leading=8.5)
    cab = ParagraphStyle("cab", parent=estilos["Normal"], fontSize=7, leading=8.5,
                         textColor=colors.white, fontName="Helvetica-Bold")

    elementos = [Paragraph(titulo, h1)]
    agora = datetime.now(timezone.utc).astimezone()
    elementos.append(Paragraph(
        subtitulo or f"Emitido em {agora:%d/%m/%Y %H:%M} · {len(df)} máquina(s) cadastrada(s)", sub))
    elementos.append(Spacer(1, 8))

    if df.empty:
        elementos.append(Paragraph("Nenhum equipamento cadastrado.", estilos["Normal"]))
        doc.build(elementos)
        return buffer.getvalue()

    # Resumo por estado
    if "Estado atual" in df.columns:
        resumo = df["Estado atual"].value_counts().to_dict()
        texto = " · ".join(f"{k}: {v}" for k, v in resumo.items())
        elementos.append(Paragraph(f"<b>Estado atual da planta:</b> {texto}", cel))
        elementos.append(Spacer(1, 8))

    cores_estado = {"Crítico": colors.HexColor("#f8d7da"),
                    "Alerta": colors.HexColor("#fff3cd"),
                    "Normal": colors.HexColor("#d7f5e3")}

    # Quebra as colunas em blocos que caibam na página, sempre repetindo a TAG
    colunas = [c for c in df.columns if c != "Máquina"]
    blocos = [colunas[i:i + 7] for i in range(0, len(colunas), 7)]
    for n, bloco in enumerate(blocos, start=1):
        if n > 1:
            elementos.append(Spacer(1, 10))
        elementos.append(Paragraph(f"Bloco {n} de {len(blocos)}", sub))
        elementos.append(Spacer(1, 4))
        cabecalho = [Paragraph("Máquina", cab)] + [Paragraph(str(c), cab) for c in bloco]
        dados = [cabecalho]
        estilo_linhas = []
        for i, (_, linha) in enumerate(df.iterrows(), start=1):
            valores = [Paragraph(f"<b>{linha['Máquina']}</b>", cel)]
            for c in bloco:
                v = linha.get(c)
                valores.append(Paragraph("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v), cel))
            dados.append(valores)
            cor = cores_estado.get(str(linha.get("Estado atual")))
            if cor:
                estilo_linhas.append(("BACKGROUND", (0, i), (-1, i), cor))
        largura = doc.width
        larguras = [largura * 0.10] + [(largura * 0.90) / len(bloco)] * len(bloco)
        tabela = Table(dados, colWidths=larguras, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2f45")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9bcc7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ] + estilo_linhas))
        elementos.append(tabela)

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        "Linhas em vermelho: máquina em estado crítico. Em amarelo: em alerta. Em verde: normal. "
        "Estado apurado pela última leitura de telemetria gravada.", sub))

    doc.build(elementos)
    return buffer.getvalue()
