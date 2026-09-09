"""
Placas de QR Code das máquinas.

Cada máquina ganha uma etiqueta para imprimir e colar no motor. Ao ler o QR
com o celular, o app abre já na máquina correspondente (parâmetro ?tag= na
URL), mostrando o painel e permitindo abrir a OS na hora.

O endereço usado no QR vem, nesta ordem:
  1. do campo preenchido na tela;
  2. de APP_URL no .streamlit/secrets.toml;
  3. do endereço local (só funciona no computador que roda o app).
"""
import os
import zipfile
from datetime import datetime
from io import BytesIO

URL_LOCAL = "http://localhost:8501"


def url_configurada():
    try:
        import streamlit as st
        if "APP_URL" in st.secrets and st.secrets["APP_URL"]:
            return str(st.secrets["APP_URL"]).rstrip("/")
    except Exception:
        pass
    return (os.environ.get("APP_URL") or URL_LOCAL).rstrip("/")


def link_maquina(tag, base=None):
    return f"{(base or url_configurada()).rstrip('/')}/?tag={tag}"


# ---------------------------------------------------------------------------
def qr_png(texto, tamanho_caixa=10, borda=2):
    """QR Code como PNG (bytes)."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                       box_size=tamanho_caixa, border=borda)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fonte(tamanho, negrito=False):
    from PIL import ImageFont
    caminhos = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrito
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if negrito else "C:/Windows/Fonts/arial.ttf",
    ]
    for c in caminhos:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, tamanho)
            except Exception:
                pass
    return ImageFont.load_default()


def placa_png(tag, equipamento=None, base=None, largura=760, altura=440):
    """Etiqueta pronta para imprimir: TAG, dados de placa e o QR Code."""
    from PIL import Image, ImageDraw
    e = equipamento or {}
    img = Image.new("RGB", (largura, altura), "white")
    d = ImageDraw.Draw(img)

    # moldura
    d.rounded_rectangle([6, 6, largura - 7, altura - 7], radius=16, outline=(20, 20, 20), width=4)
    # faixa do topo
    d.rounded_rectangle([6, 6, largura - 7, 92], radius=16, fill=(24, 26, 42))
    d.rectangle([6, 70, largura - 7, 92], fill=(24, 26, 42))
    d.text((28, 24), tag, font=_fonte(44, True), fill="white")
    d.text((28, 66), "MANUTENÇÃO PREDITIVA · FORZY", font=_fonte(15), fill=(170, 175, 200))

    # QR
    qr = Image.open(BytesIO(qr_png(link_maquina(tag, base), tamanho_caixa=10, borda=1)))
    lado = altura - 140
    qr = qr.resize((lado, lado))
    img.paste(qr, (largura - lado - 30, 112))

    # dados
    y = 118
    linhas = [
        (f"{e.get('Fabricante', '')} {e.get('Modelo', '')}".strip() or "Motor elétrico", 22, True),
        (f"Potência: {e.get('Potencia', '-')}", 18, False),
        (f"Tensão: {e.get('Tensao', '-')}", 18, False),
        (f"Rotação: {e.get('RPM', '-')}", 18, False),
        (f"Planta: {e.get('Planta', '-')}", 18, False),
        (f"Criticidade: {e.get('Criticidade', '-')}", 18, False),
    ]
    for texto, tam, negrito in linhas:
        d.text((30, y), texto[:38], font=_fonte(tam, negrito), fill=(20, 20, 20))
        y += tam + 12

    d.text((30, altura - 56), "Aponte a câmera do celular", font=_fonte(15, True), fill=(60, 60, 60))
    d.text((30, altura - 34), "para ver o painel e abrir a OS", font=_fonte(15), fill=(90, 90, 90))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
def zip_placas(equipamentos, base=None):
    """ZIP com uma etiqueta PNG por máquina."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for e in equipamentos:
            tag = e.get("TAG")
            if not tag:
                continue
            z.writestr(f"placa_{tag}.png", placa_png(tag, e, base))
    return buf.getvalue()


def pdf_placas(equipamentos, base=None, por_pagina=4):
    """Folha A4 com as etiquetas prontas para imprimir e recortar."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    largura_pg, altura_pg = A4
    margem = 12 * mm
    largura = largura_pg - 2 * margem
    altura = (altura_pg - 2 * margem) / por_pagina - 4 * mm

    validos = [e for e in equipamentos if e.get("TAG")]
    for i, e in enumerate(validos):
        pos = i % por_pagina
        if pos == 0 and i:
            c.showPage()
        y = altura_pg - margem - (pos + 1) * (altura + 4 * mm)
        png = placa_png(e["TAG"], e, base)
        c.drawImage(ImageReader(BytesIO(png)), margem, y, width=largura, height=altura,
                    preserveAspectRatio=True, anchor="c", mask="auto")
        c.setDash(2, 3)
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.line(margem, y - 2 * mm, largura_pg - margem, y - 2 * mm)
        c.setDash()
    c.save()
    return buf.getvalue()


def nome_arquivo(extensao="zip"):
    return f"{datetime.now():%Y-%m-%d}_placas_qrcode.{extensao}"
