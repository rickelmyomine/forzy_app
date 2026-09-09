"""
Dúvidas frequentes: 50 perguntas respondidas na hora só com os dados das
leituras (telemetria), cadastro, previsões, manutenções e funcionários do
MongoDB — sem chamar a IA externa. Cada função devolve texto em Markdown.
"""
import re
from datetime import datetime, timedelta, timezone

import pandas as pd

from features.limites import NOMES_FALHA, VARIAVEIS, LIMITES, classificar_status
from features.previsao import prever, modelo_disponivel
from features.prognostico import prever_data_manutencao
from providers.db_mongo import (
    EquipamentoRepository, TelemetriaRepository, ManutencaoRepository, MongoIndisponivelError,
)

FUSO = timezone(timedelta(hours=-3))


def _agora():
    return datetime.now(timezone.utc)


def _fmt(d):
    if d is None:
        return "-"
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(FUSO).strftime("%d/%m %H:%M")


def _tags():
    try:
        tags = set(EquipamentoRepository.listar_tags())
    except MongoIndisponivelError:
        tags = set()
    return sorted(tags | set(TelemetriaRepository.obter_tags_disponiveis()))


def _ultimas():
    out = {}
    for t, l in TelemetriaRepository.ultimas_leituras(_tags()).items():
        s, ic = classificar_status(l.get("Temperatura"), l.get("Vibracao"), l.get("Corrente"), l.get("RPM"), l.get("FalhaCodigo", 0))
        out[t] = (l, s, ic)
    return out


def _resumo(dias):
    fim = _agora()
    return TelemetriaRepository.resumo_intervalo(fim - timedelta(days=dias), fim, _tags())


def _tabela(linhas, colunas):
    if not linhas:
        return "_Sem dados._"
    df = pd.DataFrame(linhas, columns=colunas)
    return df.to_markdown(index=False)


# --- Perguntas -------------------------------------------------------------
def q_status_agora():
    u = _ultimas()
    crit = [f"{t} ({', '.join(m for m in _motivos(l))})" for t, (l, s, ic) in u.items() if s == "Crítico"]
    ale = [t for t, (l, s, ic) in u.items() if s == "Alerta"]
    nor = [t for t, (l, s, ic) in u.items() if s == "Normal"]
    return (f"**Estado atual da planta ({len(u)} máquinas):**\n\n"
            f"- 🔴 Críticas ({len(crit)}): {'; '.join(crit) or 'nenhuma'}\n"
            f"- 🟡 Em alerta ({len(ale)}): {', '.join(ale) or 'nenhuma'}\n"
            f"- 🟢 Normais ({len(nor)}): {', '.join(nor) or 'nenhuma'}")


def _motivos(l):
    from features.prognostico import motivos_status
    ms = motivos_status(l)
    return [m.replace("**", "") for m in ms] or ["dentro da faixa"]


def q_mais_quente():
    u = _ultimas()
    linhas = sorted(((t, l["Temperatura"], s) for t, (l, s, ic) in u.items()), key=lambda x: -x[1])[:5]
    return "**Máquinas mais quentes agora (última leitura):**\n\n" + _tabela(
        [(t, f"{v:.1f} °C", s) for t, v, s in linhas], ["Máquina", "Temperatura", "Status"]) + \
        f"\n\nFaixa normal: {LIMITES['Temperatura']['normal'][0]:g}–{LIMITES['Temperatura']['normal'][1]:g} °C; crítico acima de {LIMITES['Temperatura']['alerta'][1]:g} °C."


def q_mais_vibracao():
    u = _ultimas()
    linhas = sorted(((t, l["Vibracao"], s) for t, (l, s, ic) in u.items()), key=lambda x: -x[1])[:5]
    return "**Máquinas com maior vibração agora:**\n\n" + _tabela(
        [(t, f"{v:.2f} mm/s", s) for t, v, s in linhas], ["Máquina", "Vibração", "Status"]) + \
        f"\n\nFaixa normal: até {LIMITES['Vibracao']['normal'][1]:g} mm/s; crítico acima de {LIMITES['Vibracao']['alerta'][1]:g} mm/s."


def q_mais_corrente():
    u = _ultimas()
    linhas = sorted(((t, l["Corrente"], s) for t, (l, s, ic) in u.items()), key=lambda x: -x[1])[:5]
    return "**Máquinas com maior corrente agora:**\n\n" + _tabela(
        [(t, f"{v:.1f} A", s) for t, v, s in linhas], ["Máquina", "Corrente", "Status"]) + \
        f"\n\nFaixa normal: {LIMITES['Corrente']['normal'][0]:g}–{LIMITES['Corrente']['normal'][1]:g} A."


