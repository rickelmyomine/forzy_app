"""
Gerador de telemetria sintética dos últimos N dias para todas as máquinas.

Reproduz as características estatísticas do dataset real Dados_Leituras_.csv
(médias/desvios por classe de falha, episódios de falha com rampa progressiva
de 30 a 80 leituras, ~10 % do tempo em falha por motor) e acrescenta um ciclo
diário de temperatura. Cada motor tem um "perfil" (algumas máquinas mais
propensas a superaquecimento, outras a desbalanceamento), coerente com a
distribuição de falhas observada no CSV.

Uso principal: scripts/gerar_dataset_30dias.py -> coleção telemetria_historico
(documentos marcados com origem="sintetico_30d", para poderem ser regenerados
sem tocar nas leituras importadas do CSV).
"""
from datetime import datetime, timedelta, timezone
import math
import random

from features.limites import classificar_status, ICONES_STATUS

# Estatísticas por classe (do CSV): média, desvio
_ESTATISTICAS = {
    0: {"RPM": (1776, 40), "Vibracao": (2.7, 0.6), "Temperatura": (68.5, 4.5), "Corrente": (12.3, 1.0)},
    1: {"RPM": (1762, 70), "Vibracao": (7.3, 1.4), "Temperatura": (69.1, 5.0), "Corrente": (12.6, 1.2)},
    2: {"RPM": (1768, 50), "Vibracao": (3.0, 0.9), "Temperatura": (84.3, 6.5), "Corrente": (14.6, 1.2)},
    3: {"RPM": (1570, 65), "Vibracao": (6.1, 1.3), "Temperatura": (68.7, 6.0), "Corrente": (14.0, 1.2)},
}

# Propensão de cada motor a cada tipo de falha (1, 2, 3) e taxa de falha alvo
_PERFIS = {
    1: ((0.2, 0.5, 0.3), 0.15), 2: ((0.6, 0.2, 0.2), 0.13), 3: ((0.2, 0.3, 0.5), 0.12),
    4: ((0.3, 0.4, 0.3), 0.09), 5: ((0.4, 0.3, 0.3), 0.09), 6: ((0.1, 0.7, 0.2), 0.14),
    7: ((0.2, 0.6, 0.2), 0.13), 8: ((0.5, 0.3, 0.2), 0.13), 9: ((0.3, 0.4, 0.3), 0.09),
    10: ((0.2, 0.6, 0.2), 0.09), 11: ((0.3, 0.3, 0.4), 0.10), 12: ((0.7, 0.2, 0.1), 0.15),
    13: ((0.2, 0.6, 0.2), 0.20), 14: ((0.4, 0.3, 0.3), 0.11), 15: ((0.3, 0.3, 0.4), 0.12),
    16: ((0.3, 0.4, 0.3), 0.08), 17: ((0.3, 0.4, 0.3), 0.08), 18: ((0.2, 0.7, 0.1), 0.11),
    19: ((0.1, 0.8, 0.1), 0.17), 20: ((0.2, 0.7, 0.1), 0.18),
}


def _gauss(rng, media, desvio):
    return rng.gauss(media, desvio)


def gerar_leituras(tags, inicio, fim, passo_minutos=10, seed=42, motores_em_degradacao=(13, 19, 2)):
    """
    Gera leituras para cada TAG entre `inicio` e `fim` (datetimes, UTC).
    `motores_em_degradacao`: motor_ids que terminam a série com uma rampa
    de deterioro ainda em curso (para o modelo de previsão ter o que apontar).
    Retorna lista de dicts no formato da coleção telemetria_historico.
    """
    rng = random.Random(seed)
    total_passos = int((fim - inicio).total_seconds() // (passo_minutos * 60)) + 1
    registros = []

    for tag in tags:
        try:
            motor_id = int(tag.split("-")[-1])
        except ValueError:
            motor_id = 1
        pesos, taxa = _PERFIS.get(motor_id, ((0.3, 0.4, 0.3), 0.10))
        offset_temp = rng.uniform(-3, 3)      # cada motor roda um pouco mais quente/frio
        offset_rpm = rng.uniform(-25, 25)

        # Agenda de episódios de falha: (indice_inicio, duracao, tipo)
        episodios = []
        # Número de episódios proporcional à taxa de falha do motor (duração média 42 leituras);
        # a fração é sorteada, então em períodos curtos (1 dia) nem todo motor tem episódio.
        esperado = total_passos * taxa / 42
        n_episodios = int(esperado) + (1 if rng.random() < (esperado - int(esperado)) else 0)
        for _ in range(n_episodios):
            dur = int(rng.gauss(42, 15))
            dur = max(8, min(dur, 85))
            ini = rng.randint(-dur // 2, total_passos - dur // 2)   # pode começar antes/terminar depois
            tipo = rng.choices([1, 2, 3], weights=pesos)[0]
            episodios.append((ini, dur, tipo))

        # Degradação em curso no final da série
        degradando = motor_id in motores_em_degradacao
        if degradando:
            tipo_final = rng.choices([1, 2, 3], weights=pesos)[0]
            dur_final = 30
            episodios.append((total_passos - dur_final, dur_final * 2, tipo_final))

        # Mapa passo -> (tipo, progresso 0..1)
        estado = {}
        for ini, dur, tipo in episodios:
            for k in range(dur):
                idx = ini + k
                if idx < 0:
                    continue
                if idx >= total_passos:
                    break
                progresso = min(1.0, (k + 1) / max(1, int(dur * 0.6)))  # rampa nos primeiros 60 %
                if idx not in estado or estado[idx][1] < progresso:
                    estado[idx] = (tipo, progresso)

        for i in range(total_passos):
            ts = inicio + timedelta(minutes=i * passo_minutos)
            hora = ts.hour + ts.minute / 60
            ciclo = 2.5 * math.sin((hora - 9) / 24 * 2 * math.pi)  # +2,5 °C à tarde

            normal = _ESTATISTICAS[0]
            valores = {k: _gauss(rng, *normal[k]) for k in normal}
            valores["Temperatura"] += ciclo + offset_temp
            valores["RPM"] += offset_rpm
            codigo = 0

            if i in estado:
                tipo, p = estado[i]
                alvo = _ESTATISTICAS[tipo]
                # a leitura caminha da distribuição normal para a da falha
                for k in valores:
                    m_alvo, s_alvo = alvo[k]
                    valores[k] = valores[k] * (1 - p) + _gauss(rng, m_alvo, s_alvo) * p
                # rotula como falha quando a rampa passou de 35 % (antes disso é "pré-sintoma")
                codigo = tipo if p >= 0.35 else 0

            temp = round(valores["Temperatura"], 2)
            vib = round(max(0.3, valores["Vibracao"]), 3)
            cor = round(max(6.0, valores["Corrente"]), 2)
            rpm = round(max(1200.0, valores["RPM"]), 2)
            status, indicador = classificar_status(temp, vib, cor, rpm, codigo)
            registros.append({
                "TAG": tag, "Temperatura": temp, "Vibracao": vib, "Corrente": cor, "RPM": rpm,
                "FalhaCodigo": codigo, "Status": status, "Indicador": indicador,
                "timestamp": ts, "origem": "sintetico_30d",
            })
    return registros


def periodo_ultimos_dias(dias=30, ate=None):
    fim = (ate or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    fim = fim - timedelta(minutes=fim.minute % 10)
    inicio = (fim - timedelta(days=dias)).replace(hour=0, minute=0)
    return inicio, fim
