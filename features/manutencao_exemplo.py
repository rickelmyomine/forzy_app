"""
Ordens de serviço de exemplo (2 por máquina) para visualização, gravadas na
primeira execução quando a coleção `manutencoes` está vazia. Ficam marcadas
com exemplo=True; podem ser apagadas pelo gerente na tela de Manutenções.
"""
import random
from datetime import datetime, timedelta, timezone

from providers.db_mongo import ManutencaoRepository, TelemetriaRepository, _obter_db

_PREVENTIVAS = [
    ("Inspeção mensal programada: verificação de ruído, fixação e limpeza das aletas de ventilação.",
     "Limpeza das aletas e da tampa defletora, reaperto dos parafusos da base, verificação de ruído no mancal.",
     "", 1.0),
    ("Revisão trimestral: lubrificação dos mancais e medição de corrente por fase.",
     "Lubrificação dos rolamentos 6205-ZZ/6204-ZZ com graxa Polyrex EM, medição de corrente (fases equilibradas), teste de isolação OK.",
     "Graxa Mobil Polyrex EM (30 g)", 1.5),
    ("Checklist preventivo: alinhamento e balanceamento do acoplamento.",
     "Verificado alinhamento com relógio comparador (dentro de 0,05 mm); balanceamento OK; reaperto do acoplamento.",
     "", 2.0),
]
_CORRETIVAS = {
    1: ("Vibração elevada e ruído no mancal dianteiro; alarme de desbalanceamento no sistema.",
        "Substituído rolamento dianteiro, realinhamento do acoplamento e balanceamento da polia. Vibração voltou a 2,5 mm/s.",
        "Rolamento 6205-ZZ, graxa Polyrex EM", 4.0),
    2: ("Temperatura acima de 88 °C por mais de 1 h; corrente 15 % acima da nominal.",
        "Limpeza das aletas e do ventilador (obstruídos por pó), verificação da carga e da tensão por fase. Temperatura normalizada em 70 °C.",
        "", 3.0),
    3: ("Queda de rotação com vibração e corrente altas; motor travando na partida.",
        "Motor isolado; acoplamento com folga substituído, rolamento traseiro trocado, eixo verificado. Teste em vazio e com carga OK.",
        "Acoplamento elástico, rolamento 6204-ZZ", 6.0),
}


def _falha_predominante(tag):
    dist = TelemetriaRepository.obter_distribuicao_falhas(tag) or {}
    dist = {int(k): v for k, v in dist.items() if int(k) != 0}
    return max(dist, key=dist.get) if dist else 2


def popular_manutencoes_exemplo(forcar=False):
    db = _obter_db()
    if db is None:
        return 0
    col = db[ManutencaoRepository.COLECAO]
    if col.count_documents({}) and not forcar:
        return 0
    rng = random.Random(7)
    agora = datetime.now(timezone.utc)
    tecnicos = ["Técnico 1", "Técnico 2"]
    criados = 0
    for i in range(1, 21):
        tag = f"MOT-{i:03d}"
        tipo_falha = _falha_predominante(tag)
        # 1) preventiva concluída há 10–28 dias
        d_prev, s_prev, p_prev, h_prev = rng.choice(_PREVENTIVAS)
        data1 = agora - timedelta(days=rng.randint(10, 28), hours=rng.randint(0, 9))
        # 2) corretiva/inspeção mais recente (2–9 dias), ligada ao tipo de falha predominante
        d_cor, s_cor, p_cor, h_cor = _CORRETIVAS[tipo_falha]
        data2 = agora - timedelta(days=rng.randint(2, 9), hours=rng.randint(0, 9))
        status2 = rng.choice(["Concluída", "Concluída", "Em andamento"])
        cat2 = "anomalia_mecanica" if tipo_falha in (1, 3) else "anomalia_eletrica"
        for data, tipo, desc, serv, pecas, horas, status, cat, cat_nome in (
            (data1, "Preventiva", d_prev, s_prev, p_prev, h_prev, "Concluída", "manutencao_preventiva", "Manutenção preventiva"),
            (data2, "Corretiva", d_cor, s_cor, p_cor, h_cor, status2, cat2, "Anomalia mecânica" if cat2 == "anomalia_mecanica" else "Anomalia elétrica"),
        ):
            tele = None
            leit = TelemetriaRepository.obter_intervalo(data - timedelta(hours=1), data, tags=[tag])
            if leit:
                l = leit[-1]
                tele = {k: l.get(k) for k in ("Temperatura", "Vibracao", "Corrente", "RPM", "Status", "FalhaCodigo", "timestamp")}
            ManutencaoRepository.criar({
                "TAG": tag, "tipo": tipo, "status": status, "data": data.replace(tzinfo=None),
                "titulo": desc[:60], "descricao_problema": desc, "servico_executado": serv,
                "pecas_trocadas": pecas, "tempo_parada_horas": horas,
                "categoria": cat, "categoria_nome": cat_nome, "telemetria_no_momento": tele,
                "tecnico": rng.choice(tecnicos), "tecnico_perfil": "tecnico",
                "criado_em": agora, "fotos": [], "exemplo": True,
            })
            criados += 1
    return criados
