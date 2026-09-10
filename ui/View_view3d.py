"""
View: Visualização 3D
Aba interativa que exibe o motor selecionado como um modelo 3D navegável,
reagindo em tempo real aos dados de telemetria (RPM, vibração, temperatura,
corrente e status de saúde).
"""

import streamlit as st

from providers.db_mongo import (
    EquipamentoRepository,
    TelemetriaRepository,
    MongoIndisponivelError,
)
from ui.Motor_3d import render_motor_engine_3d
from ui.navegacao import botao_ia
from features.prognostico import prever_data_manutencao
from features.textos import INTRO_3D



BOTAO_GRANDE = """
<style>
/* Botao "Analisar com a IA" desta tela: grande e em largura total */
section[data-testid="stMain"] button[kind="primary"],
div[data-testid="stMain"] button[kind="primary"],
div[data-testid="stMain"] div[data-testid="stButton"] > button{
    font-size:1.35rem !important; font-weight:700 !important;
    padding:1.1rem 1.4rem !important; border-radius:12px !important;
    width:100% !important; min-height:68px !important; height:auto !important;}
section[data-testid="stMain"] button[kind="primary"] p,
div[data-testid="stMain"] button[kind="primary"] p,
div[data-testid="stMain"] div[data-testid="stButton"] > button p{
    font-size:1.35rem !important; font-weight:700 !important; line-height:1.3 !important;}
</style>"""

CORES_QUADRO = {
    "Crítico": ("#e66767", "rgba(230,103,103,0.12)", "\U0001F534", "ESTADO CRÍTICO"),
    "Alerta": ("#c98500", "rgba(201,133,0,0.12)", "\U0001F7E1", "EM ALERTA"),
    "Normal": ("#008300", "rgba(0,131,0,0.12)", "\U0001F7E2", "OPERAÇÃO NORMAL"),
}


def _sem_marcacao(texto):
    return (texto or "").replace("**", "")


def _quadro_diagnostico(tag, status, prog):
    """Quadro grande e isolado com a causa do estado e a previsão de manutenção."""
    estado = (prog or {}).get("status") or status or "Normal"
    cor, fundo, icone, rotulo = CORES_QUADRO.get(estado, CORES_QUADRO["Normal"])

    motivos = (prog or {}).get("motivos") or []
    if motivos:
        causa = "; ".join(_sem_marcacao(m) for m in motivos)
    elif estado == "Normal":
        causa = "Todas as variáveis dentro da faixa ideal do manual técnico."
    else:
        causa = "Variável fora da faixa ideal detectada pela telemetria."

    previsao = _sem_marcacao((prog or {}).get("texto", ""))
    bloco_previsao = ""
    if previsao:
        bloco_previsao = (
            '<div style="margin-top:18px; font-size:.9rem; text-transform:uppercase;'
            ' letter-spacing:1.2px; opacity:.75">Previsão de manutenção</div>'
            '<div style="font-size:1.3rem; line-height:1.5; margin-top:4px">'
            '\U0001F4C5 Se continuar operando desta forma: ' + previsao + '</div>'
        )

    st.html(
        '<div style="border:2px solid ' + cor + '; background:' + fundo + '; border-radius:14px;'
        ' padding:22px 26px; margin:6px 0 16px 0;">'
        '<div style="font-size:1.9rem; font-weight:800; color:' + cor + '; letter-spacing:.4px;'
        ' line-height:1.2">' + icone + ' ' + tag + ' — ' + rotulo + '</div>'
        '<div style="margin-top:16px; font-size:.9rem; text-transform:uppercase;'
        ' letter-spacing:1.2px; opacity:.75">O que está causando</div>'
        '<div style="font-size:1.5rem; font-weight:600; line-height:1.45; margin-top:4px">'
        + causa + '</div>'
        + bloco_previsao +
        '</div>'
    )


