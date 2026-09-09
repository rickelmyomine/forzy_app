"""
Monta o contexto (grounding) do Chat IA a partir do MongoDB e da base de
conhecimento, para o Gemini responder com os dados da planta e citar fontes.

Blocos:
  1. Persona e regras (cita fonte, não inventa números, diz o nível de confiança)
  2. Cadastro das máquinas (simplificado)
  3. Telemetria: estado atual + resumo das últimas 24 h e 7 dias por máquina
     (médias, máximos, leituras em falha por tipo, última falha)
  4. Previsões do modelo de falhas por máquina
  5. Manutenções registradas (últimas OS; todas as OS da máquina em foco)
  6. Máquina em foco (quando o usuário veio de outra tela): últimas leituras
  7. Documentação recuperada (RAG) relevante à pergunta + limiares
"""
from datetime import datetime, timedelta, timezone

from features.base_conhecimento import buscar, formatar_para_contexto
from features.limites import NOMES_FALHA, classificar_status, descricao_limites
from features.previsao import prever, modelo_disponivel
from providers.db_mongo import (
    EquipamentoRepository, TelemetriaRepository, ManutencaoRepository,
    PrevisaoRepository, MongoIndisponivelError,
)


def _fmt_dt(d):
    if d is None:
        return "-"
    if hasattr(d, "astimezone"):
        try:
            return d.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m %H:%M")
        except Exception:
            return d.strftime("%d/%m %H:%M")
    return str(d)


def _bloco_cadastro(cadastro, tags):
    linhas = []
    for t in tags:
        e = cadastro.get(t)
        if not e:
            linhas.append(f"- {t}: sem cadastro técnico (só telemetria)")
            continue
        partes = [f"{e.get('Fabricante', '-')} {e.get('Modelo', '')}".strip(), f"potência {e.get('Potencia', '-')}",
                  f"tensão {e.get('Tensao', '-')}", f"corrente nominal {e.get('Corrente', '-')}",
                  f"rotação nominal {e.get('RPM', '-')}", f"planta {e.get('Planta', '-')}",
                  f"criticidade {e.get('Criticidade', '-')}", f"instalado em {e.get('AnoInstalacao', '-')}"]
        if e.get("Observacoes"):
            partes.append(f"obs: {str(e['Observacoes'])[:160]}")
        docs = []
        if e.get("datasheet_nome"):
            docs.append("folha de dados PDF")
        if e.get("site_url"):
            docs.append("site do fabricante")
        if e.get("foto"):
            docs.append("foto")
        if docs:
            partes.append("documentos: " + ", ".join(docs))
        linhas.append(f"- {t}: " + "; ".join(partes))
    return "\n".join(linhas) or "Nenhum equipamento cadastrado."


def _bloco_telemetria(tags):
    agora = datetime.now(timezone.utc)
    r24 = TelemetriaRepository.resumo_intervalo(agora - timedelta(hours=24), agora, tags)
    r7 = TelemetriaRepository.resumo_intervalo(agora - timedelta(days=7), agora, tags)
    ultimas = TelemetriaRepository.ultimas_leituras(tags)
    linhas = []
    for t in tags:
        ult = ultimas.get(t)
        if not ult:
            linhas.append(f"- {t}: sem leituras")
            continue
        status, _ = classificar_status(ult.get("Temperatura"), ult.get("Vibracao"), ult.get("Corrente"), ult.get("RPM"), ult.get("FalhaCodigo", 0))
        falha_atual = NOMES_FALHA.get(int(ult.get("FalhaCodigo") or 0), "")
        atual = (f"agora ({_fmt_dt(ult.get('timestamp'))}): {status}"
                 + (f" — {falha_atual}" if falha_atual and falha_atual != "Normal" else "")
                 + f", T {ult.get('Temperatura')}°C, V {ult.get('Vibracao')} mm/s, I {ult.get('Corrente')} A, {ult.get('RPM', 0):.0f} RPM")
        a = r24.get(t)
        b = r7.get(t)
        s24 = (f"24h: T méd {a['temp_med']:.1f}/máx {a['temp_max']:.1f}°C, V méd {a['vib_med']:.2f}/máx {a['vib_max']:.2f}, "
               f"I máx {a['cor_max']:.1f} A, RPM mín {a['rpm_min']:.0f}, leituras em falha {a['falhas']} "
               f"(desbal. {a['falhas_1']}, superaq. {a['falhas_2']}, mec. {a['falhas_3']})") if a else "24h: sem dados"
        s7 = (f"7d: {b['n']} leituras, {b['falhas']} em falha (desbal. {b['falhas_1']}, superaq. {b['falhas_2']}, mec. {b['falhas_3']}), "
              f"T máx {b['temp_max']:.1f}°C, V máx {b['vib_max']:.2f} mm/s, última falha {_fmt_dt(b.get('ultima_falha'))}") if b else "7d: sem dados"
        linhas.append(f"- {t} | {atual} | {s24} | {s7}")
    return "\n".join(linhas)


