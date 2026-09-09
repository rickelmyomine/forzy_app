"""
Alertas de falha e de manutenção: montagem do relatório padrão, envio por
e-mail (Gmail SMTP) e por WhatsApp (Twilio, quando configurado, ou link
wa.me para envio com um clique).

Destinatários: funcionários cadastrados em Cadastro de Funcionários
(coleção `funcionarios`, campo `receber_alertas`).

Configuração em `.streamlit/secrets.toml`:
    GMAIL_USER / GMAIL_APP_PASSWORD        envio de e-mail
    ALERTA_TELEFONE                        telefone de plantão exibido no login
    TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM
                                           WhatsApp automático (opcional)
"""
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from features.limites import NOMES_FALHA
from providers.db_mongo import FuncionarioRepository, NotificacaoRepository, MongoIndisponivelError

FUSO = timezone(timedelta(hours=-3))

# Um alerta só é disparado quando a máquina fica em estado crítico por várias
# leituras seguidas (evita alarme por pico isolado). Como as leituras chegam a
# cada 10 min, 3 leituras ≈ 30 minutos em estado crítico.
LEITURAS_CRITICAS_SEGUIDAS = 3

# Regra do disparo automático para o Gerente de Manutenção: se a máquina
# permanecer em estado crítico por este tempo, o e-mail sai sozinho.
MINUTOS_CRITICOS_AUTOMATICO = 30


def _cfg(chave, padrao=None):
    try:
        import streamlit as st
        if chave in st.secrets:
            return st.secrets[chave]
    except Exception:
        pass
    return os.environ.get(chave, padrao)


def telefone_plantao():
    return _cfg("ALERTA_TELEFONE", "(DD) 123456789")


def so_digitos(telefone):
    return re.sub(r"\D", "", telefone or "")


def numero_internacional(telefone, ddi="55"):
    """(11) 98765-4321 -> 5511987654321"""
    d = so_digitos(telefone)
    if not d:
        return ""
    return d if d.startswith(ddi) and len(d) > 11 else ddi + d


# ---------------------------------------------------------------------------
# Relatórios (texto padrão do projeto)
# ---------------------------------------------------------------------------
def relatorio_falha(tag, leitura, status=None, acao=None, equipamento=None):
    """
    🔧 *RELATÓRIO DE FALHA DO MOTOR*
    *Motor:* MOT-001
    *Descrição:* Estado crítico — Superaquecimento detectado por telemetria.
    ...
    """
    leitura = leitura or {}
    status = status or leitura.get("Status") or "Crítico"
    cod = int(leitura.get("FalhaCodigo") or 0)
    nome_falha = NOMES_FALHA.get(cod, "")
    descricao = f"Estado {status.lower()}"
    if nome_falha and nome_falha != "Normal":
        descricao += f" — {nome_falha}"
    descricao += " detectado por telemetria."

    ts = leitura.get("timestamp")
    if hasattr(ts, "tzinfo"):
        ts = ts.replace(tzinfo=ts.tzinfo or timezone.utc).astimezone(FUSO)
        horario = ts.strftime("%d/%m/%Y %H:%M")
    else:
        horario = datetime.now(FUSO).strftime("%d/%m/%Y %H:%M")

    acao = acao or ("Inspeção e manutenção imediatas." if status == "Crítico"
                    else "Programar inspeção e acompanhar as próximas leituras.")

    linhas = [
        "🔧 *RELATÓRIO DE FALHA DO MOTOR*",
        "",
        f"*Motor:* {tag}",
    ]
    if equipamento:
        ident = " ".join(str(equipamento.get(k, "")) for k in ("Fabricante", "Modelo")).strip()
        if ident:
            linhas.append(f"*Equipamento:* {ident}")
        if equipamento.get("Planta"):
            linhas.append(f"*Planta:* {equipamento['Planta']}")
    linhas += [
        f"*Descrição:* {descricao}",
        f"*Temperatura:* {leitura.get('Temperatura', '-')}°C",
        f"*Vibração:* {leitura.get('Vibracao', '-')} mm/s",
        f"*Corrente:* {leitura.get('Corrente', '-')}A",
    ]
    if leitura.get("RPM") is not None:
        try:
            linhas.append(f"*Rotação:* {float(leitura['RPM']):.0f} RPM")
        except (TypeError, ValueError):
            pass
    linhas += [
        f"*Horário da leitura:* {horario}",
        f"*Ação Recomendada:* {acao}",
    ]
    return "\n".join(linhas)


