"""
Cadastro de Funcionários e Alertas.

- Cadastro (só o gerente): nome, cargo, e-mail, telefone e planta.
- Envio manual de alertas: monta o relatório de falha de uma máquina e envia
  por e-mail e WhatsApp para os cadastrados que recebem alertas.
- Histórico dos alertas enviados e status dos canais.
"""
import pandas as pd
import streamlit as st

from features.estilos import abas

from auth.auth import eh_gerente, nome_usuario_atual
from features.alertas import (
    relatorio_falha, enviar_alerta, enviar_email, link_whatsapp, destinatarios,
    email_configurado, whatsapp_automatico_configurado, telefone_plantao,
    panorama_criticos, verificar_e_alertar_criticos, limite_minutos_automatico,
    verificacao_automatica_ligada, definir_limite_minutos, MINUTOS_MIN, MINUTOS_MAX,
)
from features.limites import classificar_status
from providers.db_mongo import (
    FuncionarioRepository, NotificacaoRepository, EquipamentoRepository,
    TelemetriaRepository, LocalizacaoRepository, MongoIndisponivelError,
)


def _plantas():
    return ["Todas as plantas"] + list(LocalizacaoRepository.obter_plantas_e_areas().keys())


# ---------------------------------------------------------------------------
def _aba_cadastro():
    if not eh_gerente():
        st.info("Somente o **Gerente de Manutenção** pode cadastrar ou alterar funcionários. "
                "Abaixo está a lista de quem recebe os alertas.")
    try:
        pessoas = FuncionarioRepository.listar()
    except MongoIndisponivelError as e:
        st.error(str(e))
        return

    if eh_gerente():
        with st.form("form_func", clear_on_submit=True):
            st.markdown("**Novo funcionário**")
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome do funcionário *")
            cargo = c2.selectbox("Cargo *", FuncionarioRepository.CARGOS)
            c3, c4 = st.columns(2)
            email = c3.text_input("E-mail *", placeholder="nome@empresa.com")
            telefone = c4.text_input("Telefone (WhatsApp) *", placeholder="(DD) 123456789")
            c5, c6 = st.columns(2)
            planta = c5.selectbox("Planta onde trabalha *", _plantas()[1:])
            receber = c6.checkbox("Receber alertas de falha e manutenção", value=True)
            if st.form_submit_button("➕ Cadastrar funcionário", type="primary"):
                from features.alertas import so_digitos
                if not nome.strip():
                    st.error("Informe o nome do funcionário.")
                elif "@" not in email:
                    st.error("Informe um e-mail válido (ex.: nome@empresa.com).")
                elif len(so_digitos(telefone)) < 10:
                    st.error("Informe o telefone com DDD — ex.: (11) 912345678.")
                else:
                    try:
                        fid = FuncionarioRepository.criar({
                            "nome": nome.strip(), "cargo": cargo, "email": email.strip().lower(),
                            "telefone": telefone.strip(), "planta": planta,
                            "receber_alertas": bool(receber), "criado_por": nome_usuario_atual(),
                        })
                        st.success(f"Funcionário #{fid} cadastrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível cadastrar (e-mail duplicado?): {e}")

    st.markdown("**Funcionários cadastrados**")
    if not pessoas:
        st.info("Nenhum funcionário cadastrado ainda. Sem cadastro, os alertas não têm para quem ir.")
        return
    df = pd.DataFrame([{
        "#": p.get("func_id"), "Nome": p.get("nome"), "Cargo": p.get("cargo"), "E-mail": p.get("email"),
        "Telefone": p.get("telefone"), "Planta": p.get("planta"),
        "Recebe alertas": "✅" if p.get("receber_alertas") else "—",
    } for p in pessoas])
    st.dataframe(df, use_container_width=True, hide_index=True)

    if eh_gerente():
        with st.expander("✏️ Editar / excluir"):
            ids = {f"#{p['func_id']} · {p['nome']} ({p['cargo']})": p["func_id"] for p in pessoas}
            escolha = st.selectbox("Funcionário", list(ids.keys()), key="func_edit")
            fid = ids[escolha]
            atual = FuncionarioRepository.buscar(fid) or {}
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome", value=atual.get("nome", ""), key=f"fn_{fid}")
            cargo = c2.selectbox("Cargo", FuncionarioRepository.CARGOS,
                                 index=FuncionarioRepository.CARGOS.index(atual["cargo"]) if atual.get("cargo") in FuncionarioRepository.CARGOS else 0,
                                 key=f"fc_{fid}")
            c3, c4 = st.columns(2)
            email = c3.text_input("E-mail", value=atual.get("email", ""), key=f"fe_{fid}")
            telefone = c4.text_input("Telefone", value=atual.get("telefone", ""), key=f"ft_{fid}")
            c5, c6 = st.columns(2)
            plantas = _plantas()[1:]
            planta = c5.selectbox("Planta", plantas,
                                  index=plantas.index(atual["planta"]) if atual.get("planta") in plantas else 0,
                                  key=f"fp_{fid}")
            receber = c6.checkbox("Receber alertas", value=bool(atual.get("receber_alertas", True)), key=f"fr_{fid}")
            b1, b2 = st.columns(2)
            if b1.button("💾 Salvar alterações", key=f"fs_{fid}", use_container_width=True):
                FuncionarioRepository.atualizar(fid, {"nome": nome, "cargo": cargo, "email": email.lower(),
                                                      "telefone": telefone, "planta": planta,
                                                      "receber_alertas": bool(receber)})
                st.success("Atualizado.")
                st.rerun()
            if b2.button("🗑️ Excluir", key=f"fd_{fid}", use_container_width=True):
                FuncionarioRepository.excluir(fid)
                st.rerun()


