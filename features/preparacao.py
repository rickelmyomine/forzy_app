"""
Preparação automática dos dados na primeira execução do app — em segundo plano.

Ao abrir o app (após o login), verifica no MongoDB e, se faltar algo, dispara
uma thread que:
  1. grava o cadastro das 20 máquinas (rápido — Consulta já funciona);
  2. confere/treina o modelo de previsão;
  3. gera a telemetria dos últimos 30 dias, DO DIA MAIS RECENTE PARA TRÁS,
     gravando dia a dia (o dashboard de hoje aparece em segundos):
       - últimos 3 dias: leitura a cada 10 min
       - dias 4 a 30: leitura a cada 30 min      (~35 mil documentos no total)

Enquanto roda, a barra lateral mostra o progresso e o app segue utilizável.
Nunca apaga leituras importadas do CSV nem manutenções registradas.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from providers.db_mongo import (
    EquipamentoRepository, TelemetriaRepository, _obter_db, _obter_client, MongoIndisponivelError,
)

DIAS = 30
DIAS_DETALHADOS = 3          # a cada 10 min
PASSO_DETALHADO = 10
PASSO_RESUMIDO = 30
ORIGEM = "sintetico_30d"

# estado compartilhado entre a thread e a UI (por processo do Streamlit)
_estado = {"rodando": False, "concluido": False, "pct": 0, "etapa": "", "feitos": [], "erro": None,
           "iniciado_em": None}


def _precisa_telemetria():
    db = _obter_db()
    if db is None:
        return False
    col = db[TelemetriaRepository.COLECAO_HISTORICO]
    ultimo = col.find_one({"origem": ORIGEM}, {"timestamp": 1}, sort=[("timestamp", -1)])
    if not ultimo:
        return True
    ts = ultimo["timestamp"]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ts > timedelta(days=1)


def _precisa_cadastro():
    try:
        tags = set(EquipamentoRepository.listar_tags())
    except MongoIndisponivelError:
        return False
    if not {f"MOT-{i:03d}" for i in range(1, 21)}.issubset(tags):
        return True
    for t in ("MOT-001", "MOT-002", "MOT-003"):
        if not (EquipamentoRepository.buscar_por_tag(t) or {}).get("foto"):
            return True
    return False


def _precisa_manutencoes():
    db = _obter_db()
    if db is None:
        return False
    return db["manutencoes"].count_documents({}) == 0


def _precisa_modelo():
    from features.previsao import carregar_modelo
    return carregar_modelo()[0] is None


def _gerar_telemetria_por_dia(progresso):
    from features.gerador_dados import gerar_leituras
    tags = [f"MOT-{i:03d}" for i in range(1, 21)]
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    agora -= timedelta(minutes=agora.minute % 10)
    TelemetriaRepository.apagar_sinteticos(ORIGEM)
    total = 0
    for offset in range(DIAS):
        dia = (agora - timedelta(days=offset)).replace(hour=0, minute=0)
        fim = agora if offset == 0 else dia.replace(hour=23, minute=50)
        passo = PASSO_DETALHADO if offset < DIAS_DETALHADOS else PASSO_RESUMIDO
        regs = gerar_leituras(tags, dia, fim, passo_minutos=passo, seed=42 + offset,
                              motores_em_degradacao=(13, 19, 2) if offset == 0 else ())
        for r in regs:
            r["origem"] = ORIGEM
        total += TelemetriaRepository.inserir_lote(regs)
        progresso(f"Telemetria: dia {offset + 1} de {DIAS} gravado ({total:,} leituras)".replace(",", "."),
                  int(100 * (offset + 1) / DIAS))
    TelemetriaRepository.garantir_indices()
    return total


def _trabalho(precisa_cad, precisa_mod, precisa_tel):
    def progresso(msg, pct=None):
        _estado["etapa"] = msg
        if pct is not None:
            _estado["pct"] = pct
    try:
        # Remove máquinas fora do escopo (ex.: MOT-021 de teste)
        try:
            from providers.db_mongo import remover_maquinas_fora_do_escopo
            fora = remover_maquinas_fora_do_escopo()
            if fora:
                _estado["feitos"].append("máquinas fora do escopo removidas: "
                                         + ", ".join(f"{k} {v}" for k, v in fora.items()))
        except Exception:
            pass
        if precisa_cad:
            progresso("Gravando o cadastro das 20 máquinas (fotos e folha de dados)...", 2)
            from features.cadastro_exemplo import popular_cadastro
            c, a = popular_cadastro(sobrescrever=False)
            _estado["feitos"].append(f"cadastro: {c} máquina(s) criada(s), {a} atualizada(s)")
        if precisa_mod:
            progresso("Treinando o modelo de previsão de falhas...", 4)
            try:
                from scripts.treinar_modelo import main as treinar
                treinar()
                from features import previsao
                previsao._cache["modelo"] = None
                _estado["feitos"].append("modelo de previsão treinado")
            except Exception as e:
                _estado["feitos"].append(f"modelo não treinado ({type(e).__name__})")
        if precisa_tel:
            n = _gerar_telemetria_por_dia(progresso)
            _estado["feitos"].append(f"{n:,} leituras de telemetria (30 dias) gravadas".replace(",", "."))
        progresso("Gravando manutenções de exemplo...", 99)
        try:
            from features.manutencao_exemplo import popular_manutencoes_exemplo
            m = popular_manutencoes_exemplo()
            if m:
                _estado["feitos"].append(f"{m} manutenções de exemplo")
        except Exception as e:
            _estado["feitos"].append(f"manutenções de exemplo não gravadas ({type(e).__name__})")
        _estado["pct"] = 100
    except Exception as e:
        _estado["erro"] = f"{type(e).__name__}: {e}"
    finally:
        _estado["rodando"] = False
        _estado["concluido"] = True


def garantir_dados_prontos():
    """Chamado pelo app após o login. Dispara a preparação uma vez por processo."""
    if _estado["rodando"] or _estado["concluido"]:
        return
    if _obter_client() is None:
        return
    try:
        precisa = (_precisa_cadastro(), _precisa_modelo(), _precisa_telemetria())
        precisa_man = _precisa_manutencoes()
    except Exception:
        return
    if not any(precisa) and not precisa_man:
        _estado["concluido"] = True
        return
    _estado.update({"rodando": True, "pct": 0, "etapa": "Iniciando...", "iniciado_em": time.time()})
    threading.Thread(target=_trabalho, args=precisa, daemon=True).start()


_aquecimento = {"feito": False}


def _aquecer():
    """Pré-calcula em segundo plano as consultas pesadas das telas principais.

    Assim, quando o usuário abre Dados Brutos, Consulta ou Análise de Riscos,
    o resultado já está no cache do Streamlit e a tela aparece na hora.
    """
    try:
        from datetime import time as _t
        import ui.view_dados as vd
        import ui.view_frota as vf
        tags = tuple(sorted(TelemetriaRepository.obter_tags_disponiveis()))
        if not tags:
            return
        _, fim_disp = vd._periodo_disponivel()
        if fim_disp is None:
            return
        import pandas as _pd
        dia = _pd.Timestamp(fim_disp, tz="UTC").tz_convert(vd.FUSO).date()
        ini = vd._para_utc(dia, _t(0, 0))
        fim = vd._para_utc(dia, _t(23, 59))
        # Ordem: primeiro o que o usuário vê logo (Dados Brutos e Consulta),
        # depois a Análise de Riscos, que é a consulta mais cara.
        etapas = [
            lambda: vd._carregar(ini, fim, tags),
            lambda: __import__("ui.view_consulta", fromlist=["x"])._cadastro_leve(),
            lambda: __import__("ui.view_consulta", fromlist=["x"])._dados_visao_geral(tags),
            lambda: __import__("ui.view_consulta", fromlist=["x"])._previsoes_todas(tags),
            lambda: vd._falhas_diarias(vd._para_utc(dia - timedelta(days=364), _t(0, 0)), fim, tags),
            lambda: vf._frota(30, None),
            lambda: vf._frota(30, "Todas as plantas"),
        ]
        for etapa in etapas:
            try:
                etapa()
            except Exception:
                pass
            time.sleep(0.4)   # deixa o servidor respirar entre as consultas
    except Exception:
        pass
    finally:
        _aquecimento["feito"] = True


def aquecer_caches():
    """Dispara o aquecimento uma única vez por processo."""
    if _aquecimento["feito"] or _aquecimento.get("rodando"):
        return
    _aquecimento["rodando"] = True
    threading.Thread(target=_aquecer, daemon=True).start()


def _barra_verde(pct, texto):
    st.markdown(
        f"""<div style="height:10px"></div>