def relatorio_manutencao(os_registro, equipamento=None):
    """Aviso ao gerente quando um técnico registra uma manutenção."""
    data = os_registro.get("data")
    data_txt = data.strftime("%d/%m/%Y %H:%M") if hasattr(data, "strftime") else str(data)
    tele = os_registro.get("telemetria_no_momento") or {}
    linhas = [
        "🛠️ *MANUTENÇÃO REGISTRADA*",
        "",
        f"*OS:* #{os_registro.get('os_id')}",
        f"*Motor:* {os_registro.get('TAG')}",
    ]
    if equipamento:
        ident = " ".join(str(equipamento.get(k, "")) for k in ("Fabricante", "Modelo")).strip()
        if ident:
            linhas.append(f"*Equipamento:* {ident}")
    linhas += [
        f"*Tipo:* {os_registro.get('tipo')} · *Status:* {os_registro.get('status')}",
        f"*Data:* {data_txt}",
        f"*Técnico:* {os_registro.get('tecnico', '-')}",
        f"*Problema:* {os_registro.get('descricao_problema', '-')}",
    ]
    if os_registro.get("servico_executado"):
        linhas.append(f"*Serviço executado:* {os_registro['servico_executado']}")
    if os_registro.get("pecas_trocadas"):
        linhas.append(f"*Peças trocadas:* {os_registro['pecas_trocadas']}")
    linhas.append(f"*Tempo de parada:* {os_registro.get('tempo_parada_horas', 0)} h")
    if tele:
        linhas.append(f"*Telemetria no registro:* {tele.get('Temperatura', '-')}°C · "
                      f"{tele.get('Vibracao', '-')} mm/s · {tele.get('Corrente', '-')}A")
    if os_registro.get("fotos"):
        linhas.append(f"*Fotos anexadas:* {len(os_registro['fotos'])}")
    return "\n".join(linhas)


def _texto_simples(markdown_whatsapp):
    """Remove os asteriscos do formato WhatsApp para o corpo do e-mail."""
    return markdown_whatsapp.replace("*", "")


# ---------------------------------------------------------------------------
# Canais de envio
# ---------------------------------------------------------------------------
def email_configurado():
    return bool(_cfg("GMAIL_USER") and _cfg("GMAIL_APP_PASSWORD"))


def whatsapp_automatico_configurado():
    return bool(_cfg("TWILIO_ACCOUNT_SID") and _cfg("TWILIO_AUTH_TOKEN") and _cfg("TWILIO_WHATSAPP_FROM"))


def enviar_email(assunto, corpo, destinatarios):
    """Envia um e-mail para vários destinatários. Retorna (ok, mensagem)."""
    destinatarios = [d for d in (destinatarios or []) if d]
    if not destinatarios:
        return False, "Nenhum e-mail cadastrado para receber alertas."
    remetente = _cfg("GMAIL_USER")
    senha = _cfg("GMAIL_APP_PASSWORD")
    if not (remetente and senha):
        return False, ("Credenciais de e-mail não configuradas. Defina GMAIL_USER e "
                       "GMAIL_APP_PASSWORD (senha de app) no .streamlit/secrets.toml.")
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(_texto_simples(corpo))
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = ", ".join(destinatarios)
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha)
            servidor.sendmail(remetente, destinatarios, msg.as_string())
        return True, f"E-mail enviado para {len(destinatarios)} destinatário(s)."
    except Exception as e:
        return False, f"Falha no envio do e-mail: {e}"


def link_whatsapp(texto, telefone=None):
    """Link wa.me que abre o WhatsApp com a mensagem pronta (envio com 1 clique)."""
    msg = urllib.parse.quote(texto)
    numero = numero_internacional(telefone) if telefone else ""
    return f"https://wa.me/{numero}?text={msg}" if numero else f"https://wa.me/?text={msg}"


