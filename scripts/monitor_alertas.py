"""
Monitor de alertas em segundo plano.

Roda continuamente (fora do Streamlit, em outro terminal/processo)
verificando a leitura mais recente de cada ativo no MongoDB. Sempre que
encontra uma leitura em estado "Alerta" ou "Crítico" que ainda não foi
notificada, envia um E-MAIL automático via Gmail — sem nenhum clique
manual e sem custo — para o endereço configurado.

Como rodar:
    1. Ative a verificação em 2 etapas na sua conta Google e gere uma
       "senha de app" em: https://myaccount.google.com/apppasswords

    2. Configure as variáveis de ambiente:
         MONGODB_URI, MONGODB_DB_NAME
         GMAIL_USER            (e-mail que envia, ex: seuemail@gmail.com)
         GMAIL_APP_PASSWORD    (a senha de app gerada no passo 1)
         EMAIL_ALERT_TO        (e-mail que vai RECEBER o alerta)

    3. Rode: python scripts/monitor_alertas.py
       Deixe rodando (em outro terminal, como tarefa agendada, ou como
       serviço) — ele verifica em loop, independente do app Streamlit
       estar aberto ou não.

    Intervalo de verificação configurável via MONITOR_INTERVALO_SEGUNDOS
    (padrão: 60 segundos).

    Regra: o e-mail só é enviado quando a máquina está em estado CRÍTICO
    SUSTENTADO — 3 leituras seguidas (~30 min), definido em
    features/alertas.py (LEITURAS_CRITICAS_SEGUIDAS). Picos isolados não
    geram alerta.
"""
import os
import sys
import time
from datetime import datetime

# Garante que o script encontra o pacote "providers" mesmo executado de
# fora da raiz do projeto.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.db_mongo import (
    TelemetriaRepository,
    TipoFalhaRepository,
    AlertaRepository,
    MongoIndisponivelError,
)
from rpa_bot import enviar_email_alerta

INTERVALO = int(os.environ.get("MONITOR_INTERVALO_SEGUNDOS", "60"))
def _email_alerta():
    """Destinatário dos alertas: variável de ambiente, secrets.toml ou os
    funcionários cadastrados que marcaram 'receber alertas'."""
    alvo = os.environ.get("EMAIL_ALERT_TO")
    if alvo:
        return alvo
    try:
        import streamlit as st
        if "EMAIL_ALERT_TO" in st.secrets:
            return st.secrets["EMAIL_ALERT_TO"]
    except Exception:
        pass
    try:
        from features.alertas import destinatarios
        emails, _ = destinatarios()
        if emails:
            return ",".join(emails)
    except Exception:
        pass
    return None


EMAIL_ALERTA = _email_alerta()


def verificar_uma_vez():
    # 1) Regra por TEMPO: crítico sustentado por 30 min avisa o Gerente de
    #    Manutenção automaticamente (usa os funcionários cadastrados no app).
    try:
        from features.alertas import verificar_e_alertar_criticos, limite_minutos_automatico
        for r in verificar_e_alertar_criticos():
            print(f"[auto {limite_minutos_automatico()}min] {r['TAG']}: crítico há {r['minutos']} min "
                  f"-> {'enviado' if r['email_ok'] else 'falhou'} para {', '.join(r['destinatarios']) or '-'}")
    except Exception as e:
        print(f"[auto] verificação automática falhou: {e}")

    # 2) Regra antiga por leitura, mantida para o destinatário fixo.
    if not EMAIL_ALERTA:
        print("ERRO: defina EMAIL_ALERT_TO (e-mail que vai receber os alertas).")
        return

    tags = TelemetriaRepository.obter_tags_disponiveis()
    for tag in tags:
        leitura = TelemetriaRepository.obter_ultima_leitura(tag)
        if not leitura:
            continue

        # Só alerta em estado CRÍTICO SUSTENTADO (3 leituras seguidas ≈ 30 min),
        # para não disparar por pico isolado.
        from features.alertas import alerta_devido, LEITURAS_CRITICAS_SEGUIDAS
        devido, n_seguidas, minutos = alerta_devido(tag)
        if not devido:
            continue
        status = leitura.get("Status") or "Crítico"

        timestamp = leitura.get("timestamp")
        if timestamp is None:
            continue

        if AlertaRepository.ja_notificado(tag, timestamp):
            continue

        # Tenta "reservar" esse alerta antes de enviar. Se outro processo
        # já reservou, marcar_notificado retorna False e a gente pula.
        if not AlertaRepository.marcar_notificado(tag, timestamp, detalhes=leitura):
            continue

        nome_falha = ""
        codigo_falha = leitura.get("FalhaCodigo")
        if codigo_falha and int(codigo_falha) != 0:
            nome_falha = f" ({TipoFalhaRepository.obter_nome(codigo_falha)})"

        assunto = f"[FORZY ALERTA] Motor {tag} — {status} sustentado{nome_falha}"
        from features.alertas import relatorio_falha
        mensagem = relatorio_falha(tag, leitura, status=status) + (
            f"\n\n*Duração:* {n_seguidas} leituras críticas seguidas (~{minutos} min)."
            f"\nVerifique o dashboard para o histórico completo."
        )

        sucesso, info = enviar_email_alerta(assunto, mensagem, EMAIL_ALERTA)
        agora = datetime.now().strftime("%H:%M:%S")
        if sucesso:
            print(f"[{agora}] ✅ E-mail enviado para {tag} ({status}{nome_falha}).")
        else:
            print(f"[{agora}] ⚠️ Falha ao enviar e-mail para {tag}: {info}")


def main():
    print(f"Monitor de alertas iniciado. Verificando a cada {INTERVALO}s. Ctrl+C para parar.")
    while True:
        try:
            verificar_uma_vez()
        except MongoIndisponivelError as e:
            print(f"⚠️ {e}")
        except Exception as e:
            print(f"⚠️ Erro inesperado no ciclo de verificação: {e}")
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()