# ---------------------------------------------------------------------------
def _aba_envio():
    st.markdown("**Enviar alerta manual para os funcionários cadastrados**")
    tags = TelemetriaRepository.obter_tags_disponiveis()
    if not tags:
        st.info("Sem máquinas com telemetria.")
        return
    c1, c2 = st.columns([1, 2])
    tag = c1.selectbox("Máquina", tags, key="al_tag")
    planta_filtro = c2.selectbox("Enviar para funcionários da planta", _plantas(), key="al_planta")

    leitura = TelemetriaRepository.obter_ultima_leitura(tag) or {}
    try:
        equipamento = EquipamentoRepository.buscar_por_tag(tag) or {}
    except MongoIndisponivelError:
        equipamento = {}
    status, ic = classificar_status(leitura.get("Temperatura"), leitura.get("Vibracao"),
                                    leitura.get("Corrente"), leitura.get("RPM"), leitura.get("FalhaCodigo", 0))
    st.caption(f"Última leitura de {tag}: {ic} {status}")

    texto_padrao = relatorio_falha(tag, leitura, status=status, equipamento=equipamento)
    texto = st.text_area("Mensagem do alerta (pode editar antes de enviar)", value=texto_padrao, height=280, key="al_texto")

    emails, telefones = destinatarios(planta=None if planta_filtro == "Todas as plantas" else planta_filtro)
    st.caption(f"Destinatários: {len(emails)} e-mail(s) · {len(telefones)} telefone(s). "
               + ("E-mail configurado ✅" if email_configurado() else "E-mail não configurado ⚠️") + " · "
               + ("WhatsApp automático ✅" if whatsapp_automatico_configurado() else "WhatsApp por link (1 clique)"))

    if st.button("📨 Enviar alerta agora", type="primary", disabled=not (emails or telefones)):
        res = enviar_alerta(f"[FORZY ALERTA] {tag} — {status}", texto,
                            planta=None if planta_filtro == "Todas as plantas" else planta_filtro,
                            origem="manual", tag=tag, usuario=nome_usuario_atual())
        (st.success if res["email_ok"] else st.warning)(res["email_msg"])
        (st.success if res["whatsapp_ok"] else st.info)(res["whatsapp_msg"])
        st.session_state["al_links"] = res["links"]

    links = st.session_state.get("al_links") or [(t, link_whatsapp(texto, t)) for t in telefones]
    if links:
        st.markdown("**Enviar pelo WhatsApp com um clique:**")
        cols = st.columns(min(len(links), 4))
        for i, (tel, url) in enumerate(links):
            cols[i % len(cols)].link_button(f"📱 {tel}", url, use_container_width=True)