def enviar_whatsapp(texto, telefones):
    """
    Envio automático via Twilio quando configurado. Retorna (ok, mensagem, links).
    `links` sempre vem preenchido para envio manual com um clique.
    """
    telefones = [t for t in (telefones or []) if so_digitos(t)]
    links = [(t, link_whatsapp(texto, t)) for t in telefones]
    if not telefones:
        return False, "Nenhum telefone cadastrado para receber alertas.", links
    if not whatsapp_automatico_configurado():
        return False, ("WhatsApp automático não configurado (Twilio). Use os links abaixo para enviar "
                       "com um clique, ou configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN e "
                       "TWILIO_WHATSAPP_FROM no secrets.toml."), links
    try:
        from twilio.rest import Client
        cliente = Client(_cfg("TWILIO_ACCOUNT_SID"), _cfg("TWILIO_AUTH_TOKEN"))
        origem = _cfg("TWILIO_WHATSAPP_FROM")
        if not origem.startswith("whatsapp:"):
            origem = "whatsapp:+" + so_digitos(origem)
        enviados = 0
        erros = []
        for t in telefones:
            try:
                cliente.messages.create(body=texto, from_=origem, to=f"whatsapp:+{numero_internacional(t)}")
                enviados += 1
            except Exception as e:
                erros.append(f"{t}: {str(e)[:80]}")
        ok = enviados > 0
        msg = f"WhatsApp enviado para {enviados} número(s)." + (f" Erros: {'; '.join(erros)}" if erros else "")
        return ok, msg, links
    except Exception as e:
        return False, f"Falha no WhatsApp automático: {e}", links


# ---------------------------------------------------------------------------
# Envio para os funcionários cadastrados
# ---------------------------------------------------------------------------
def destinatarios(planta=None, apenas_gerentes=False):
    try:
        pessoas = FuncionarioRepository.listar(planta=planta, apenas_alertas=True)
    except MongoIndisponivelError:
        return [], []
    if apenas_gerentes:
        pessoas = [p for p in pessoas if "gerente" in (p.get("cargo") or "").lower()] or pessoas
    return ([p["email"] for p in pessoas if p.get("email")],
            [p["telefone"] for p in pessoas if p.get("telefone")])


def enviar_alerta(assunto, texto, planta=None, apenas_gerentes=False, origem="manual", tag=None, usuario=None):
    """
    Envia o alerta por e-mail e WhatsApp para os funcionários que recebem alertas.
    Retorna dict com o resultado de cada canal e os links de WhatsApp.
    """
    emails, telefones = destinatarios(planta=planta, apenas_gerentes=apenas_gerentes)
    ok_email, msg_email = enviar_email(assunto, texto, emails)
    ok_zap, msg_zap, links = enviar_whatsapp(texto, telefones)
    try:
        NotificacaoRepository.registrar({
            "origem": origem, "TAG": tag, "assunto": assunto, "texto": texto,
            "emails": emails, "telefones": telefones,
            "email_ok": ok_email, "whatsapp_ok": ok_zap, "usuario": usuario,
        })
    except Exception:
        pass
    return {"emails": emails, "telefones": telefones, "email_ok": ok_email, "email_msg": msg_email,
            "whatsapp_ok": ok_zap, "whatsapp_msg": msg_zap, "links": links}


def notificar_manutencao(os_registro, equipamento=None, usuario=None):
    """Avisa o gerente (e-mail + WhatsApp) que uma manutenção foi registrada."""
    texto = relatorio_manutencao(os_registro, equipamento)
    assunto = f"[FORZY] Manutenção registrada — OS #{os_registro.get('os_id')} · {os_registro.get('TAG')}"
    return enviar_alerta(assunto, texto, planta=(equipamento or {}).get("Planta"),
                         apenas_gerentes=True, origem="manutencao",
                         tag=os_registro.get("TAG"), usuario=usuario)