def _bloco_previsoes(tags):
    if not modelo_disponivel():
        return "Modelo de previsão não treinado."
    salvas = PrevisaoRepository.obter_todas()
    desatualizadas = [t for t in tags
                      if t not in salvas
                      or (datetime.now(timezone.utc) - salvas[t].get("gerado_em", datetime(2000, 1, 1, tzinfo=timezone.utc)).replace(tzinfo=timezone.utc)) > timedelta(minutes=30)]
    if desatualizadas:
        for t, ult in TelemetriaRepository.ultimas_n_por_tag(desatualizadas, 5).items():
            p = prever(ult) if ult else None
            if p:
                PrevisaoRepository.salvar(t, p)
                salvas[t] = p
    linhas = []
    for t in tags:
        p = salvas.get(t)
        if not p:
            linhas.append(f"- {t}: sem previsão")
            continue
        probs = ", ".join(f"{k} {v*100:.0f}%" for k, v in p["probabilidades"].items())
        linhas.append(f"- {t}: {p['classe_nome']} (risco {p['nivel_risco'].lower()}, {p['risco']*100:.0f}%) — {probs}")
    return "\n".join(linhas)


def _bloco_manutencoes(tags, tag_foco=None):
    try:
        if tag_foco:
            docs = ManutencaoRepository.listar(tag=tag_foco, limite=30)
        else:
            docs = ManutencaoRepository.listar(limite=25)
            docs = [d for d in docs if d.get("TAG") in tags] or docs
    except MongoIndisponivelError:
        return "MongoDB indisponível."
    if not docs:
        return "Nenhuma manutenção registrada" + (f" para {tag_foco}." if tag_foco else ".")
    linhas = []
    for d in docs:
        data = d.get("data")
        data_txt = data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else str(data)
        tele = d.get("telemetria_no_momento") or {}
        linhas.append(
            f"- OS #{d.get('os_id')} {d.get('TAG')} {data_txt} [{d.get('tipo')}/{d.get('status')}/{d.get('categoria_nome', '')}] "
            f"problema: {d.get('descricao_problema', '')[:140]}; serviço: {d.get('servico_executado', '')[:140]}; "
            f"peças: {d.get('pecas_trocadas', '') or '-'}; parada {d.get('tempo_parada_horas', 0)} h; técnico {d.get('tecnico', '-')}"
            + (f"; telemetria no registro T {tele.get('Temperatura')}°C V {tele.get('Vibracao')} mm/s" if tele else "")
            + (f"; {len(d.get('fotos') or [])} foto(s)" if d.get("fotos") else "")
        )
    try:
        est = ManutencaoRepository.estatisticas()
        cab = f"Total de OS no sistema: {est['total']} (por status: {est['por_status']}; por tipo: {est['por_tipo']})\n"
    except MongoIndisponivelError:
        cab = ""
    return cab + "\n".join(linhas)


def _bloco_foco(tag):
    ult = TelemetriaRepository.obter_ultimas_n(tag, 12)
    if not ult:
        return f"{tag}: sem leituras."
    linhas = [f"  {_fmt_dt(l.get('timestamp'))}: T {l.get('Temperatura')}°C, V {l.get('Vibracao')} mm/s, I {l.get('Corrente')} A, "
              f"{l.get('RPM', 0):.0f} RPM, {NOMES_FALHA.get(int(l.get('FalhaCodigo') or 0))}" for l in ult]
    dist = TelemetriaRepository.obter_distribuicao_falhas(tag)
    dist_txt = ", ".join(f"{NOMES_FALHA.get(int(k), k)}: {v}" for k, v in sorted(dist.items()))
    return f"Últimas 12 leituras de {tag} (mais antiga primeiro):\n" + "\n".join(linhas) + \
        f"\nDistribuição de todo o histórico de {tag} por estado: {dist_txt}"


