"""
Manutenções — ordens de serviço registradas pelos técnicos, com fotos
antes/durante/depois, captura automática da telemetria no momento do
registro e classificação automática do evento.
"""
from datetime import datetime, date, time, timezone

import pandas as pd
import streamlit as st

from features.estilos import abas

from auth.auth import nome_usuario_atual, perfil_atual, eh_gerente
from ui.navegacao import botao_ia
from features.classificador_texto import classificar_evento, CATEGORIAS
from features.imagens import comprimir_para_b64, b64_para_bytes, tamanho_legivel
from providers.db_mongo import (
    EquipamentoRepository,
    ManutencaoRepository,
    TelemetriaRepository,
    TipoFalhaRepository,
    MongoIndisponivelError,
)

_MAX_FOTOS = 6


def _tags_disponiveis():
    try:
        tags = set(EquipamentoRepository.listar_tags())
    except MongoIndisponivelError:
        tags = set()
    tags |= set(TelemetriaRepository.obter_tags_disponiveis())
    return sorted(tags)


def _telemetria_no_momento(tag):
    leitura = TelemetriaRepository.obter_ultima_leitura(tag)
    if not leitura:
        return None
    campos = {k: leitura.get(k) for k in ("Temperatura", "Vibracao", "Corrente", "RPM", "Status", "FalhaCodigo", "timestamp")}
    if campos.get("FalhaCodigo") is not None:
        try:
            campos["FalhaNome"] = TipoFalhaRepository.obter_nome(campos["FalhaCodigo"])
        except Exception:
            pass
    return campos


def _fotos_upload(prefixo):
    arquivos = st.file_uploader(
        f"Fotos (até {_MAX_FOTOS}) — JPG/PNG", type=["jpg", "jpeg", "png"],
        accept_multiple_files=True, key=f"{prefixo}_fotos",
    )
    fotos = []
    if arquivos:
        arquivos = arquivos[:_MAX_FOTOS]
        cols = st.columns(min(len(arquivos), 3))
        for i, arq in enumerate(arquivos):
            with cols[i % 3]:
                b64, mime, tam = comprimir_para_b64(arq.getvalue())
                st.image(arq.getvalue(), use_container_width=True)
                momento = st.selectbox("Momento", ManutencaoRepository.MOMENTOS_FOTO, key=f"{prefixo}_mom_{i}")
                legenda = st.text_input("Legenda", key=f"{prefixo}_leg_{i}", placeholder=arq.name)
                st.caption(f"{arq.name} → {tamanho_legivel(tam)}")
                fotos.append({"b64": b64, "mime": mime, "momento": momento,
                              "legenda": legenda or arq.name, "arquivo": arq.name})
    return fotos