def render_view3d():
    st.title("🧊 Visualização 3D do Ativo")
    st.caption(
        "Modelo 3D interativo do motor — arraste com o mouse para girar a câmera "
        "e use o scroll para dar zoom. Use os botões no canto superior direito da "
        "cena para alternar entre **Vista Externa**, **Vista Explodida** (peças se "
        "separam) e **Entrar no Motor** (câmera vai para dentro e revela estator, "
        "rotor, rolamentos e bobinas). A cor, a rotação e a vibração do modelo "
        "refletem a telemetria em tempo real do ativo selecionado."
    )

    tags_disponiveis = TelemetriaRepository.obter_tags_disponiveis()
    if not tags_disponiveis:
        st.info("Nenhum ativo disponível para visualização ainda.")
        return

    vindo_do_qr = st.session_state.pop("view3d_tag", None)
    if vindo_do_qr in tags_disponiveis:
        st.session_state["select_ativo_3d"] = vindo_do_qr
    motor_tag = st.selectbox(
        "Selecione o Ativo para Visualizar em 3D:",
        tags_disponiveis,
        key="select_ativo_3d",
    )

    # Mesma lógica de fallback usada em 'Dados Brutos (Telemetria)':
    # prioriza leitura real, cai para mock se não houver histórico ainda.
    leitura_real = TelemetriaRepository.obter_ultima_leitura(motor_tag)
    if leitura_real:
        leitura = leitura_real
        fonte_dado = "📡 dado real importado"
    else:
        leitura = TelemetriaRepository.obter_dados_atuais(motor_tag)
        fonte_dado = "🎲 dado simulado (mock)"

    status_saude = leitura.get("Status", "Normal")
    temp_atual = leitura.get("Temperatura", 25.0)
    vibra_atual = leitura.get("Vibracao", 0.0)
    corrente_atual = leitura.get("Corrente", 0.0)
    rpm_atual = leitura.get("RPM", 0.0)

    try:
        detalhes = EquipamentoRepository.buscar_por_tag(motor_tag)
    except MongoIndisponivelError:
        detalhes = None

    col_info, col_toggle = st.columns([3, 1])
    with col_info:
        if detalhes:
            st.caption(
                f"**{detalhes.get('Modelo', motor_tag)}** — "
                f"{detalhes.get('Fabricante', 'Fabricante não informado')} · "
                f"Fonte da leitura: {fonte_dado}"
            )
        else:
            st.caption(f"Fonte da leitura: {fonte_dado}")
    with col_toggle:
        altura_canvas = st.select_slider(
            "Tamanho da cena",
            options=[360, 420, 480, 560, 640],
            value=480,
        )

    render_motor_engine_3d(
        status=status_saude,
        rpm=rpm_atual,
        vibracao=vibra_atual,
        temperatura=temp_atual,
        corrente=corrente_atual,
        motor_tag=motor_tag,
        height=altura_canvas,
    )

    st.divider()

    prog = prever_data_manutencao(motor_tag)
    _quadro_diagnostico(motor_tag, status_saude, prog)
    st.caption(INTRO_3D)

    st.html(BOTAO_GRANDE)
    botao_ia(motor_tag, f"O modelo 3D do {motor_tag} está mostrando status {status_saude}. Explique o que está acontecendo "
                        f"com base na telemetria e no histórico, e o que o técnico deve fazer.",
             chave=f"ia_3d_{motor_tag}", rotulo=f"🤖 Analisar {motor_tag} com a IA",
             origem="visualizacao_3d", destaque=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", status_saude)
    col2.metric("RPM", f"{rpm_atual:.0f}" if rpm_atual is not None else "-")
    col3.metric("Vibração (mm/s)", vibra_atual)
    col4.metric("Temperatura (°C)", temp_atual)

    with st.expander("ℹ️ Como interpretar o modelo 3D"):
        st.markdown(
            """
- **Cor do motor** — reflete o `Status` do ativo: 🟢 Normal, 🟡 Alerta, 🔴 Crítico.
- **Velocidade de giro do eixo/hélice** — proporcional ao `RPM` atual (escala visual, não literal).
- **Tremor/vibração do modelo** — proporcional ao valor de `Vibração (mm/s)`.
- **Brilho das aletas** — aumenta com a `Temperatura` do motor.
- **Halo no piso** — pulsa mais rápido quanto mais crítico o estado do ativo.

**Modos de visualização (botões no canto superior direito da cena):**
- **🔩 Vista Externa** — o motor fechado, como a placa de identificação real (padrão WEG).
- **🔧 Vista Explodida** — a tampa traseira, a flange dianteira e a caixa de ligação se
  afastam ao longo do eixo, revelando o estator, o rotor e os rolamentos por dentro.
  Use o controle deslizante "Separação das peças" para ajustar o quanto elas se afastam.
- **🔍 Entrar no Motor** — a câmera se aproxima e a carcaça fica semitransparente,
  permitindo "entrar" visualmente no motor e ver rótulos identificando cada peça
  (estator, rotor, rolamentos, ventoinha, caixa de ligação).
- **📷 Foto Real** — mostra/oculta uma miniatura da foto real do motor no canto da
  cena, para comparar com o modelo 3D.
            """
        )