PERSONA = """Você é o assistente técnico de manutenção da planta Forzy, integrado ao sistema de gestão
da planta (telemetria, cadastro, manutenções e modelo de previsão). Responde em português do
Brasil, de forma objetiva, para técnicos e para o gerente de manutenção.

REGRAS
1. Use os DADOS DA PLANTA abaixo como fonte de verdade para números, status, falhas, previsões
   e manutenções. Nunca invente valores; se algo não estiver nos dados, diga isso.
2. Use a DOCUMENTAÇÃO recuperada para procedimentos, limiares e explicações; ao usá-la, cite a
   fonte entre colchetes no formato [Fonte: nome — seção].
3. O que não estiver nos dados nem na documentação pode ser pesquisado na internet (manuais de
   fabricantes, normas, boas práticas) — cite o site consultado e deixe claro que veio de fora.
   Ao recomendar substituição de uma máquina, indique o site do fabricante do cadastro.
4. Termine análises de máquina com: estado, causa provável, ação recomendada (com prazo:
   imediata / programar / monitorar) e nível de confiança (alto/médio/baixo).
5. Uma previsão do modelo ou um alerta é um sinal para priorizar inspeção, não um diagnóstico
   confirmado — deixe isso claro quando for relevante.
6. Seja conciso: use listas curtas; sem introduções longas."""


def montar_contexto(pergunta, planta=None, tag_foco=None, origem=None):
    """Retorna (contexto_str, fontes_recuperadas)."""
    try:
        cadastro = {e["TAG"]: e for e in EquipamentoRepository.buscar_todos() if e.get("TAG")}
    except MongoIndisponivelError:
        cadastro = {}
    tags = sorted(set(cadastro) | set(TelemetriaRepository.obter_tags_disponiveis()))
    if planta and planta != "Todas as plantas":
        filtradas = [t for t in tags if cadastro.get(t, {}).get("Planta") in (planta, None)]
        tags = filtradas or tags

    boost = None
    pl = (pergunta or "").lower()
    for termo in ("superaquecimento", "desbalanceamento", "mecânica", "preventiva", "corretiva"):
        if termo in pl:
            boost = termo
            break
    fontes = buscar(pergunta + (f" {tag_foco}" if tag_foco else ""), k=4, boost_categoria=boost)

    partes = [
        PERSONA,
        f"\n[Contexto de navegação] Planta filtrada: {planta or 'Todas as plantas'}."
        + (f" Máquina em foco: {tag_foco}." if tag_foco else "")
        + (f" O usuário veio da tela: {origem}." if origem else "")
        + f" Agora: {datetime.now(timezone(timedelta(hours=-3))):%d/%m/%Y %H:%M} (horário de Brasília).",
        "\n[Limiares operacionais usados no dashboard]\n" + descricao_limites(),
        "\n[DADOS DA PLANTA — Cadastro dos equipamentos]\n" + _bloco_cadastro(cadastro, tags),
        "\n[DADOS DA PLANTA — Telemetria: estado atual, últimas 24 h e 7 dias]\n" + _bloco_telemetria(tags),
        "\n[DADOS DA PLANTA — Previsão do modelo de falhas (última janela de 5 leituras)]\n" + _bloco_previsoes(tags),
        "\n[DADOS DA PLANTA — Manutenções registradas pelos técnicos]\n" + _bloco_manutencoes(tags, tag_foco),
    ]
    if tag_foco:
        partes.append(f"\n[MÁQUINA EM FOCO — {tag_foco}]\n" + _bloco_foco(tag_foco))
    try:
        import streamlit as st
        resumo_frota = st.session_state.pop("chat_frota_resumo", None)
    except Exception:
        resumo_frota = None
    if resumo_frota is None and (origem == "analise_de_frota" or any(w in pl for w in ("trocar", "substitu", "comprar", "frota", "atualizar"))):
        from features.frota import tabela_frota, resumo_frota_texto
        resumo_frota = resumo_frota_texto(tabela_frota(30), top=10)
    if resumo_frota:
        partes.append("\n[DADOS DA PLANTA — Análise de riscos (30 dias): saúde, manutenções, críticas, alertas e recomendação por regras]\n" + resumo_frota)
    if fontes:
        partes.append("\n[DOCUMENTAÇÃO recuperada para esta pergunta]\n" + formatar_para_contexto(fontes))
    return "\n".join(partes), fontes
