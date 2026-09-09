"""
Utilitários de imagem: compressão para armazenar fotos dentro do MongoDB
(base64) e conversão de volta para exibição no Streamlit.

Uma foto de celular (3–6 MB) vira ~150–300 KB após redimensionar para
1200 px e salvar em JPEG 82%, bem abaixo do limite de 16 MB por documento.
"""
import base64
import io

from PIL import Image, ImageOps

MAX_LADO_PX = 1200
QUALIDADE_JPEG = 82
MAX_LADO_MINIATURA = 320


def comprimir_para_b64(dados_bytes, max_lado=MAX_LADO_PX, qualidade=QUALIDADE_JPEG):
    """
    Recebe os bytes de uma imagem (qualquer formato suportado pelo Pillow),
    corrige a rotação EXIF, redimensiona e devolve (base64_str, mime, tamanho_bytes).
    """
    img = Image.open(io.BytesIO(dados_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_lado, max_lado))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
    conteudo = buffer.getvalue()
    return base64.b64encode(conteudo).decode("ascii"), "image/jpeg", len(conteudo)


def miniatura_b64(b64_str, max_lado=MAX_LADO_MINIATURA):
    """Gera uma miniatura (base64) a partir de uma imagem já em base64."""
    dados = base64.b64decode(b64_str)
    img = Image.open(io.BytesIO(dados))
    img.thumbnail((max_lado, max_lado))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def b64_para_bytes(b64_str):
    return base64.b64decode(b64_str)


def b64_para_data_uri(b64_str, mime="image/jpeg"):
    return f"data:{mime};base64,{b64_str}"


def tamanho_legivel(n_bytes):
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.0f} KB"
    return f"{n_bytes / (1024 * 1024):.1f} MB"