# ---------------------------------------------------------------------------
def _aba_nova():
    tags = _tags_disponiveis()
    if not tags:
        st.info("Cadastre um equipamento primeiro.")
        return

    c1, c2, c3 = st.columns([1.2, 1, 1])
    tag = c1.selectbox("Equipamento (TAG)", tags, key="man_tag")
    tipo = c2.selectbox("Tipo", ManutencaoRepository.TIPOS, key="man_tipo")
    status = c3.selectbox("Status", ManutencaoRepository.STATUS, index=0, key="man_status")

    c4, c5, c6 = st.columns(3)
    data_dia = c4.date_input("Data", value=date.today(), key="man_data")
    hora = c5.time_input("Hora", value=datetime.now().time().replace(second=0, microsecond=0), key="man_hora")
    tempo_parada = c6.number_input("Tempo de parada (h)", min_value=0.0, step=0.5, key="man_parada")

    descricao = st.text_area("Descrição do problema / motivo *", height=90, key="man_desc",
                             placeholder="O que foi observado? Ruído, aquecimento, vibração, alarme do sistema...")
    servico = st.text_area("Serviço executado", height=90, key="man_serv",
                           placeholder="O que foi feito? Peças, ajustes, medições...")
    pecas = st.text_input("Peças trocadas", key="man_pecas", placeholder="Ex.: rolamento 6205-ZZ, graxa Polyrex EM")

    # Classificação automática ao vivo
    texto_evento = f"{descricao} {servico} {pecas}"
    if texto_evento.strip():
        cat, cat_nome, _ = classificar_evento(texto_evento, tipo)
        st.caption(f"🏷️ Classificação automática do evento: **{cat_nome}** (`{cat}`) — pode ser ajustada abaixo.")
    else:
        cat = "manutencao_preventiva" if tipo == "Preventiva" else "manutencao_corretiva"
    categoria = st.selectbox(
        "Categoria do evento", list(CATEGORIAS.keys()),
        index=list(CATEGORIAS.keys()).index(cat),
        format_func=lambda k: CATEGORIAS[k], key="man_cat",
    )

    # Telemetria no momento
    tele = _telemetria_no_momento(tag)
    with st.expander("📡 Telemetria capturada no momento do registro", expanded=bool(tele)):
        if tele:
            m = st.columns(4)
            m[0].metric("Temperatura", f"{tele.get('Temperatura', '-')} °C")
            m[1].metric("Vibração", f"{tele.get('Vibracao', '-')} mm/s")
            m[2].metric("Corrente", f"{tele.get('Corrente', '-')} A")
            rpm = tele.get("RPM")
            m[3].metric("Rotação", f"{rpm:.0f} RPM" if isinstance(rpm, (int, float)) else "-")
            extra = f"Status: {tele.get('Status', '-')}"
            if tele.get("FalhaNome"):
                extra += f" · Falha: {tele['FalhaNome']}"
            ts = tele.get("timestamp")
            if hasattr(ts, "strftime"):
                extra += f" · leitura de {ts:%d/%m/%Y %H:%M}"
            st.caption(extra + " — salvo junto com a OS para rastreabilidade.")
        else:
            st.caption("Sem leitura de telemetria para esta TAG.")

    st.markdown("**Fotos da intervenção**")
    fotos = _fotos_upload("man")

    if st.button("💾 Registrar manutenção", type="primary"):
        if not descricao.strip():
            st.error("Descreva o problema / motivo da manutenção.")
            return
        agora = datetime.now(timezone.utc)
        registro = {
            "TAG": tag,
            "tipo": tipo,
            "status": status,
            "data": datetime.combine(data_dia, hora),
            "titulo": descricao.strip()[:60],
            "descricao_problema": descricao.strip(),
            "servico_executado": servico.strip(),
            "pecas_trocadas": pecas.strip(),
            "tempo_parada_horas": float(tempo_parada),
            "categoria": categoria,
            "categoria_nome": CATEGORIAS[categoria],
            "telemetria_no_momento": tele,
            "tecnico": nome_usuario_atual(),
            "tecnico_perfil": perfil_atual(),
            "criado_em": agora,
            "fotos": [
                {**f, "enviado_por": nome_usuario_atual(), "enviado_em": agora}
                for f in fotos
            ],
        }
        try:
            os_id = ManutencaoRepository.criar(registro)
        except MongoIndisponivelError as e:
            st.error(str(e))
            return
        st.success(f"OS #{os_id} registrada para {tag} por {nome_usuario_atual()} "
                   f"({len(fotos)} foto(s)).")
        # Avisa o gerente por e-mail / WhatsApp
        try:
            from features.alertas import notificar_manutencao
            equipamento = EquipamentoRepository.buscar_por_tag(tag) or {}
            res = notificar_manutencao({**registro, "os_id": os_id}, equipamento, usuario=nome_usuario_atual())
            if res["email_ok"]:
                st.info(f"📧 Gerente avisado: {res['email_msg']}")
            elif res["emails"]:
                st.warning(f"📧 {res['email_msg']}")
            else:
                st.caption("Nenhum gerente cadastrado para receber o aviso — cadastre em 'Cadastro de Funcionários'.")
            if res["links"]:
                st.markdown("Avisar pelo WhatsApp: " + " · ".join(f"[{t}]({u})" for t, u in res["links"]))
        except Exception as e:
            st.caption(f"Aviso ao gerente não enviado ({type(e).__name__}).")
        for k in list(st.session_state.keys()):
            if k.startswith("man_"):
                st.session_state.pop(k, None)
        st.rerun()