def q_menor_rpm():
    u = _ultimas()
    linhas = sorted(((t, l.get("RPM", 0), s) for t, (l, s, ic) in u.items()), key=lambda x: x[1])[:5]
    return "**Máquinas com menor rotação agora (queda de RPM indica falha mecânica):**\n\n" + _tabela(
        [(t, f"{v:.0f} RPM", s) for t, v, s in linhas], ["Máquina", "Rotação", "Status"]) + \
        f"\n\nFaixa normal: {LIMITES['RPM']['normal'][0]:g}–{LIMITES['RPM']['normal'][1]:g} RPM."


def _q_falhas(dias, titulo):
    r = _resumo(dias)
    linhas = sorted(((t, v["falhas"], v["falhas_1"], v["falhas_2"], v["falhas_3"], v["n"]) for t, v in r.items()), key=lambda x: -x[1])
    linhas = [(t, f, d, s, m, f"{100 * f / n:.1f}%" if n else "-") for t, f, d, s, m, n in linhas if f][:10]
    if not linhas:
        return f"**{titulo}:** nenhuma leitura em falha no período. 🟢"
    return f"**{titulo} (top 10):**\n\n" + _tabela(linhas, ["Máquina", "Leituras em falha", "Desbal.", "Superaq.", "Mecânica", "% do tempo"])


def q_falhas_24h():
    return _q_falhas(1, "Máquinas com mais falhas nas últimas 24 h")


def q_falhas_7d():
    return _q_falhas(7, "Máquinas com mais falhas nos últimos 7 dias")


def q_falhas_30d():
    return _q_falhas(30, "Máquinas com mais falhas nos últimos 30 dias")


def _q_tipo(cod, dias=30):
    r = _resumo(dias)
    chave = f"falhas_{cod}"
    linhas = sorted(((t, v[chave]) for t, v in r.items() if v.get(chave)), key=lambda x: -x[1])[:10]
    nome = NOMES_FALHA[cod]
    if not linhas:
        return f"**{nome} nos últimos {dias} dias:** nenhuma ocorrência. 🟢"
    return f"**Máquinas com mais leituras de {nome.lower()} nos últimos {dias} dias:**\n\n" + _tabela(linhas, ["Máquina", "Leituras"])


def q_superaquecimento():
    return _q_tipo(2)


def q_desbalanceamento():
    return _q_tipo(1)


def q_falha_mecanica():
    return _q_tipo(3)


def q_ultima_falha():
    r = _resumo(30)
    linhas = sorted(((t, v.get("ultima_falha")) for t, v in r.items() if v.get("ultima_falha")), key=lambda x: x[1], reverse=True)[:10]
    return "**Última falha registrada por máquina (30 dias):**\n\n" + _tabela([(t, _fmt(d)) for t, d in linhas], ["Máquina", "Última falha"])


def q_previsao_risco():
    if not modelo_disponivel():
        return "Modelo de previsão não disponível."
    linhas = []
    for t, ult in TelemetriaRepository.ultimas_n_por_tag(_tags(), 5).items():
        p = prever(ult) if ult else None
        if p:
            linhas.append((t, p["classe_nome"], p["nivel_risco"], f"{p['risco'] * 100:.0f}%"))
    linhas.sort(key=lambda x: -float(x[3].rstrip("%")))
    return "**Risco de falha previsto pelo modelo (últimas 5 leituras):**\n\n" + _tabela(linhas[:10], ["Máquina", "Classe prevista", "Risco", "Probabilidade de falha"]) + \
        "\n\nRisco baixo < 20 %, moderado 20–50 %, alto > 50 %. Sinal para priorizar inspeção, não diagnóstico."


def q_proxima_manutencao():
    linhas = []
    for t in _tags():
        p = prever_data_manutencao(t)
        if p and p["horas"] is not None:
            linhas.append((t, p["nivel"], f"{p['horas']:.0f} h" if p["horas"] < 48 else f"{p['horas'] / 24:.0f} dias",
                           _fmt(p["data"]), VARIAVEIS[p["variavel"]]["rotulo"] if p["variavel"] else "modelo"))
    linhas.sort(key=lambda x: {"imediata": 0, "programar": 1, "monitorar": 2}[x[1]])
    if not linhas:
        return "Nenhuma máquina com tendência de manutenção nos próximos 30 dias. 🟢"
    return "**Próximas manutenções previstas (tendência + modelo):**\n\n" + _tabela(linhas[:12], ["Máquina", "Urgência", "Prazo", "Data estimada", "Motivo"])


def q_media_planta_24h():
    r = _resumo(1)
    if not r:
        return "Sem leituras nas últimas 24 h."
    df = pd.DataFrame(r.values())
    return ("**Média da planta nas últimas 24 h:**\n\n"
            f"- Temperatura média {df['temp_med'].mean():.1f} °C (máx {df['temp_max'].max():.1f} °C)\n"
            f"- Vibração média {df['vib_med'].mean():.2f} mm/s (máx {df['vib_max'].max():.2f} mm/s)\n"
            f"- Corrente média {df['cor_med'].mean():.1f} A (máx {df['cor_max'].max():.1f} A)\n"
            f"- Rotação média {df['rpm_med'].mean():.0f} RPM (mín {df['rpm_min'].min():.0f} RPM)\n"
            f"- Leituras em falha: {int(df['falhas'].sum())} de {int(df['n'].sum())} ({100 * df['falhas'].sum() / max(1, df['n'].sum()):.1f} %)")