<div style="font-size:0.85em;margin-bottom:4px">{texto}</div>
<div style="background:rgba(255,255,255,0.15);border-radius:6px;height:14px;width:100%;overflow:hidden">
  <div style="background:#1db954;height:14px;width:{max(0, min(100, pct))}%;border-radius:6px;transition:width .5s"></div>
</div>
<div style="font-size:0.8em;text-align:right;opacity:.85">{pct}%</div>""",
        unsafe_allow_html=True,
    )


def painel_progresso():
    """Barra de carregamento: só fica se atualizando enquanto há trabalho."""
    if _estado["rodando"]:
        _painel_ativo()
    elif _estado.get("erro"):
        _barra_verde(_estado["pct"], "Carregamento interrompido")
        st.warning(f"Preparação automática falhou: {_estado['erro']}")
    else:
        if _estado["feitos"] and not _estado.get("cache_limpo"):
            st.cache_data.clear()
            _estado["cache_limpo"] = True
        aquecer_caches()
        _barra_verde(100, "✅ Atualização concluída")


@st.fragment(run_every=2)
def _painel_ativo():
    """Atualiza sozinho a cada 2 s enquanto a preparação está rodando."""
    if _estado["rodando"]:
        _barra_verde(_estado["pct"], f"⬇️ Carregando dados do banco… {_estado['etapa']}")
        st.caption("Você já pode navegar — os gráficos vão se completando.")
    else:
        _barra_verde(100, "✅ Atualização concluída")
        st.rerun(scope="app")