# ---------------------------------------------------------------------------
def _card_os(m):
    d = m.get("data")
    d_txt = d.strftime("%d/%m/%Y %H:%M") if hasattr(d, "strftime") else str(d)
    icone_status = {"Aberta": "🟠", "Em andamento": "🔵", "Concluída": "🟢"}.get(m.get("status"), "⚪")
    resumo = (m.get("descricao_problema") or m.get("titulo") or "")[:70]
    with st.expander(f"{icone_status} OS #{m.get('os_id')} · {m.get('TAG')} · {d_txt} · {m.get('tipo')} — {resumo}"):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Status:** {m.get('status')}")
        c2.markdown(f"**Técnico:** {m.get('tecnico', '-')}")
        c3.markdown(f"**Categoria:** {m.get('categoria_nome', '-')}")
        c4.markdown(f"**Parada:** {m.get('tempo_parada_horas', 0)} h")
        if m.get("descricao_problema"):
            st.markdown(f"**Problema:** {m['descricao_problema']}")
        if m.get("servico_executado"):
            st.markdown(f"**Serviço:** {m['servico_executado']}")
        if m.get("pecas_trocadas"):
            st.markdown(f"**Peças:** {m['pecas_trocadas']}")
        tele = m.get("telemetria_no_momento")
        if tele:
            st.caption(
                f"📡 Telemetria no registro: {tele.get('Temperatura', '-')}°C · "
                f"{tele.get('Vibracao', '-')} mm/s · {tele.get('Corrente', '-')} A · "
                f"{tele.get('RPM', '-')} RPM · {tele.get('Status', '-')}"
                + (f" · {tele['FalhaNome']}" if tele.get("FalhaNome") else "")
            )

        fotos = m.get("fotos") or []
        if fotos:
            completo = ManutencaoRepository.buscar(m["os_id"]) or {}
            fotos_full = completo.get("fotos") or []
            cols = st.columns(min(len(fotos_full), 3) or 1)
            for i, f in enumerate(fotos_full):
                with cols[i % 3]:
                    if f.get("b64"):
                        st.image(b64_para_bytes(f["b64"]), use_container_width=True)
                    st.caption(f"{f.get('momento', '')} — {f.get('legenda', '')}")

        # Ações
        a1, a2, a3 = st.columns([1, 1, 2])
        novo_status = a1.selectbox("Alterar status", ManutencaoRepository.STATUS,
                                   index=ManutencaoRepository.STATUS.index(m.get("status", "Aberta")),
                                   key=f"st_{m['os_id']}")
        if a2.button("Aplicar", key=f"btn_st_{m['os_id']}") and novo_status != m.get("status"):
            ManutencaoRepository.atualizar(m["os_id"], {"status": novo_status}, usuario=nome_usuario_atual())
            st.rerun()

        novas = st.file_uploader("Adicionar fotos a esta OS", type=["jpg", "jpeg", "png"],
                                 accept_multiple_files=True, key=f"add_{m['os_id']}")
        if novas:
            momento = st.selectbox("Momento", ManutencaoRepository.MOMENTOS_FOTO, index=2, key=f"addmom_{m['os_id']}")
            if st.button("Enviar fotos", key=f"btn_add_{m['os_id']}"):
                for arq in novas[:_MAX_FOTOS]:
                    b64, mime, _ = comprimir_para_b64(arq.getvalue())
                    ManutencaoRepository.adicionar_foto(m["os_id"], {
                        "b64": b64, "mime": mime, "momento": momento, "legenda": arq.name,
                        "enviado_por": nome_usuario_atual(), "enviado_em": datetime.now(timezone.utc),
                    })
                st.success("Fotos adicionadas.")
                st.rerun()

        if eh_gerente():
            if st.button("🗑️ Excluir OS (gerente)", key=f"del_{m['os_id']}"):
                ManutencaoRepository.excluir(m["os_id"])
                st.rerun()


def _aba_historico():
    tags = _tags_disponiveis()
    if not tags:
        st.info("Nenhuma máquina cadastrada.")
        return
    padrao = st.session_state.get("consulta_tag")
    c1, c2, c3 = st.columns(3)
    tag = c1.selectbox("Máquina", tags, index=tags.index(padrao) if padrao in tags else 0, key="hist_tag")
    status = c2.selectbox("Status", ["Todos"] + ManutencaoRepository.STATUS, key="hist_status")
    tipo = c3.selectbox("Tipo", ["Todos"] + ManutencaoRepository.TIPOS, key="hist_tipo")

    try:
        docs = ManutencaoRepository.listar(
            tag=tag,
            status=None if status == "Todos" else status,
        )
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    if tipo != "Todos":
        docs = [d for d in docs if d.get("tipo") == tipo]

    botao_ia(tag, f"Resuma o histórico de manutenções do {tag} e diga o que ele indica sobre a condição da máquina.",
             chave=f"ia_hist_{tag}", rotulo=f"🤖 Analisar manutenções do {tag} com a IA", origem="manutencoes")
    if not docs:
        st.info(f"Nenhuma manutenção registrada para {tag} com esses filtros.")
        return

    df = pd.DataFrame([{
        "OS": d.get("os_id"), "Data": d.get("data"), "Tipo": d.get("tipo"),
        "Status": d.get("status"), "Problema": (d.get("descricao_problema") or "")[:60], "Técnico": d.get("tecnico"),
        "Categoria": d.get("categoria_nome"), "Parada (h)": d.get("tempo_parada_horas"),
        "Fotos": len(d.get("fotos") or []),
    } for d in docs])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("#### Detalhes")
    for m in docs[:50]:
        _card_os(m)