def q_percentual_normal():
    r = _resumo(7)
    linhas = sorted(((t, 100 * (v["n"] - v["falhas"] - v.get("alertas", 0)) / v["n"]) for t, v in r.items() if v["n"]), key=lambda x: x[1])[:10]
    return "**Máquinas com menor % do tempo em operação normal (7 dias):**\n\n" + _tabela([(t, f"{p:.1f}%") for t, p in linhas], ["Máquina", "% normal"])


def q_manutencoes_abertas():
    try:
        docs = ManutencaoRepository.listar(limite=500)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    abertas = [d for d in docs if d.get("status") in ("Aberta", "Em andamento")]
    if not abertas:
        return "Nenhuma ordem de serviço aberta ou em andamento. 🟢"
    return "**Ordens de serviço abertas / em andamento:**\n\n" + _tabela(
        [(d.get("os_id"), d.get("TAG"), d["data"].strftime("%d/%m/%Y") if hasattr(d.get("data"), "strftime") else "-", d.get("tipo"), d.get("status"), (d.get("descricao_problema") or "")[:60], d.get("tecnico"))
         for d in abertas], ["OS", "Máquina", "Data", "Tipo", "Status", "Problema", "Técnico"])


def q_mais_manutencoes():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada."
    df = pd.DataFrame(docs)
    g = df.groupby("TAG").agg(OS=("os_id", "count"), Corretivas=("tipo", lambda s: (s == "Corretiva").sum()),
                              Horas=("tempo_parada_horas", "sum")).sort_values(["OS", "Corretivas"], ascending=False).head(10)
    return "**Máquinas com mais manutenções registradas:**\n\n" + g.reset_index().rename(columns={"TAG": "Máquina", "Horas": "Horas paradas"}).to_markdown(index=False)


def q_horas_paradas():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada."
    df = pd.DataFrame(docs)
    g = df.groupby("TAG")["tempo_parada_horas"].sum().sort_values(ascending=False).head(10)
    total = df["tempo_parada_horas"].sum()
    return f"**Horas paradas por máquina (total {total:g} h):**\n\n" + _tabela([(t, f"{h:g} h") for t, h in g.items()], ["Máquina", "Horas paradas"])


def q_ultimas_manutencoes():
    try:
        docs = ManutencaoRepository.listar(limite=8)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada."
    return "**Últimas manutenções registradas:**\n\n" + _tabela(
        [(d.get("os_id"), d.get("TAG"), d["data"].strftime("%d/%m/%Y") if hasattr(d.get("data"), "strftime") else "-", d.get("tipo"), d.get("status"), (d.get("servico_executado") or d.get("descricao_problema") or "")[:70])
         for d in docs], ["OS", "Máquina", "Data", "Tipo", "Status", "Serviço"])


