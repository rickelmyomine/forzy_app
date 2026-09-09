"""
Coleta de Dados — entrada de leituras de máquinas e equipamentos para
análise e formação de dataset.

Três caminhos:
  📄 Arquivo (CSV/Excel)  — funcional: importa leituras para o MongoDB.
  ✍️ Manual               — funcional: digita uma leitura pontual.
  📶 Bluetooth / IoT      — previsto: leitura direta de sensores/coletores
                            (ainda não implementado, botão de demonstração).
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from features.estilos import abas

from auth.auth import nome_usuario_atual
from features.limites import VARIAVEIS, classificar_status
from providers.db_mongo import (
    TelemetriaRepository, EquipamentoRepository, DatasetRepository, _exigir_db,
    MongoIndisponivelError,
)

ORIGEM_ARQUIVO = "importado_arquivo"
ORIGEM_MANUAL = "coleta_manual"
ORIGEM_BLUETOOTH = "coleta_bluetooth"

COLUNAS_ESPERADAS = {
    "TAG": ["tag", "maquina", "máquina", "motor", "equipamento", "motor_id"],
    "timestamp": ["timestamp", "data", "datahora", "data_hora", "horario", "horário"],
    "Temperatura": ["temperatura", "temperatura_c", "temp", "temp_c"],
    "Vibracao": ["vibracao", "vibração", "vibracao_mm_s", "vibration"],
    "Corrente": ["corrente", "corrente_a", "current"],
    "RPM": ["rpm", "rotacao", "rotação", "rotacao_rpm", "velocidade"],
    "FalhaCodigo": ["falha", "falhacodigo", "falha_codigo", "fault"],
}


def _mapear_colunas(df):
    """Reconhece as colunas do arquivo pelos nomes mais comuns."""
    mapa = {}
    for destino, apelidos in COLUNAS_ESPERADAS.items():
        for col in df.columns:
            if str(col).strip().lower() in apelidos:
                mapa[col] = destino
                break
    return mapa


def _aba_arquivo():
    st.markdown("**Importar leituras de um arquivo CSV ou Excel**")
    st.caption("Serve para trazer coletas feitas em campo (coletor de vibração, multímetro, planilha do "
               "técnico) ou exportações de outro sistema. As leituras entram no mesmo histórico das máquinas "
               "e passam a alimentar os gráficos, o modelo de previsão e o Chat IA.")
    with st.expander("📋 Formato aceito"):
        st.markdown(
            "Uma linha por leitura. Colunas reconhecidas (nome flexível):\n\n"
            "| Coluna | Aceita também | Obrigatória |\n|---|---|---|\n"
            "| TAG | maquina, motor, motor_id | sim |\n"
            "| timestamp | data, data_hora, horario | sim |\n"
            "| Temperatura | temperatura_c, temp | sim |\n"
            "| Vibracao | vibracao_mm_s, vibração | sim |\n"
            "| Corrente | corrente_a | sim |\n"
            "| RPM | rotacao, rotacao_rpm | sim |\n"
            "| FalhaCodigo | falha (0 a 3) | não |\n"
        )
        exemplo = pd.DataFrame({
            "TAG": ["MOT-001", "MOT-001"], "timestamp": ["2026-09-08 08:00", "2026-09-08 08:10"],
            "Temperatura": [68.4, 69.1], "Vibracao": [2.7, 2.9], "Corrente": [12.2, 12.4],
            "RPM": [1770, 1768], "FalhaCodigo": [0, 0]})
        st.dataframe(exemplo, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Baixar modelo de planilha",
                           exemplo.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name="modelo_coleta_forzy.csv", mime="text/csv")

    arquivo = st.file_uploader("Arquivo de leituras", type=["csv", "xlsx", "xls"], key="col_arquivo")
    if arquivo is None:
        return
    try:
        if arquivo.name.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(arquivo)
        else:
            conteudo = arquivo.getvalue()
            try:
                df = pd.read_csv(pd.io.common.BytesIO(conteudo), sep=None, engine="python", decimal=",", encoding="utf-8-sig")
            except Exception:
                df = pd.read_csv(pd.io.common.BytesIO(conteudo), sep=None, engine="python", encoding="latin-1")
    except Exception as e:
        st.error(f"Não consegui ler o arquivo: {e}")
        return

    st.markdown(f"**Prévia** — {len(df)} linha(s), {len(df.columns)} coluna(s)")
    st.dataframe(df.head(10), use_container_width=True)

    mapa = _mapear_colunas(df)
    df = df.rename(columns=mapa)
    faltando = [c for c in ("TAG", "timestamp", "Temperatura", "Vibracao", "Corrente", "RPM") if c not in df.columns]
    if faltando:
        st.error(f"Colunas não encontradas: {', '.join(faltando)}. Renomeie no arquivo ou use o modelo acima.")
        return
    st.success(f"Colunas reconhecidas: {', '.join(mapa.values())}")

    if st.button("💾 Importar para o histórico", type="primary"):
        try:
            registros = []
            for _, l in df.iterrows():
                tag = str(l["TAG"]).strip().upper()
                if tag.isdigit():
                    tag = f"MOT-{int(tag):03d}"
                ts = pd.to_datetime(l["timestamp"], errors="coerce", dayfirst=True)
                if pd.isna(ts):
                    continue
                cod = int(l["FalhaCodigo"]) if "FalhaCodigo" in df.columns and not pd.isna(l.get("FalhaCodigo")) else 0
                temp, vib = float(l["Temperatura"]), float(l["Vibracao"])
                cor, rpm = float(l["Corrente"]), float(l["RPM"])
                status, indicador = classificar_status(temp, vib, cor, rpm, cod)
                registros.append({"TAG": tag, "Temperatura": temp, "Vibracao": vib, "Corrente": cor, "RPM": rpm,
                                  "FalhaCodigo": cod, "Status": status, "Indicador": indicador,
                                  "timestamp": ts.to_pydatetime(), "origem": ORIGEM_ARQUIVO,
                                  "importado_por": nome_usuario_atual(), "arquivo": arquivo.name})
            if not registros:
                st.error("Nenhuma linha válida (verifique a coluna de data/hora).")
                return
            TelemetriaRepository.inserir_lote(registros)
            TelemetriaRepository.garantir_indices()
            st.success(f"✅ {len(registros)} leitura(s) importadas para o histórico "
                       f"({df['TAG'].nunique()} máquina(s)). Já aparecem em Dados Brutos.")
            st.cache_data.clear()
        except MongoIndisponivelError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Falha na importação: {e}")


def _aba_manual():
    st.markdown("**Registrar uma leitura manual**")
    st.caption("Para medições pontuais feitas em campo com instrumento portátil (termômetro infravermelho, "
               "coletor de vibração, alicate amperímetro, tacômetro).")
    try:
        tags = sorted(set(EquipamentoRepository.listar_tags()) | set(TelemetriaRepository.obter_tags_disponiveis()))
    except MongoIndisponivelError:
        tags = TelemetriaRepository.obter_tags_disponiveis()
    if not tags:
        st.info("Cadastre uma máquina primeiro.")
        return
    with st.form("form_coleta_manual"):
        c1, c2, c3 = st.columns(3)
        tag = c1.selectbox("Máquina", tags)
        data = c2.date_input("Data", value=datetime.now().date())
        hora = c3.time_input("Hora", value=datetime.now().time().replace(second=0, microsecond=0))
        c4, c5, c6, c7 = st.columns(4)
        temp = c4.number_input("Temperatura (°C)", min_value=0.0, max_value=200.0, value=68.0, step=0.1)
        vib = c5.number_input("Vibração (mm/s)", min_value=0.0, max_value=30.0, value=2.7, step=0.1)
        cor = c6.number_input("Corrente (A)", min_value=0.0, max_value=100.0, value=12.3, step=0.1)
        rpm = c7.number_input("Rotação (RPM)", min_value=0.0, max_value=5000.0, value=1770.0, step=10.0)
        obs = st.text_input("Observação (instrumento usado, condição da máquina...)")
        enviar = st.form_submit_button("💾 Registrar leitura", type="primary")
    if enviar:
        status, indicador = classificar_status(temp, vib, cor, rpm, 0)
        try:
            TelemetriaRepository.inserir_lote([{
                "TAG": tag, "Temperatura": temp, "Vibracao": vib, "Corrente": cor, "RPM": rpm,
                "FalhaCodigo": 0, "Status": status, "Indicador": indicador,
                "timestamp": datetime.combine(data, hora), "origem": ORIGEM_MANUAL,
                "observacao": obs, "importado_por": nome_usuario_atual(),
            }])
            st.success(f"✅ Leitura de {tag} registrada — estado {indicador} {status}.")
            st.cache_data.clear()
        except MongoIndisponivelError as e:
            st.error(str(e))


def _aba_bluetooth():
    st.markdown("**Coleta por Bluetooth / sensor IoT**")
    st.info("🚧 **Recurso previsto — ainda não implementado.** Esta tela mostra como a coleta direta vai "
            "funcionar quando os coletores forem integrados.")
    st.caption("A ideia: o técnico aproxima o celular ou o notebook do coletor Bluetooth (ou o gateway "
               "IoT publica via MQTT), o app lê temperatura, vibração, corrente e rotação e grava direto no "
               "histórico da máquina — sem digitar nada.")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Dispositivo", ["(nenhum dispositivo pareado)"], disabled=True)
        st.selectbox("Máquina de destino", ["MOT-001"], disabled=True)
        st.button("📶 Procurar dispositivos Bluetooth", disabled=True, use_container_width=True)
        st.button("⏺️ Iniciar coleta contínua", disabled=True, use_container_width=True)
    with c2:
        st.markdown(
            "**O que será necessário para ativar:**\n\n"
            "1. Coletor com Bluetooth LE (ex.: sensor de vibração/temperatura industrial) ou gateway IoT.\n"
            "2. Biblioteca de comunicação no servidor (`bleak` para BLE, `paho-mqtt` para MQTT).\n"
            "3. Mapeamento do protocolo do fabricante (UUID das características BLE ou tópico MQTT).\n"
            "4. Cadastro do dispositivo vinculado à TAG da máquina.\n\n"
            "As leituras entrarão na mesma coleção `telemetria_historico`, com "
            "`origem=\"coleta_bluetooth\"`, e passarão a alimentar os gráficos, o modelo de previsão e "
            "os alertas automaticamente."
        )


def _aba_dataset():
    st.markdown("**Dataset acumulado**")
    st.caption("Tudo o que está no histórico, por origem. Use o download para treinar modelos fora do app "
               "ou para entregar o dataset.")
    db = None
    try:
        db = _exigir_db()
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    col = db[TelemetriaRepository.COLECAO_HISTORICO]
    origens = list(col.aggregate([{"$group": {"_id": "$origem", "n": {"$sum": 1},
                                              "inicio": {"$min": "$timestamp"}, "fim": {"$max": "$timestamp"}}}]))
    nomes = {ORIGEM_ARQUIVO: "Importado de arquivo", ORIGEM_MANUAL: "Coleta manual",
             ORIGEM_BLUETOOTH: "Coleta Bluetooth", "sintetico_30d": "Telemetria dos últimos 30 dias",
             None: "Importado do CSV histórico"}
    linhas = [{"Origem": nomes.get(o["_id"], o["_id"] or "-"), "Leituras": o["n"],
               "De": o["inicio"].strftime("%d/%m/%Y") if hasattr(o.get("inicio"), "strftime") else "-",
               "Até": o["fim"].strftime("%d/%m/%Y") if hasattr(o.get("fim"), "strftime") else "-"} for o in origens]
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
    total = sum(o["n"] for o in origens)
    st.metric("Total de leituras no dataset", f"{total:,}".replace(",", "."))

    c1, c2 = st.columns([1, 2])
    dias = c1.selectbox("Baixar as leituras dos últimos", [1, 7, 30], index=1, format_func=lambda d: f"{d} dia(s)")
    if c2.button("⬇️ Preparar arquivo CSV do dataset"):
        from datetime import timedelta
        fim = datetime.now(timezone.utc)
        leituras = TelemetriaRepository.obter_intervalo(fim - timedelta(days=dias), fim)
        if not leituras:
            st.info("Sem leituras no período.")
        else:
            df = pd.DataFrame(leituras)
            st.download_button(f"⬇️ Baixar {len(df)} leituras (CSV)",
                               df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                               file_name=f"dataset_forzy_{dias}d.csv", mime="text/csv")


def _gerar_ultimos_5_dias():
    """Cria (ou atualiza) o dataset dos últimos 5 dias de toda a planta."""
    from datetime import timedelta
    from features.exportar import preparar_csv, nome_dataset
    from providers.db_mongo import DatasetRepository
    from features.graficos import df_de_leituras
    fim = datetime.now(timezone.utc)
    ini = fim - timedelta(days=5)
    leituras = TelemetriaRepository.obter_intervalo(ini, fim)
    if not leituras:
        return None, 0
    df = df_de_leituras(leituras)
    nome = nome_dataset("ultimos5dias", fim)
    csv_texto = preparar_csv(df)
    try:
        from auth.auth import nome_usuario_atual
        usuario = nome_usuario_atual()
    except Exception:
        usuario = "-"
    tags = sorted(df["TAG"].unique()) if "TAG" in df.columns else []
    DatasetRepository.registrar(nome, csv_texto, {
        "origem_tela": "Biblioteca — últimos 5 dias",
        "maquinas": list(tags), "qtd_maquinas": len(tags),
        "gerado_por": usuario, "periodo_dias": 5,
        "periodo_inicio": ini, "periodo_fim": fim,
    })
    return nome, len(df)


def _aba_biblioteca():
    st.markdown("**Biblioteca de datasets gerados**")
    st.caption("Todos os arquivos CSV já gerados nas telas de Dados Brutos, Consulta de Equipamentos "
               "e Comparação ficam guardados aqui. Filtre por data no calendário ou pesquise pelo "
               "nome, pela máquina, pela tela de origem ou por quem gerou.")

    # --- Dataset padrão dos últimos 5 dias ---
    with st.container(border=True):
        c1, c2 = st.columns([2.4, 1])
        c1.markdown("**📅 Dataset dos últimos 5 dias — toda a planta**")
        c1.caption("Arquivo pronto com as leituras das 20 máquinas nos últimos 5 dias. "
                   "Clique para gerar agora ou atualizar com os dados mais recentes.")
        c2.write("")
        if c2.button("🔄 Gerar / atualizar", key="bib_5dias", type="primary", use_container_width=True):
            with st.spinner("Montando o dataset dos últimos 5 dias..."):
                try:
                    nome, n = _gerar_ultimos_5_dias()
                except MongoIndisponivelError as e:
                    st.error(str(e))
                    nome, n = None, 0
            if nome:
                st.session_state["bib_msg"] = (
                    f"Dataset **{nome}** criado com {n:,} leituras.".replace(",", "."))
                st.rerun()
            else:
                st.info("Sem leituras nos últimos 5 dias.")
    msg = st.session_state.pop("bib_msg", None)
    if msg:
        st.success(msg)

    # --- Filtros ---
    c1, c2 = st.columns([1.6, 1.4])
    busca = c1.text_input("Pesquisar", key="bib_busca",
                          placeholder="ex.: MOT-007, comparacao, telemetria, gerente...")
    usar_data = c2.checkbox("Filtrar por data de geração", key="bib_usar_data")
    periodo = None
    if usar_data:
        hoje = datetime.now().date()
        periodo = c2.date_input("Período (calendário)", value=(hoje - timedelta(days=7), hoje),
                                format="DD/MM/YYYY", key="bib_datas")

    try:
        docs = DatasetRepository.listar(busca)
    except MongoIndisponivelError as e:
        st.error(str(e))
        return

    if usar_data and periodo:
        d0 = periodo[0] if isinstance(periodo, (list, tuple)) else periodo
        d1 = periodo[1] if isinstance(periodo, (list, tuple)) and len(periodo) > 1 else d0
        def _no_periodo(d):
            q = d.get("gerado_em")
            if not hasattr(q, "date"):
                return False
            return d0 <= q.date() <= d1
        docs = [d for d in docs if _no_periodo(d)]

    if not docs:
        st.info("Nenhum dataset encontrado com esses filtros. Gere um acima (últimos 5 dias) ou no "
                "fim das telas de Dados Brutos e Consulta de Equipamentos.")
        return

    df = pd.DataFrame([{
        "Arquivo": d.get("nome"),
        "Gerado em": d["gerado_em"].strftime("%d/%m/%Y %H:%M") if hasattr(d.get("gerado_em"), "strftime") else "-",
        "Tela de origem": d.get("origem_tela", "-"),
        "Máquinas": d.get("qtd_maquinas") or (len(d.get("maquinas") or []) or None),
        "Leituras": d.get("linhas"),
        "Tamanho": f"{(d.get('bytes') or 0) / 1024:.0f} KB",
        "Gerado por": d.get("gerado_por", "-"),
    } for d in docs])
    st.dataframe(df, use_container_width=True, hide_index=True, height=min(60 + 36 * len(df), 420))
    st.caption(f"{len(docs)} dataset(s) na biblioteca.")

    nomes = [d["nome"] for d in docs]
    c1, c2, c3 = st.columns([2.4, 1, 1])
    escolhido = c1.selectbox("Dataset", nomes, key="bib_sel")
    doc = next((d for d in docs if d["nome"] == escolhido), {})
    maquinas = doc.get("maquinas") or []
    if maquinas:
        st.caption("Máquinas no arquivo: " + ", ".join(maquinas[:20]) + ("..." if len(maquinas) > 20 else ""))
    csv_texto = DatasetRepository.obter_csv(escolhido)
    c2.write("")
    c3.write("")
    if csv_texto:
        c2.download_button("⬇️ Baixar", csv_texto.encode("utf-8-sig"), file_name=escolhido,
                           mime="text/csv", key="bib_baixar", use_container_width=True)
    else:
        c2.button("⬇️ Baixar", disabled=True, use_container_width=True,
                  help=doc.get("aviso") or "Conteúdo não disponível para este registro.")
    if c3.button("🗑️ Excluir", key="bib_excluir", use_container_width=True):
        DatasetRepository.excluir(escolhido)
        st.rerun()

    if csv_texto:
        with st.expander("👁️ Prévia das primeiras linhas"):
            import io
            st.dataframe(pd.read_csv(io.StringIO(csv_texto), sep=";", decimal=",", nrows=20),
                         use_container_width=True, hide_index=True)


def render_coleta():
    st.title("📥 Coleta de Dados")
    st.caption("Entrada de leituras de máquinas e equipamentos para análise e formação do dataset: "
               "importação de arquivo, registro manual e (em breve) coleta por Bluetooth/IoT.")
    aba = abas(["📄 Arquivo (CSV/Excel)", "✍️ Manual", "📶 Bluetooth / IoT",
                "📚 Biblioteca", "🗃️ Dataset"], "aba_coleta")
    if aba.startswith("📄"):
        _aba_arquivo()
    elif aba.startswith("✍️"):
        _aba_manual()
    elif aba.startswith("📶"):
        _aba_bluetooth()
    elif aba.startswith("📚"):
        _aba_biblioteca()
    else:
        _aba_dataset()