def _aba_resumo():
    try:
        est = ManutencaoRepository.estatisticas()
        docs = ManutencaoRepository.listar(limite=1000)
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    c = st.columns(4)
    c[0].metric("Total de OS", est["total"])
    c[1].metric("Abertas", est["por_status"].get("Aberta", 0))
    c[2].metric("Em andamento", est["por_status"].get("Em andamento", 0))
    c[3].metric("Concluídas", est["por_status"].get("Concluída", 0))
    if not docs:
        return
    df = pd.DataFrame(docs)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.to_period("M").astype(str)
    anos = sorted(df["ano"].dropna().astype(int).unique(), reverse=True)
    c1, c2 = st.columns([1, 3])
    ano = c1.selectbox("Ano", ["Todos"] + [str(a) for a in anos], key="res_ano")
    if ano != "Todos":
        df = df[df["ano"] == int(ano)]
    if df.empty:
        st.info("Sem manutenções no ano selecionado.")
        return

    from features.graficos import manutencoes_por_mes, barras_rotuladas, pizza_tipos_os

    por_mes = df.groupby(["mes", "tipo"]).size().unstack(fill_value=0).sort_index()
    st.plotly_chart(manutencoes_por_mes(por_mes), use_container_width=True)
    st.caption("Cada barra é um mês; as cores da legenda acima separam o tipo de manutenção. "
               "Muita **corretiva** (vermelho) em relação à **preventiva** (verde) indica que a planta "
               "está apagando incêndio em vez de prevenir — o ideal é a corretiva ficar abaixo de 30 % do total.")

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(pizza_tipos_os(df["tipo"].value_counts()), use_container_width=True)
        st.caption("Participação de cada tipo de manutenção no período. A legenda à direita mostra a cor "
                   "de cada tipo; passe o mouse para ver a quantidade de OS.")
    with col2:
        top_maq = df["TAG"].value_counts().head(15)
        st.plotly_chart(barras_rotuladas(top_maq, "Máquinas com mais ordens de serviço",
                                         "Máquina", "Ordens de serviço"),
                        use_container_width=True)
        st.caption("As 15 máquinas que mais exigiram manutenção. O número em cima de cada barra é a "
                   "quantidade de OS. Máquinas no topo desta lista são candidatas a revisão ou substituição.")

    if "tempo_parada_horas" in df:
        horas = df.groupby("TAG")["tempo_parada_horas"].sum().sort_values(ascending=False).head(15)
        st.plotly_chart(barras_rotuladas(horas, "Horas paradas por máquina",
                                         "Máquina", "Horas paradas (h)"),
                        use_container_width=True)
        st.caption("Soma das horas em que cada máquina ficou indisponível por manutenção no período. "
                   "É o indicador que traduz manutenção em perda de produção.")

    st.markdown("**Detalhe por mês**")
    for mes, grupo in sorted(df.groupby("mes"), key=lambda x: x[0], reverse=True):
        nome_mes = pd.Period(mes).strftime("%m/%Y")
        with st.expander(f"📅 {nome_mes} — {len(grupo)} OS · {grupo['tempo_parada_horas'].sum():g} h paradas"):
            tabela = grupo[["os_id", "TAG", "data", "tipo", "status", "tecnico", "categoria_nome", "tempo_parada_horas"]].copy()
            tabela.columns = ["OS", "Máquina", "Data", "Tipo", "Status", "Técnico", "Categoria", "Parada (h)"]
            st.dataframe(tabela.sort_values("Data", ascending=False), use_container_width=True, hide_index=True)


def render_manutencao():
    st.title("🛠️ Manutenções")
    st.caption("Registro de ordens de serviço pelos técnicos, com fotos e telemetria do momento — persistido no MongoDB Atlas.")
    aba = abas(["➕ Nova OS", "📋 Histórico", "📊 Resumo"], "aba_manut")
    if aba.startswith("➕"):
        _aba_nova()
    elif aba.startswith("📋"):
        _aba_historico()
    else:
        _aba_resumo()