# ---------------------------------------------------------------------------
# Regra de alerta: só estados críticos sustentados
# ---------------------------------------------------------------------------
def criticos_consecutivos(tag, maximo=12):
    """
    Quantas leituras seguidas (da mais recente para trás) a máquina está em
    estado Crítico. 0 = a última leitura não é crítica.
    """
    from features.limites import classificar_status
    from providers.db_mongo import TelemetriaRepository
    leituras = TelemetriaRepository.obter_historico(tag, limite=maximo)  # mais recente primeiro
    n = 0
    for l in leituras:
        status, _ = classificar_status(l.get("Temperatura"), l.get("Vibracao"), l.get("Corrente"),
                                       l.get("RPM"), l.get("FalhaCodigo", 0))
        if status == "Crítico":
            n += 1
        else:
            break
    return n


def alerta_devido(tag, minimo=None):
    """
    True quando a máquina está em estado crítico sustentado (padrão: 3 leituras
    seguidas ≈ 30 min). Retorna (deve_alertar, n_leituras, minutos_aprox).
    """
    minimo = minimo or LEITURAS_CRITICAS_SEGUIDAS
    n = criticos_consecutivos(tag)
    return n >= minimo, n, n * 10


def maquinas_em_alerta_sustentado(tags=None):
    """Lista de (tag, n_leituras) das máquinas que já atingiram o critério."""
    from providers.db_mongo import TelemetriaRepository
    tags = tags or TelemetriaRepository.obter_tags_disponiveis()
    saida = []
    for t in tags:
        devido, n, _ = alerta_devido(t)
        if devido:
            saida.append((t, n))
    return saida


