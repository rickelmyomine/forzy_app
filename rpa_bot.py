import os
import urllib.parse
import webbrowser

def enviar_alerta_whatsapp(mensagem_texto: str, numero_destino: str = "") -> bool:
    """
    Abre o WhatsApp Web com a mensagem pré-preenchida (envio manual — ainda
    precisa clicar em "Enviar" dentro do WhatsApp). Útil para acionamento
    manual pelo operador enquanto olha o dashboard.
    """
    mensagem_encodada = urllib.parse.quote(mensagem_texto)
    
    if numero_destino:
        url = f"https://web.whatsapp.com/send?phone={numero_destino}&text={mensagem_encodada}"
    else:
        url = f"https://web.whatsapp.com/send?text={mensagem_encodada}"

    webbrowser.open(url)
    return True


def enviar_email_alerta(assunto: str, mensagem_texto: str, destinatario: str) -> tuple[bool, str]:
    """
    Envia um e-mail de alerta automático via Gmail SMTP, sem nenhum clique
    manual e sem custo. Usado pelo script de monitoramento em segundo
    plano (scripts/monitor_alertas.py).

    Requer as variáveis de ambiente (ou st.secrets, se chamado de dentro
    do Streamlit):
        GMAIL_USER            e-mail que envia (ex: seuemail@gmail.com)
        GMAIL_APP_PASSWORD    senha de app do Gmail (NÃO é a senha normal
                               da conta — veja como gerar em
                               https://myaccount.google.com/apppasswords,
                               precisa da verificação em 2 etapas ativada)

    Retorna (sucesso: bool, mensagem_ou_erro: str).
    """
    import smtplib
    from email.mime.text import MIMEText

    remetente = os.environ.get("GMAIL_USER")
    senha_app = os.environ.get("GMAIL_APP_PASSWORD")

    if not (remetente and senha_app):
        try:
            import streamlit as st
            remetente = remetente or st.secrets.get("GMAIL_USER")
            senha_app = senha_app or st.secrets.get("GMAIL_APP_PASSWORD")
        except Exception:
            pass

    if not (remetente and senha_app):
        return False, (
            "Credenciais do Gmail não configuradas. Defina GMAIL_USER e "
            "GMAIL_APP_PASSWORD (senha de app, não a senha normal)."
        )

    try:
        msg = MIMEText(mensagem_texto)
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = destinatario

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha_app)
            servidor.sendmail(remetente, [destinatario], msg.as_string())

        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, str(e)
