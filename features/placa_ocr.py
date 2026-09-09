"""
Leitura da placa de identificação do motor (OCR) com o Gemini (visão).

Substitui a simulação de OCR da versão anterior: a foto da placa é enviada
ao modelo, que devolve os campos em JSON. Se a chave do Gemini não estiver
configurada ou a chamada falhar, retorna (None, motivo) e a tela cai para
preenchimento manual — o cadastro nunca fica bloqueado pela IA.
"""
import json
import os
import re

import streamlit as st

CAMPOS_PLACA = [
    "Fabricante", "Modelo", "Potencia", "Tensao", "Corrente", "RPM",
    "Frequencia", "Carcaca", "GrauProtecao", "Isolacao", "FatorServico",
    "Peso", "NumeroSerie", "Rendimento", "FatorPotencia", "Observacoes",
]

_PROMPT = """Você é um assistente de manutenção industrial. A imagem é a placa de
identificação (nameplate) de um motor elétrico. Extraia os dados e responda
SOMENTE com um JSON válido, sem comentários, com exatamente estas chaves
(use string vazia quando o campo não existir na placa):

{
  "Fabricante": "ex: WEG",
  "Modelo": "ex: W22 Premium",
  "Potencia": "ex: 2,2 kW (3,0 cv)  — inclua kW e cv se ambos aparecerem",
  "Tensao": "ex: 220/380 V",
  "Corrente": "ex: 8,25/4,78 A",
  "RPM": "ex: 1745",
  "Frequencia": "ex: 60 Hz",
  "Carcaca": "ex: 90L",
  "GrauProtecao": "ex: IP55",
  "Isolacao": "ex: F",
  "FatorServico": "ex: 1,25",
  "Peso": "ex: 26 kg",
  "NumeroSerie": "número de série/ordem se visível",
  "Rendimento": "ex: 87,5 %",
  "FatorPotencia": "ex: 0,80",
  "Observacoes": "qualquer outra informação relevante (norma, rolamentos, graxa, freio, marcações à mão, etc.)"
}"""


def _obter_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def _modelo_ocr():
    try:
        if "GEMINI_MODELO_OCR" in st.secrets:
            return st.secrets["GEMINI_MODELO_OCR"]
    except Exception:
        pass
    # Mantém a mesma família usada pelo chat (ver ui/view_chat.py)
    return os.environ.get("GEMINI_MODELO_OCR", "gemini-3.6-flash")


def _extrair_json(texto):
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError("resposta sem JSON")
    return json.loads(texto[inicio:fim + 1])


def extrair_dados_placa(imagem_bytes, mime="image/jpeg"):
    """
    Retorna (dict_campos, None) em caso de sucesso ou (None, motivo) em falha.
    """
    api_key = _obter_api_key()
    if not api_key:
        return None, "Chave GEMINI_API_KEY não configurada — preencha os campos manualmente."

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=45_000),
        )
        resposta = client.models.generate_content(
            model=_modelo_ocr(),
            contents=[
                types.Part.from_bytes(data=imagem_bytes, mime_type=mime),
                _PROMPT,
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        dados = _extrair_json(resposta.text or "")
        limpo = {campo: str(dados.get(campo, "") or "").strip() for campo in CAMPOS_PLACA}
        return limpo, None
    except Exception as e:  # rede, chave, modelo, JSON inválido...
        return None, f"OCR indisponível ({type(e).__name__}: {str(e)[:160]}). Preencha manualmente."
