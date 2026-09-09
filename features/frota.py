"""
Análise de frota: quais máquinas têm mais manutenções, mais leituras
críticas e mais alertas, com pontuação de saúde e recomendação
(manter / revisar-atualizar / substituir) por regras — a IA usa este
resumo para fundamentar a resposta.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd

from features.previsao import prever, modelo_disponivel
from providers.db_mongo import (
    EquipamentoRepository, TelemetriaRepository, ManutencaoRepository, MongoIndisponivelError,
)

ANO_ATUAL = datetime.now().year


def tabela_frota(dias=30, tags=None):
    """DataFrame com um resumo por máquina no período."""
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=dias)
    try:
        cadastro = {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}
    except MongoIndisponivelError:
        cadastro = {}
    tags = sorted(tags or (set(cadastro) | set(TelemetriaRepository.obter_tags_disponiveis())))
    resumo = TelemetriaRepository.resumo_intervalo(inicio, agora, tags)
    previsoes = {}
    if modelo_disponivel():
        for t, ult in TelemetriaRepository.ultimas_n_por_tag(tags, 5).items():
            p = prever(ult) if ult else None
            if p:
                previsoes[t] = p
    try:
        manutencoes = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        manutencoes = []
    man_por_tag = {}
    for m in manutencoes:
        d = m.get("data")
        if hasattr(d, "tzinfo") and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        if d and d >= inicio:
            lst = man_por_tag.setdefault(m.get("TAG"), [])
            lst.append(m)

    linhas = []
    for t in tags:
        e = cadastro.get(t, {})
        r = resumo.get(t, {})
        n = r.get("n", 0) or 0
        mans = man_por_tag.get(t, [])
        corretivas = sum(1 for m in mans if m.get("tipo") == "Corretiva")
        horas_paradas = sum(float(m.get("tempo_parada_horas") or 0) for m in mans)
        risco = None
        p = previsoes.get(t)
        if p:
            risco = p["risco"]
        try:
            idade = ANO_ATUAL - int(e.get("AnoInstalacao") or ANO_ATUAL)
        except (TypeError, ValueError):
            idade = 0
        pct_falha = (r.get("falhas", 0) / n * 100) if n else 0.0
        pct_critico = (r.get("criticos", 0) / n * 100) if n else 0.0
        pct_alerta = (r.get("alertas", 0) / n * 100) if n else 0.0

        # Pontuação de saúde (0–100): parte de 100 e desconta
        saude = 100.0
        saude -= min(35, pct_falha * 1.5)          # ~23 % em falha => -35
        saude -= min(10, pct_alerta * 1.0)
        saude -= min(20, corretivas * 5)
        saude -= min(10, horas_paradas * 0.3)
        saude -= min(10, max(0, idade - 10) * 1.0)  # >10 anos começa a descontar
        if risco is not None:
            saude -= min(15, risco * 15)
        saude = max(0.0, round(saude, 0))

        if saude < 40 or (pct_falha > 15 and corretivas >= 2 and idade >= 12):
            rec = "Substituir (avaliar compra de nova)"
        elif saude < 60 or corretivas >= 3 or pct_falha > 15:
            rec = "Revisar / atualizar"
        else:
            rec = "Manter"

        linhas.append({
            "Máquina": t, "Fabricante": e.get("Fabricante", "-"), "Modelo": e.get("Modelo", "-"),
            "Idade (anos)": idade, "Criticidade": (e.get("Criticidade") or "-")[:1],
            "Manutenções": len(mans), "Corretivas": corretivas, "Horas paradas": round(horas_paradas, 1),
            "Leituras críticas": int(r.get("criticos", 0) or 0), "Leituras em alerta": int(r.get("alertas", 0) or 0),
            "Leituras em falha": int(r.get("falhas", 0) or 0), "% em falha": round(pct_falha, 1),
            "Superaq.": int(r.get("falhas_2", 0) or 0), "Desbal.": int(r.get("falhas_1", 0) or 0), "Mec.": int(r.get("falhas_3", 0) or 0),
            "Risco modelo": f"{risco * 100:.0f}%" if risco is not None else "-",
            "Saúde": int(saude), "Recomendação": rec, "Site": e.get("site_url", ""),
        })
    df = pd.DataFrame(linhas)
    if not df.empty:
        df = df.sort_values(["Saúde", "Leituras críticas"], ascending=[True, False]).reset_index(drop=True)
    return df


def resumo_frota_texto(df, top=8):
    """Texto compacto para o contexto do Chat IA."""
    if df is None or df.empty:
        return "Sem dados de frota."
    linhas = []
    for _, r in df.head(top).iterrows():
        linhas.append(
            f"- {r['Máquina']} ({r['Fabricante']} {r['Modelo']}, {r['Idade (anos)']} anos, crit. {r['Criticidade']}): "
            f"saúde {r['Saúde']}/100, {r['Manutenções']} manutenções ({r['Corretivas']} corretivas, {r['Horas paradas']} h paradas), "
            f"{r['Leituras críticas']} leituras críticas, {r['Leituras em alerta']} em alerta, {r['% em falha']}% em falha "
            f"(superaq. {r['Superaq.']}, desbal. {r['Desbal.']}, mec. {r['Mec.']}), risco modelo {r['Risco modelo']} → {r['Recomendação']}"
            + (f"; site do fabricante: {r['Site']}" if r.get("Site") else "")
        )
    piores = ", ".join(df.head(3)["Máquina"])
    return (f"Ranking de saúde da frota (pior → melhor), {len(df)} máquinas. Piores: {piores}.\n" + "\n".join(linhas))
