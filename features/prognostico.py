"""
Prognóstico por máquina: por que está em alerta/crítico e, se continuar
assim, quando a manutenção deve acontecer.

- motivos_status(leitura): quais variáveis estão fora da faixa e quanto.
- prever_data_manutencao(tag): extrapola a tendência das últimas horas
  (regressão linear por variável) até o limite crítico e combina com o
  risco do modelo de falhas. Devolve data estimada e justificativa.
"""
from datetime import datetime, timedelta, timezone

import numpy as np

from features.limites import LIMITES, VARIAVEIS, NOMES_FALHA, status_variavel
from features.previsao import prever
from providers.db_mongo import TelemetriaRepository

HORIZONTE_MAX_DIAS = 30


def motivos_status(leitura):
    """Lista de frases explicando o status da leitura."""
    motivos = []
    cod = int(leitura.get("FalhaCodigo") or 0)
    if cod:
        motivos.append(f"leitura rotulada como **{NOMES_FALHA.get(cod, cod)}** pelo sistema de detecção")
    for v in ("Temperatura", "Vibracao", "Corrente", "RPM"):
        val = leitura.get(v)
        if val is None:
            continue
        s = status_variavel(v, float(val))
        if s == "Normal":
            continue
        lim = LIMITES[v]
        u = VARIAVEIS[v]["unidade"]
        if v == "RPM":
            ref = lim["normal"][0]
            motivos.append(f"{VARIAVEIS[v]['rotulo']} em **{float(val):.0f} {u}**, {ref - float(val):.0f} {u} abaixo do mínimo normal ({ref:g} {u}) → {s.lower()}")
        else:
            ref = lim["normal"][1]
            motivos.append(f"{VARIAVEIS[v]['rotulo']} em **{float(val):.1f} {u}**, {float(val) - ref:.1f} {u} acima do máximo normal ({ref:g} {u}) → {s.lower()}")
    return motivos


def _tendencia_horas(leituras, variavel):
    """Inclinação (unidade/hora) por regressão linear sobre as leituras."""
    pts = [(l["timestamp"], float(l[variavel])) for l in leituras if l.get(variavel) is not None and l.get("timestamp")]
    if len(pts) < 4:
        return None, None
    t0 = pts[0][0]
    x = np.array([(p[0] - t0).total_seconds() / 3600 for p in pts])
    y = np.array([p[1] for p in pts])
    if x.max() - x.min() < 0.5:
        return None, None
    a, b = np.polyfit(x, y, 1)
    return float(a), float(a * x.max() + b)


def prever_data_manutencao(tag, leituras=None):
    """
    Retorna dict: {data (datetime), horas, variavel, nivel, texto, motivos, risco_modelo}.
    """
    leituras = leituras or TelemetriaRepository.obter_ultimas_n(tag, 36)   # ~6 h em 10 min
    if not leituras:
        return None
    ultima = leituras[-1]
    agora = datetime.now(timezone.utc)
    prev = prever(leituras[-5:])
    risco = prev["risco"] if prev else 0.0
    status_atual = "Normal"
    from features.limites import classificar_status
    status_atual, _ = classificar_status(ultima.get("Temperatura"), ultima.get("Vibracao"), ultima.get("Corrente"),
                                         ultima.get("RPM"), ultima.get("FalhaCodigo", 0))

    candidatos = []
    for v in ("Temperatura", "Vibracao", "Corrente", "RPM"):
        incl, atual = _tendencia_horas(leituras, v)
        if incl is None:
            continue
        lim = LIMITES[v]
        if v == "RPM":
            limite = lim["alerta"][0]
            if incl < -0.01 and atual > limite:
                candidatos.append((( atual - limite) / -incl, v, incl))
        else:
            limite = lim["alerta"][1]
            if incl > 0.01 and atual < limite:
                candidatos.append(((limite - atual) / incl, v, incl))
            elif atual >= limite:
                candidatos.append((0.0, v, incl))

    horas = None
    variavel = None
    if candidatos:
        horas, variavel, _ = min(candidatos, key=lambda c: c[0])

    # Combina com o modelo e o status atual
    if status_atual == "Crítico" or risco >= 0.5:
        horas = 0.0 if horas is None else min(horas, 24.0)
        nivel = "imediata"
    elif status_atual == "Alerta" or risco >= 0.2:
        horas = 72.0 if horas is None else min(horas, 7 * 24)
        nivel = "programar"
    else:
        nivel = "monitorar"
        if horas is None or horas > HORIZONTE_MAX_DIAS * 24:
            horas = None

    if horas is None:
        data = None
        texto = (f"Sem tendência de saída da faixa nos próximos {HORIZONTE_MAX_DIAS} dias. "
                 f"Manter o plano preventivo (próxima inspeção mensal).")
    else:
        data = agora + timedelta(hours=horas)
        data_local = data.astimezone(timezone(timedelta(hours=-3)))
        if horas <= 0.5:
            quando = "agora"
        elif horas < 48:
            quando = f"em ~{horas:.0f} h ({data_local:%d/%m %H:%M})"
        else:
            quando = f"em ~{horas / 24:.0f} dias ({data_local:%d/%m/%Y})"
        base = (f"tendência de {VARIAVEIS[variavel]['rotulo'].lower()}" if variavel else "risco do modelo de falhas")
        if nivel == "imediata":
            texto = f"manutenção **imediata** (parar e inspecionar {quando}) — motivo: {base}."
        elif nivel == "programar":
            texto = f"**programar manutenção** {quando} — motivo: {base}."
        else:
            texto = f"**monitorar**: pela {base} o limite de alerta seria atingido {quando}; planejar inspeção antes disso."
        if prev:
            texto += f" Modelo de previsão: {prev['classe_nome']} com risco {prev['nivel_risco'].lower()} ({risco * 100:.0f}%)."

    return {"data": data, "horas": horas, "variavel": variavel, "nivel": nivel, "texto": texto,
            "motivos": motivos_status(ultima), "status": status_atual, "risco_modelo": risco,
            "classe_modelo": prev["classe_nome"] if prev else None}