# ---------------------------------------------------------------------------
# Disparo automático para o Gerente de Manutenção
# ---------------------------------------------------------------------------
def minutos_criticos_seguidos(tag, maximo=40):
    """
    Há quantos minutos a máquina está continuamente em estado crítico,
    medido pelos horários das leituras (mais confiável que contar leituras,
    porque o intervalo entre elas varia).

    Retorna (minutos, n_leituras, leitura_mais_recente, primeira_critica).
    """
    from features.limites import classificar_status
    from providers.db_mongo import TelemetriaRepository
    leituras = TelemetriaRepository.obter_historico(tag, limite=maximo)  # mais recente primeiro
    criticas = []
    for l in leituras:
        status, _ = classificar_status(l.get("Temperatura"), l.get("Vibracao"), l.get("Corrente"),
                                       l.get("RPM"), l.get("FalhaCodigo", 0))
        if status != "Crítico":
            break
        criticas.append(l)
    if not criticas:
        return 0, 0, (leituras[0] if leituras else None), None
    recente, primeira = criticas[0], criticas[-1]
    t1, t0 = recente.get("timestamp"), primeira.get("timestamp")
    minutos = 0
    if hasattr(t1, "timestamp") and hasattr(t0, "timestamp"):
        minutos = int(abs((t1 - t0).total_seconds()) // 60)
    if len(criticas) > 1 and minutos == 0:
        minutos = (len(criticas) - 1) * 10        # estimativa se faltar horário
    return minutos, len(criticas), recente, primeira


MINUTOS_MIN = 10
MINUTOS_MAX = 60
CHAVE_MINUTOS = "alerta_minutos_criticos"


def limite_minutos_automatico():
    """
    Minutos de estado crítico que disparam o e-mail automático.
    Ordem: valor calibrado na tela (banco) → secrets.toml → padrão 30.
    Sempre entre 10 e 60 minutos.
    """
    valor = None
    try:
        from providers.db_mongo import ConfiguracaoRepository
        valor = ConfiguracaoRepository.obter(CHAVE_MINUTOS)
    except Exception:
        valor = None
    if valor is None:
        valor = _cfg("ALERTA_MINUTOS_CRITICOS", MINUTOS_CRITICOS_AUTOMATICO)
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        valor = MINUTOS_CRITICOS_AUTOMATICO
    return max(MINUTOS_MIN, min(MINUTOS_MAX, valor))


def definir_limite_minutos(minutos, usuario=None):
    """Grava o tempo de calibração (10 a 60 min). Retorna o valor efetivo."""
    minutos = max(MINUTOS_MIN, min(MINUTOS_MAX, int(minutos)))
    try:
        from providers.db_mongo import ConfiguracaoRepository
        ConfiguracaoRepository.definir(CHAVE_MINUTOS, minutos, usuario)
    except Exception:
        pass
    return minutos


def verificar_e_alertar_criticos(tags=None, minutos=None, forcar=False):
    """
    Percorre as máquinas e, para cada uma em estado crítico há pelo menos
    `minutos` (padrão 30), envia AUTOMATICAMENTE o relatório de falha por
    e-mail e WhatsApp ao Gerente de Manutenção.

    O mesmo episódio nunca é notificado duas vezes: o controle é feito pela
    coleção `alertas_enviados`, usando o horário da primeira leitura crítica
    do episódio como chave.

    Retorna lista de dicts com o que foi verificado e enviado.
    """
    from providers.db_mongo import TelemetriaRepository, EquipamentoRepository, AlertaRepository
    limite = minutos or limite_minutos_automatico()
    tags = tags or TelemetriaRepository.obter_tags_disponiveis()
    resultados = []
    for tag in tags:
        try:
            mins, n, recente, primeira = minutos_criticos_seguidos(tag)
        except Exception:
            continue
        if not recente or mins < limite:
            continue
        chave = (primeira or {}).get("timestamp") or (recente or {}).get("timestamp")
        if not forcar:
            try:
                if not AlertaRepository.marcar_notificado(
                        tag, chave, {"tipo": "critico_sustentado", "minutos": mins, "leituras": n}):
                    continue        # este episódio já foi notificado
            except Exception:
                pass
        try:
            equipamento = EquipamentoRepository.buscar_por_tag(tag) or {}
        except Exception:
            equipamento = {}
        texto = relatorio_falha(tag, recente, status="Crítico", equipamento=equipamento)
        texto += (f"\n\n*Duração:* estado crítico há {mins} minutos seguidos "
                  f"({n} leituras consecutivas).\n"
                  "*Envio:* automático — limite de "
                  f"{limite} minutos em estado crítico atingido.")
        res = enviar_alerta(f"[FORZY CRÍTICO] {tag} — crítico há {mins} min", texto,
                            planta=equipamento.get("Planta"), apenas_gerentes=True,
                            origem="automatico_30min", tag=tag, usuario="Sistema")
        resultados.append({"TAG": tag, "minutos": mins, "leituras": n,
                           "email_ok": res["email_ok"], "email_msg": res["email_msg"],
                           "whatsapp_ok": res["whatsapp_ok"], "destinatarios": res["emails"]})
    return resultados


def panorama_criticos(tags=None):
    """Situação de cada máquina crítica agora, para exibir na tela (sem enviar nada)."""
    from providers.db_mongo import TelemetriaRepository
    limite = limite_minutos_automatico()
    tags = tags or TelemetriaRepository.obter_tags_disponiveis()
    linhas = []
    for tag in tags:
        try:
            mins, n, recente, _ = minutos_criticos_seguidos(tag)
        except Exception:
            continue
        if n:
            linhas.append({"TAG": tag, "minutos": mins, "leituras": n,
                           "atingiu_limite": mins >= limite,
                           "faltam": max(0, limite - mins)})
    return sorted(linhas, key=lambda d: -d["minutos"])


_ultima_verificacao = {"quando": 0.0, "resultado": []}


def verificacao_automatica_ligada():
    valor = _cfg("ALERTA_AUTOMATICO", "1")
    return str(valor).strip().lower() not in ("0", "false", "nao", "não", "off")


def verificar_periodicamente(intervalo_seg=300):
    """
    Chamado a cada carregamento do app. Roda a verificação automática no
    máximo uma vez a cada `intervalo_seg` (padrão 5 min) por processo, em
    segundo plano, para não atrasar a tela.
    """
    import threading
    import time as _time
    if not verificacao_automatica_ligada():
        return
    agora = _time.time()
    if agora - _ultima_verificacao["quando"] < intervalo_seg:
        return
    _ultima_verificacao["quando"] = agora

    def _rodar():
        try:
            _ultima_verificacao["resultado"] = verificar_e_alertar_criticos()
        except Exception:
            _ultima_verificacao["resultado"] = []

    threading.Thread(target=_rodar, daemon=True).start()