def _aba_historico():
    try:
        docs = NotificacaoRepository.listar(50)
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    if not docs:
        st.info("Nenhum alerta enviado ainda pelo app.")
        return
    df = pd.DataFrame([{
        "Quando": d["enviado_em"].strftime("%d/%m/%Y %H:%M") if hasattr(d.get("enviado_em"), "strftime") else "-",
        "Origem": d.get("origem"), "Máquina": d.get("TAG", "-"), "Assunto": d.get("assunto", "")[:60],
        "E-mails": len(d.get("emails") or []), "Telefones": len(d.get("telefones") or []),
        "E-mail": "✅" if d.get("email_ok") else "⚠️", "WhatsApp": "✅" if d.get("whatsapp_ok") else "⚠️",
        "Por": d.get("usuario", "-"),
    } for d in docs])
    st.dataframe(df, use_container_width=True, hide_index=True)
    with st.expander("Ver a última mensagem enviada"):
        st.code(docs[0].get("texto", ""), language=None)


def _aba_config():
    st.markdown("**Como os alertas funcionam**")
    st.markdown(
        "- **Automático (24 h por dia):** o script `scripts/monitor_alertas.py` roda em outro terminal, "
        "verifica a cada 60 s a última leitura de cada máquina e envia e-mail quando o estado é Alerta ou "
        "Crítico — sem repetir o mesmo alerta (controle na coleção `alertas_enviados`). "
        "Para ligar: duplo clique em `monitor_alertas.bat`.\n"
        "- **Manual:** a aba *Enviar alerta* acima manda o relatório da máquina escolhida para todos os "
        "funcionários cadastrados (e-mail + WhatsApp).\n"
        "- **Manutenção registrada:** ao salvar uma OS, o gerente é avisado automaticamente por e-mail "
        "e WhatsApp com o resumo do serviço."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("E-mail (Gmail)", "Configurado ✅" if email_configurado() else "Pendente ⚠️")
    c2.metric("WhatsApp automático", "Configurado ✅" if whatsapp_automatico_configurado() else "Por link")
    c3.metric("Telefone de plantão", telefone_plantao())
    if not whatsapp_automatico_configurado():
        st.info("O WhatsApp automático (sem clique) exige uma conta Twilio. Sem ela, o app gera o link "
                "`wa.me` com a mensagem pronta — basta clicar e enviar. Para ativar, preencha no "
                "`.streamlit/secrets.toml`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` e `TWILIO_WHATSAPP_FROM`.")
    st.caption(f"O telefone de plantão exibido na tela de login vem de `ALERTA_TELEFONE` no secrets.toml "
               f"(atual: {telefone_plantao()}).")


def _aba_automatico():
    limite = limite_minutos_automatico()
    st.markdown(f"**Alerta automático para o Gerente de Manutenção — {limite} minutos em estado crítico**")
    st.caption(
        f"Quando uma máquina permanece em estado **crítico por {limite} minutos seguidos**, o sistema "
        "envia sozinho o relatório de falha por e-mail (e WhatsApp) para os funcionários cadastrados "
        "com cargo de gerente. Picos isolados não disparam nada, e o mesmo episódio nunca é enviado "
        "duas vezes. O envio manual da aba anterior continua funcionando normalmente."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Limite para disparo", f"{limite} min")
    c2.metric("Verificação automática", "Ligada ✅" if verificacao_automatica_ligada() else "Desligada ⚠️")
    emails_g, _ = destinatarios(apenas_gerentes=True)
    c3.metric("Gerentes que recebem", len(emails_g))

    # --- Calibração do tempo ---
    with st.container(border=True):
        st.markdown("**⏱️ Calibração do tempo de análise**")
        st.caption("Quanto tempo a máquina precisa ficar em estado crítico, sem interrupção, para o "
                   "e-mail sair sozinho ao Gerente de Manutenção. Valores menores avisam mais cedo, "
                   "mas aumentam a chance de alarme por oscilação passageira; valores maiores só "
                   "avisam quando o problema já se confirmou.")
        if not eh_gerente():
            st.info(f"Ajuste disponível apenas para o Gerente de Manutenção. Valor atual: **{limite} minutos**.")
        else:
            cc1, cc2 = st.columns([3, 1])
            novo_valor = cc1.slider(
                "Minutos em estado crítico para disparar", min_value=MINUTOS_MIN, max_value=MINUTOS_MAX,
                value=limite, step=5, key="cal_minutos",
                help="De 10 minutos (mais sensível) a 1 hora (mais conservador).")
            cc2.write("")
            cc2.write("")
            if cc2.button("💾 Salvar", type="primary", use_container_width=True, key="cal_salvar"):
                efetivo = definir_limite_minutos(novo_valor, usuario=nome_usuario_atual())
                st.success(f"Calibração salva: o alerta automático passa a disparar com "
                           f"**{efetivo} minutos** de estado crítico contínuo.")
                st.rerun()
            faixa = ("mais sensível — avisa cedo, pode pegar oscilação passageira" if novo_valor <= 15
                     else "equilibrado — recomendado para a maioria das plantas" if novo_valor <= 35
                     else "mais conservador — só avisa com o problema já confirmado")
            st.caption(f"Selecionado: **{novo_valor} minutos** · {faixa}. "
                       f"Com leituras a cada 10 minutos, isso equivale a cerca de "
                       f"{max(1, round(novo_valor / 10))} leitura(s) críticas seguidas.")
    if emails_g:
        st.caption("Recebem o alerta automático: " + ", ".join(emails_g))
    else:
        st.warning("Nenhum gerente cadastrado com 'receber alertas' marcado — sem isso o alerta "
                   "automático não tem para quem ir. Cadastre na aba **Funcionários**.")

    st.markdown("**Situação agora**")
    try:
        linhas = panorama_criticos()
    except Exception as e:
        st.error(f"Não foi possível verificar: {e}")
        return
    if not linhas:
        st.success("🟢 Nenhuma máquina em estado crítico neste momento.")
    else:
        df = pd.DataFrame([{
            "Máquina": l["TAG"],
            "Em estado crítico há": f"{l['minutos']} min",
            "Leituras seguidas": l["leituras"],
            "Situação": ("🔴 Limite atingido — alerta disparado"
                         if l["atingiu_limite"] else f"🟡 Faltam {l['faltam']} min para disparar"),
        } for l in linhas])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption("A verificação roda sozinha a cada 5 minutos enquanto o app estiver aberto, e "
                   "continuamente quando o monitor (`monitor_alertas.bat`) estiver em execução.")

    if st.button("🔄 Verificar e enviar agora", type="primary"):
        with st.spinner("Verificando as máquinas..."):
            res = verificar_e_alertar_criticos()
        if not res:
            st.info(f"Nenhuma máquina atingiu {limite} minutos seguidos em estado crítico "
                    "(ou o episódio já havia sido notificado).")
        for r in res:
            (st.success if r["email_ok"] else st.warning)(
                f"{r['TAG']} — crítico há {r['minutos']} min · {r['email_msg']}")

    with st.expander("⚙️ Outras formas de configurar"):
        st.markdown(
            "O tempo ajustado no controle acima fica gravado no banco e vale para todos os "
            "usuários, sem reiniciar o app.\n\n"
            "Para definir um valor inicial ou desligar o disparo automático, use o "
            "`.streamlit/secrets.toml`:\n\n"
            "```toml\n"
            "ALERTA_MINUTOS_CRITICOS = 30   # valor inicial, se nada foi calibrado na tela\n"
            "ALERTA_AUTOMATICO = 1          # 0 desliga o disparo automático\n"
            "```"
        )


def render_funcionarios():
    st.title("👥 Cadastro de Funcionários e Alertas")
    st.caption("Quem recebe os alertas de falha e de manutenção por e-mail e WhatsApp. "
               "O cadastro é feito pelo Gerente de Manutenção.")
    aba = abas(["👤 Funcionários", "🚨 Alerta automático", "📨 Enviar alerta",
                "🗂️ Histórico", "⚙️ Como funciona"], "aba_func")
    if aba.startswith("👤"):
        _aba_cadastro()
    elif aba.startswith("🚨"):
        _aba_automatico()
    elif aba.startswith("📨"):
        _aba_envio()
    elif aba.startswith("🗂️"):
        _aba_historico()
    else:
        _aba_config()