def q_cadastro():
    try:
        eq = [e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")]
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    return f"**Cadastro técnico ({len(eq)} máquinas):**\n\n" + _tabela(
        [(e["TAG"], e.get("Fabricante", "-"), e.get("Modelo", "-"), e.get("Potencia", "-"), e.get("Planta", "-"), (e.get("Criticidade") or "-")[:1], e.get("AnoInstalacao", "-"))
         for e in eq], ["Máquina", "Fabricante", "Modelo", "Potência", "Planta", "Crit.", "Ano"])


def q_mais_antigas():
    try:
        eq = [e for e in EquipamentoRepository.buscar_todos() if e.get("TAG") and e.get("AnoInstalacao")]
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    ano = datetime.now().year
    linhas = sorted(((e["TAG"], e.get("Fabricante"), e.get("Modelo"), e["AnoInstalacao"], ano - int(e["AnoInstalacao"])) for e in eq), key=lambda x: -x[4])[:10]
    return "**Máquinas mais antigas (candidatas a revisão/substituição):**\n\n" + _tabela(linhas, ["Máquina", "Fabricante", "Modelo", "Instalação", "Idade (anos)"])


def q_faixas():
    from features.limites import descricao_limites
    return "**Faixas de operação usadas no dashboard (manual técnico + histórico):**\n\n" + descricao_limites().replace("- ", "- ")


def q_falhas_por_hora():
    fim = _agora()
    f = TelemetriaRepository.obter_falhas_intervalo(fim - timedelta(days=7), fim, _tags())
    if not f:
        return "Nenhuma falha nos últimos 7 dias. 🟢"
    df = pd.DataFrame(f)
    df["hora"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.hour
    g = df.groupby("hora").size().sort_values(ascending=False).head(5)
    return "**Horários com mais falhas (7 dias):**\n\n" + _tabela([(f"{h:02d}h–{h + 1:02d}h", n) for h, n in g.items()], ["Horário", "Leituras em falha"])


# --- Perguntas adicionais (21 a 50) -----------------------------------------
def q_ranking_saude():
    from features.frota import tabela_frota
    df = tabela_frota(30)
    if df.empty:
        return "Sem dados."
    return "**Ranking de saúde das máquinas (pior → melhor, 30 dias):**\n\n" + df.head(12)[
        ["Máquina", "Saúde", "Leituras críticas", "Leituras em alerta", "Manutenções", "Recomendação"]].to_markdown(index=False)


def q_substituir():
    from features.frota import tabela_frota
    df = tabela_frota(30)
    subst = df[df["Recomendação"].str.startswith("Substituir")]
    revisar = df[df["Recomendação"].str.startswith("Revisar")]
    if subst.empty and revisar.empty:
        return "Nenhuma máquina precisa de substituição ou revisão pelos critérios atuais. 🟢"
    txt = ""
    if not subst.empty:
        txt += "**Candidatas a substituição:**\n\n" + subst[["Máquina", "Fabricante", "Modelo", "Idade (anos)", "Saúde", "% em falha"]].to_markdown(index=False) + "\n\n"
    if not revisar.empty:
        txt += "**Revisar / atualizar:**\n\n" + revisar[["Máquina", "Saúde", "Corretivas", "% em falha"]].head(10).to_markdown(index=False)
    return txt


def q_criticas_duradouras():
    from features.alertas import LEITURAS_CRITICAS_SEGUIDAS, criticos_consecutivos
    linhas = []
    for t in _tags():
        n = criticos_consecutivos(t)
        if n:
            linhas.append((t, n, f"{n * 10} min aprox.", "Sim" if n >= LEITURAS_CRITICAS_SEGUIDAS else "Ainda não"))
    if not linhas:
        return "Nenhuma máquina em estado crítico sustentado agora. 🟢"
    linhas.sort(key=lambda x: -x[1])
    return (f"**Máquinas em estado crítico sustentado** (alerta dispara a partir de "
            f"{LEITURAS_CRITICAS_SEGUIDAS} leituras seguidas):\n\n"
            + _tabela(linhas, ["Máquina", "Leituras críticas seguidas", "Duração", "Gera alerta"]))


def q_temperatura_maxima_7d():
    r = _resumo(7)
    linhas = sorted(((t, round(v["temp_max"], 1), round(v["temp_med"], 1)) for t, v in r.items()), key=lambda x: -x[1])[:10]
    return "**Maiores temperaturas dos últimos 7 dias:**\n\n" + _tabela(linhas, ["Máquina", "Temp. máxima (°C)", "Temp. média (°C)"])


def q_vibracao_maxima_7d():
    r = _resumo(7)
    linhas = sorted(((t, round(v["vib_max"], 2), round(v["vib_med"], 2)) for t, v in r.items()), key=lambda x: -x[1])[:10]
    return "**Maiores vibrações dos últimos 7 dias:**\n\n" + _tabela(linhas, ["Máquina", "Vib. máxima (mm/s)", "Vib. média (mm/s)"])


def q_corrente_maxima_7d():
    r = _resumo(7)
    linhas = sorted(((t, round(v["cor_max"], 1), round(v["cor_med"], 1)) for t, v in r.items()), key=lambda x: -x[1])[:10]
    return "**Maiores correntes dos últimos 7 dias:**\n\n" + _tabela(linhas, ["Máquina", "Corrente máx (A)", "Corrente média (A)"])


def q_rpm_minimo_7d():
    r = _resumo(7)
    linhas = sorted(((t, round(v["rpm_min"], 0), round(v["rpm_med"], 0)) for t, v in r.items()), key=lambda x: x[1])[:10]
    return "**Menores rotações dos últimos 7 dias (queda de RPM = falha mecânica):**\n\n" + _tabela(linhas, ["Máquina", "RPM mínimo", "RPM médio"])


def q_comparar_hoje_ontem():
    hoje = _resumo(1)
    dois = _resumo(2)
    linhas = []
    for t, v in hoje.items():
        d = dois.get(t)
        if not d or not d.get("n"):
            continue
        # ontem = janela de 2 dias menos hoje
        n_ontem = d["n"] - v["n"]
        f_ontem = d["falhas"] - v["falhas"]
        if n_ontem <= 0:
            continue
        linhas.append((t, v["falhas"], max(0, f_ontem), "↑" if v["falhas"] > f_ontem else ("↓" if v["falhas"] < f_ontem else "→")))
    linhas.sort(key=lambda x: -x[1])
    return "**Falhas hoje x ontem:**\n\n" + _tabela(linhas[:12], ["Máquina", "Falhas hoje", "Falhas ontem", "Tendência"])


def q_maquinas_sem_falha():
    r = _resumo(30)
    ok = [t for t, v in r.items() if not v.get("falhas")]
    return (f"**Máquinas sem nenhuma falha nos últimos 30 dias ({len(ok)}):** "
            + (", ".join(sorted(ok)) if ok else "nenhuma — todas tiveram ao menos uma falha."))


def q_planta_pior():
    try:
        cad = {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    r = _resumo(30)
    por_planta = {}
    for t, v in r.items():
        planta = cad.get(t, {}).get("Planta", "Não informada")
        d = por_planta.setdefault(planta, {"falhas": 0, "leituras": 0, "maquinas": 0})
        d["falhas"] += v.get("falhas", 0)
        d["leituras"] += v.get("n", 0)
        d["maquinas"] += 1
    linhas = [(p, d["maquinas"], d["falhas"], f"{100 * d['falhas'] / d['leituras']:.1f}%" if d["leituras"] else "-")
              for p, d in por_planta.items()]
    linhas.sort(key=lambda x: -x[2])
    return "**Falhas por planta (30 dias):**\n\n" + _tabela(linhas, ["Planta", "Máquinas", "Leituras em falha", "% do tempo"])


def q_por_fabricante():
    try:
        cad = {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    r = _resumo(30)
    por_fab = {}
    for t, v in r.items():
        fab = cad.get(t, {}).get("Fabricante", "Não informado")
        d = por_fab.setdefault(fab, {"falhas": 0, "leituras": 0, "maquinas": 0})
        d["falhas"] += v.get("falhas", 0)
        d["leituras"] += v.get("n", 0)
        d["maquinas"] += 1
    linhas = [(f, d["maquinas"], d["falhas"], f"{100 * d['falhas'] / d['leituras']:.1f}%" if d["leituras"] else "-")
              for f, d in por_fab.items()]
    linhas.sort(key=lambda x: -x[2])
    return "**Falhas por fabricante (30 dias):**\n\n" + _tabela(linhas, ["Fabricante", "Máquinas", "Leituras em falha", "% do tempo"])


def q_criticidade():
    try:
        eq = [e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")]
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    alta = [e["TAG"] for e in eq if str(e.get("Criticidade", "")).startswith("A")]
    r = _resumo(30)
    linhas = [(t, r.get(t, {}).get("falhas", 0), r.get(t, {}).get("criticos", 0)) for t in sorted(alta)]
    return ("**Máquinas de criticidade A (alta) e suas falhas em 30 dias:**\n\n"
            + _tabela(linhas, ["Máquina", "Leituras em falha", "Leituras críticas"]))


def q_potencia():
    try:
        eq = [e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")]
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    linhas = [(e["TAG"], e.get("Potencia", "-"), e.get("Tensao", "-"), e.get("Corrente", "-"), e.get("RPM", "-")) for e in eq]
    return "**Dados de placa das máquinas:**\n\n" + _tabela(linhas, ["Máquina", "Potência", "Tensão", "Corrente nominal", "Rotação nominal"])


def q_sem_cadastro():
    try:
        cad = set(EquipamentoRepository.listar_tags())
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    tele = set(TelemetriaRepository.obter_tags_disponiveis())
    sem = sorted(tele - cad)
    sem_foto = []
    for t in sorted(cad):
        if not (EquipamentoRepository.buscar_por_tag(t) or {}).get("foto"):
            sem_foto.append(t)
    return (f"**Máquinas com telemetria mas sem cadastro técnico ({len(sem)}):** {', '.join(sem) or 'nenhuma'}\n\n"
            f"**Cadastradas sem foto ({len(sem_foto)}):** {', '.join(sem_foto) or 'nenhuma'}")


def q_preventivas_vs_corretivas():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada."
    df = pd.DataFrame(docs)
    cont = df["tipo"].value_counts()
    prev = int(cont.get("Preventiva", 0))
    corr = int(cont.get("Corretiva", 0))
    total = int(cont.sum())
    razao = f"{prev / corr:.1f} preventivas por corretiva" if corr else "sem corretivas"
    return (f"**Preventivas x corretivas:** {prev} preventivas, {corr} corretivas, "
            f"{total} OS no total ({razao}).\n\nO ideal de mercado é pelo menos 3 preventivas para cada corretiva.")


def q_manutencoes_mes():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada."
    df = pd.DataFrame(docs)
    df["mes"] = pd.to_datetime(df["data"], errors="coerce").dt.to_period("M").astype(str)
    g = df.groupby("mes").agg(OS=("os_id", "count"), Horas=("tempo_parada_horas", "sum")).sort_index(ascending=False)
    return "**Manutenções por mês:**\n\n" + g.reset_index().rename(columns={"mes": "Mês", "Horas": "Horas paradas"}).to_markdown(index=False)


def q_tecnicos():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada."
    df = pd.DataFrame(docs)
    g = df.groupby("tecnico").agg(OS=("os_id", "count"), Horas=("tempo_parada_horas", "sum")).sort_values("OS", ascending=False)
    return "**Manutenções por técnico:**\n\n" + g.reset_index().rename(columns={"tecnico": "Técnico", "Horas": "Horas"}).to_markdown(index=False)


def q_pecas():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    pecas = [d.get("pecas_trocadas") for d in docs if d.get("pecas_trocadas")]
    if not pecas:
        return "Nenhuma peça registrada nas manutenções."
    from collections import Counter
    itens = Counter()
    for p in pecas:
        for item in re.split(r"[,;]", p):
            item = item.strip()
            if item:
                itens[item] += 1
    return "**Peças mais trocadas:**\n\n" + _tabela(list(itens.most_common(10)), ["Peça", "Vezes"])


def q_sem_manutencao():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    com = {d.get("TAG") for d in docs}
    sem = [t for t in _tags() if t not in com]
    ultimas = []
    for d in docs:
        ultimas.append((d.get("TAG"), d.get("data")))
    mais_antigas = {}
    for tag, data in ultimas:
        if tag and (tag not in mais_antigas or (data and data > mais_antigas[tag])):
            mais_antigas[tag] = data
    atrasadas = sorted(((t, d) for t, d in mais_antigas.items() if d), key=lambda x: x[1])[:5]
    txt = f"**Máquinas sem nenhuma manutenção registrada ({len(sem)}):** {', '.join(sem) or 'nenhuma'}"
    if atrasadas:
        txt += "\n\n**Manutenções mais antigas (candidatas à próxima preventiva):**\n\n" + _tabela(
            [(t, d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)) for t, d in atrasadas],
            ["Máquina", "Última manutenção"])
    return txt


def q_tempo_medio_reparo():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    corr = [d for d in docs if d.get("tipo") == "Corretiva" and d.get("tempo_parada_horas")]
    if not corr:
        return "Sem manutenções corretivas com tempo de parada registrado."
    horas = [float(d["tempo_parada_horas"]) for d in corr]
    return (f"**Tempo médio de reparo (MTTR):** {sum(horas) / len(horas):.1f} h por manutenção corretiva "
            f"({len(corr)} corretivas, de {min(horas):g} h a {max(horas):g} h).")


def q_disponibilidade():
    try:
        docs = ManutencaoRepository.listar(limite=5000)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    horas_periodo = 30 * 24
    paradas = {}
    for d in docs:
        paradas[d.get("TAG")] = paradas.get(d.get("TAG"), 0) + float(d.get("tempo_parada_horas") or 0)
    linhas = sorted(((t, round(h, 1), f"{100 * (horas_periodo - h) / horas_periodo:.1f}%") for t, h in paradas.items()),
                    key=lambda x: x[1], reverse=True)[:10]
    return ("**Disponibilidade estimada (30 dias, considerando as horas paradas registradas):**\n\n"
            + _tabela(linhas, ["Máquina", "Horas paradas", "Disponibilidade"]))


def q_funcionarios():
    from providers.db_mongo import FuncionarioRepository
    try:
        pessoas = FuncionarioRepository.listar()
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not pessoas:
        return "Nenhum funcionário cadastrado. Cadastre em 'Cadastro de Funcionários' para os alertas terem destinatário."
    return "**Funcionários cadastrados:**\n\n" + _tabela(
        [(p.get("nome"), p.get("cargo"), p.get("email"), p.get("telefone"), p.get("planta"),
          "Sim" if p.get("receber_alertas") else "Não") for p in pessoas],
        ["Nome", "Cargo", "E-mail", "Telefone", "Planta", "Recebe alertas"])


def q_alertas_enviados():
    from providers.db_mongo import NotificacaoRepository
    try:
        docs = NotificacaoRepository.listar(15)
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhum alerta enviado pelo app ainda."
    return "**Últimos alertas enviados:**\n\n" + _tabela(
        [(_fmt(d.get("enviado_em")), d.get("origem"), d.get("TAG", "-"),
          f"{len(d.get('emails') or [])} e-mail(s)", "✅" if d.get("email_ok") else "⚠️") for d in docs],
        ["Quando", "Origem", "Máquina", "Destinatários", "E-mail"])


def q_o_que_fazer_agora():
    u = _ultimas()
    criticas = [t for t, (l, s, ic) in u.items() if s == "Crítico"]
    if not criticas:
        return "Nenhuma ação urgente: nenhuma máquina em estado crítico agora. 🟢 Siga o plano preventivo."
    linhas = []
    for t in criticas:
        p = prever_data_manutencao(t)
        linhas.append((t, p["classe_modelo"] or "-", p["nivel"], (p["motivos"][0].replace("**", "") if p["motivos"] else "-")))
    return ("**Prioridades agora (máquinas críticas):**\n\n"
            + _tabela(linhas, ["Máquina", "Diagnóstico do modelo", "Urgência", "Motivo principal"])
            + "\n\nComece pelas de urgência *imediata*: isolar, inspecionar e registrar a manutenção no app.")


def q_causas_superaquecimento():
    return ("**Superaquecimento — causas prováveis e o que fazer:**\n\n"
            "1. Ventilação obstruída (aletas/tampa defletora sujas) → limpar.\n"
            "2. Sobrecarga mecânica → conferir a carga acoplada e a corrente por fase.\n"
            "3. Tensão desbalanceada ou falta de fase → medir as três fases.\n"
            "4. Rolamento com atrito excessivo → ouvir/medir vibração e lubrificar.\n"
            "5. Isolação degradada → teste de megger na próxima parada.\n\n"
            f"Limite do sistema: acima de 80 °C é alerta; acima de 88 °C, crítico.")


def q_causas_vibracao():
    return ("**Vibração alta — causas prováveis e o que fazer:**\n\n"
            "1. Desbalanceamento do rotor ou da carga → balancear.\n"
            "2. Desalinhamento do acoplamento → alinhar com relógio comparador.\n"
            "3. Folga/fixação frouxa na base → reapertar.\n"
            "4. Rolamento desgastado → substituir (verificar ruído e temperatura do mancal).\n"
            "5. Eixo empenado → medir excentricidade.\n\n"
            "Limite do sistema: acima de 4,5 mm/s é alerta; acima de 6,0 mm/s, crítico.")


def q_causas_queda_rpm():
    return ("**Queda de rotação — causas prováveis e o que fazer:**\n\n"
            "1. Carga travando (transportador, bomba, redutor) → verificar o acionado.\n"
            "2. Rolamento travando → inspeção imediata.\n"
            "3. Falta de fase / tensão baixa → medir alimentação.\n"
            "4. Acoplamento danificado → substituir.\n\n"
            "Limite do sistema: abaixo de 1680 RPM é alerta; abaixo de 1600 RPM, crítico. "
            "Queda de RPM com vibração e corrente altas é a assinatura de falha mecânica.")


def q_plano_preventivo():
    return ("**Plano de manutenção preventiva dos motores:**\n\n"
            "- **Mensal:** inspeção visual, limpeza das aletas e ventilação, verificação de fixação e ruído.\n"
            "- **Trimestral:** lubrificação dos mancais, reaperto, medição de corrente por fase, análise da "
            "tendência de temperatura e vibração.\n"
            "- **Anual:** teste de isolação (megger), alinhamento e balanceamento.\n\n"
            "Registre cada intervenção em *Manutenções* — o gerente é avisado automaticamente.")


def q_como_modelo_funciona():
    from features.previsao import carregar_modelo
    _, meta = carregar_modelo()
    if not meta:
        return "Modelo de previsão não carregado."
    return (f"**Modelo de previsão de falhas:** {meta.get('modelo')}\n\n"
            f"- Entradas: temperatura, vibração, corrente e rotação, mais a média e o desvio das últimas "
            f"{meta.get('janela')} leituras.\n"
            f"- Treinado com {meta.get('n_treino')} leituras e testado com {meta.get('n_teste')} "
            f"(divisão cronológica por máquina).\n"
            f"- Acurácia em teste: {meta.get('acuracia_teste')} · F1-macro: {meta.get('f1_macro_teste')}.\n"
            f"- Saídas: probabilidade de Normal, Desbalanceamento, Superaquecimento e Falha mecânica.\n\n"
            "É um sinal para priorizar inspeção, não um diagnóstico confirmado.")


def q_leituras_por_dia():
    r = _resumo(30)
    total = sum(v.get("n", 0) for v in r.values())
    falhas = sum(v.get("falhas", 0) for v in r.values())
    return (f"**Volume de dados (30 dias):** {total:,} leituras de {len(r)} máquinas, "
            f"{falhas:,} em falha ({100 * falhas / total:.1f}%).".replace(",", ".")
            + "\n\nAs leituras chegam a cada 10 minutos nos últimos 3 dias e a cada 30 minutos nos demais.")


def q_horario_pico_temperatura():
    fim = _agora()
    leit = TelemetriaRepository.obter_intervalo(fim - timedelta(days=7), fim, _tags(), campos=["Temperatura", "timestamp"])
    if not leit:
        return "Sem leituras."
    df = pd.DataFrame(leit)
    df["hora"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.hour
    g = df.groupby("hora")["Temperatura"].mean().round(1).sort_values(ascending=False).head(6)
    return ("**Horários mais quentes da planta (média dos últimos 7 dias):**\n\n"
            + _tabela([(f"{h:02d}h", v) for h, v in g.items()], ["Horário", "Temperatura média (°C)"]))


CARDAPIO = [
    ("Quais máquinas estão em estado crítico ou alerta agora?", q_status_agora),
    ("Quais máquinas estão mais quentes agora?", q_mais_quente),
    ("Quais máquinas têm maior vibração agora?", q_mais_vibracao),
    ("Quais máquinas têm maior corrente agora?", q_mais_corrente),
    ("Quais máquinas têm menor rotação (RPM) agora?", q_menor_rpm),
    ("Quais máquinas tiveram mais falhas nas últimas 24 horas?", q_falhas_24h),
    ("Quais máquinas tiveram mais falhas nos últimos 7 dias?", q_falhas_7d),
    ("Quais máquinas tiveram mais falhas nos últimos 30 dias?", q_falhas_30d),
    ("Quais máquinas mais tiveram superaquecimento?", q_superaquecimento),
    ("Quais máquinas mais tiveram desbalanceamento?", q_desbalanceamento),
    ("Quais máquinas mais tiveram falha mecânica?", q_falha_mecanica),
    ("Quando foi a última falha de cada máquina?", q_ultima_falha),
    ("Qual o risco de falha previsto pelo modelo para cada máquina?", q_previsao_risco),
    ("Quando será a próxima manutenção prevista de cada máquina?", q_proxima_manutencao),
    ("Qual a média de temperatura, vibração, corrente e rotação da planta nas últimas 24 h?", q_media_planta_24h),
    ("Quais máquinas ficaram menos tempo em operação normal na semana?", q_percentual_normal),
    ("Quais ordens de serviço estão abertas ou em andamento?", q_manutencoes_abertas),
    ("Quais máquinas têm mais manutenções registradas?", q_mais_manutencoes),
    ("Quais máquinas ficaram mais horas paradas?", q_horas_paradas),
    ("Em que horários do dia ocorrem mais falhas?", q_falhas_por_hora),
    ("Qual o ranking de saúde das máquinas?", q_ranking_saude),
    ("Quais máquinas devem ser substituídas ou revisadas?", q_substituir),
    ("Quais máquinas estão em estado crítico sustentado (alerta real)?", q_criticas_duradouras),
    ("Quais as maiores temperaturas dos últimos 7 dias?", q_temperatura_maxima_7d),
    ("Quais as maiores vibrações dos últimos 7 dias?", q_vibracao_maxima_7d),
    ("Quais as maiores correntes dos últimos 7 dias?", q_corrente_maxima_7d),
    ("Quais as menores rotações dos últimos 7 dias?", q_rpm_minimo_7d),
    ("As falhas aumentaram ou diminuíram de ontem para hoje?", q_comparar_hoje_ontem),
    ("Quais máquinas passaram 30 dias sem nenhuma falha?", q_maquinas_sem_falha),
    ("Qual planta tem mais falhas?", q_planta_pior),
    ("Qual fabricante tem mais falhas?", q_por_fabricante),
    ("Como estão as máquinas de criticidade alta?", q_criticidade),
    ("Quais são os dados de placa de cada máquina?", q_potencia),
    ("Quais máquinas estão sem cadastro técnico ou sem foto?", q_sem_cadastro),
    ("Quais são as máquinas mais antigas da planta?", q_mais_antigas),
    ("Qual a relação entre manutenções preventivas e corretivas?", q_preventivas_vs_corretivas),
    ("Quantas manutenções foram feitas por mês?", q_manutencoes_mes),
    ("Quantas manutenções cada técnico registrou?", q_tecnicos),
    ("Quais peças são mais trocadas?", q_pecas),
    ("Quais máquinas estão sem manutenção registrada?", q_sem_manutencao),
    ("Qual o tempo médio de reparo (MTTR)?", q_tempo_medio_reparo),
    ("Qual a disponibilidade das máquinas?", q_disponibilidade),
    ("Quais são as últimas manutenções registradas?", q_ultimas_manutencoes),
    ("Quem está cadastrado para receber os alertas?", q_funcionarios),
    ("Quais alertas já foram enviados pelo sistema?", q_alertas_enviados),
    ("O que eu devo fazer agora? (prioridades)", q_o_que_fazer_agora),
    ("O que causa superaquecimento e como resolver?", q_causas_superaquecimento),
    ("O que causa vibração alta e como resolver?", q_causas_vibracao),
    ("O que causa queda de rotação e como resolver?", q_causas_queda_rpm),
    ("Qual é o plano de manutenção preventiva?", q_plano_preventivo),
    ("Como funciona o modelo de previsão de falhas?", q_como_modelo_funciona),
    ("Quais são as faixas de operação de cada variável?", q_faixas),
    ("Quantas leituras o sistema tem armazenadas?", q_leituras_por_dia),
    ("Quais os horários mais quentes da planta?", q_horario_pico_temperatura),
    ("Qual o cadastro completo das máquinas?", q_cadastro),
]

# Extras usadas em outras telas
EXTRAS = {"cadastro": q_cadastro, "mais_antigas": q_mais_antigas, "faixas": q_faixas, "ultimas_manutencoes": q_ultimas_manutencoes}


def responder_pronta(indice):
    pergunta, fn = CARDAPIO[indice]
    try:
        return fn()
    except Exception as e:
        return f"Não consegui calcular esta resposta agora ({type(e).__name__}: {e})."
