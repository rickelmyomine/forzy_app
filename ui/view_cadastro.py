"""
Cadastro Técnico de Equipamentos.

Abas:
  ➕ Novo equipamento  — foto da placa → OCR (Gemini) → confirma → salva no Mongo
  ✏️ Editar / Foto     — altera dados e adiciona/troca a foto do equipamento
  🖼️ Galeria           — cards com foto, dados principais e última manutenção
  ⚙️ Dados legados      — (gerente) migra os 20 motores importados sem TAG
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from features.estilos import abas

from auth.auth import nome_usuario_atual, eh_gerente
from features.equipamento import cadastrar_equipamento, validar_tag
from features.imagens import comprimir_para_b64, b64_para_bytes, tamanho_legivel
from features.placa_ocr import extrair_dados_placa, CAMPOS_PLACA
from providers.db_mongo import (
    EquipamentoRepository,
    LocalizacaoRepository,
    ManutencaoRepository,
    MongoIndisponivelError,
)

CRITICIDADES = ["A - Alta", "B - Média", "C - Baixa"]

# Folha de dados simplificada: só o essencial para o técnico
_CAMPOS_FORM = [
    # (chave, rótulo, coluna)
    ("Fabricante", "Fabricante", 0),
    ("Modelo", "Modelo", 1),
    ("Potencia", "Potência", 0),
    ("Tensao", "Tensão (V)", 1),
    ("Corrente", "Corrente nominal (A)", 0),
    ("RPM", "Rotação nominal (RPM)", 1),
    ("NumeroSerie", "Nº de série", 0),
]

# Campos extras lidos pelo OCR que viram texto nas Observações
_EXTRAS_OCR = ["Frequencia", "Carcaca", "GrauProtecao", "Isolacao", "FatorServico", "Peso", "Rendimento", "FatorPotencia"]
_ROTULOS_EXTRAS = {"Frequencia": "Frequência", "Carcaca": "Carcaça", "GrauProtecao": "Proteção", "Isolacao": "Isolação",
                   "FatorServico": "FS", "Peso": "Peso", "Rendimento": "Rendimento", "FatorPotencia": "FP"}


def _consolidar_observacoes(dados):
    """Junta os campos extras do OCR em uma linha de observações."""
    partes = [f"{_ROTULOS_EXTRAS[k]} {dados[k]}" for k in _EXTRAS_OCR if dados.get(k)]
    obs = (dados.get("Observacoes") or "").strip()
    if partes:
        obs = ("; ".join(partes) + (". " + obs if obs else "")).strip()
    return obs


def _campos_placa_form(prefixo, valores):
    """Desenha os campos da placa em duas colunas e devolve dict com os valores."""
    col = st.columns(2)
    resultado = {}
    for chave, rotulo, idx in _CAMPOS_FORM:
        resultado[chave] = col[idx].text_input(
            rotulo, value=str(valores.get(chave, "") or ""), key=f"{prefixo}_{chave}"
        )
    resultado["Observacoes"] = st.text_area(
        "Observações (para o técnico na manutenção)",
        value=str(valores.get("Observacoes", "") or ""),
        key=f"{prefixo}_Observacoes",
        height=90,
        placeholder="Ex.: rolamentos 6205-ZZ, graxa Polyrex EM, ponto de lubrificação lateral, cuidados especiais...",
    )
    c1, c2 = st.columns(2)
    resultado["site_url"] = c1.text_input("Site do fabricante (link)", value=str(valores.get("site_url", "") or ""), key=f"{prefixo}_site")
    resultado["manual_url"] = c2.text_input("Manual (link)", value=str(valores.get("manual_url", "") or ""), key=f"{prefixo}_manual")
    return resultado


def _upload_pdf(prefixo, valores):
    """Folha de dados do fabricante em PDF (guardada em base64 no Mongo)."""
    atual = valores.get("datasheet_nome")
    if atual:
        st.caption(f"📄 PDF atual: {atual}")
    pdf = st.file_uploader("Folha de dados do fabricante (PDF, até 5 MB)", type=["pdf"], key=f"{prefixo}_pdf")
    if pdf is not None:
        dados = pdf.getvalue()
        if len(dados) > 5 * 1024 * 1024:
            st.error("PDF acima de 5 MB.")
            return None
        import base64
        return {"datasheet_pdf": base64.b64encode(dados).decode("ascii"), "datasheet_nome": pdf.name}
    return None


def _campos_localizacao_form(prefixo, valores):
    estrutura = LocalizacaoRepository.obter_plantas_e_areas()
    plantas = list(estrutura.keys())
    planta_atual = valores.get("Planta") or st.session_state.get("planta_selecionada") or plantas[0]
    if planta_atual not in plantas:
        planta_atual = plantas[0]
    c1, c2, c3 = st.columns(3)
    planta = c1.selectbox("Planta", plantas, index=plantas.index(planta_atual), key=f"{prefixo}_Planta")
    crit_atual = valores.get("Criticidade") if valores.get("Criticidade") in CRITICIDADES else CRITICIDADES[1]
    criticidade = c2.selectbox("Criticidade", CRITICIDADES, index=CRITICIDADES.index(crit_atual), key=f"{prefixo}_Crit")
    ano = c3.text_input("Ano de instalação", value=str(valores.get("AnoInstalacao", "") or ""), key=f"{prefixo}_Ano")
    return {"Planta": planta, "Criticidade": criticidade, "AnoInstalacao": ano}


# ---------------------------------------------------------------------------
# Aba 1 — Novo equipamento
# ---------------------------------------------------------------------------
def _aba_novo():
    st.write("Fotografe a **placa de identificação** do motor. A IA lê os dados da placa; "
             "você confere, informa a TAG e a localização, e o cadastro é salvo no MongoDB Atlas.")

    arquivo = st.file_uploader(
        "Foto da placa ou do equipamento (JPG, PNG)", type=["jpg", "jpeg", "png"], key="novo_foto"
    )

    if arquivo is None:
        for k in ("ocr_dados", "ocr_msg", "ocr_arquivo"):
            st.session_state.pop(k, None)
        return

    # Reprocessa OCR se trocou o arquivo
    if st.session_state.get("ocr_arquivo") != arquivo.name:
        st.session_state.pop("ocr_dados", None)
        st.session_state.pop("ocr_msg", None)
        st.session_state["ocr_arquivo"] = arquivo.name

    dados_brutos = arquivo.getvalue()
    foto_b64, mime, tamanho = comprimir_para_b64(dados_brutos)

    col_img, col_ocr = st.columns([1, 1.4])
    with col_img:
        st.image(dados_brutos, caption=f"{arquivo.name} — será salva com {tamanho_legivel(tamanho)}", use_container_width=True)
    with col_ocr:
        if st.button("🔍 Ler dados da placa (OCR com IA)", type="primary", use_container_width=True):
            with st.spinner("Lendo a placa com o Gemini..."):
                dados, msg = extrair_dados_placa(b64_para_bytes(foto_b64), mime)
            if dados:
                dados["Observacoes"] = _consolidar_observacoes(dados)
                st.session_state["ocr_dados"] = dados
                st.session_state["ocr_msg"] = None
            else:
                st.session_state["ocr_dados"] = {c: "" for c in CAMPOS_PLACA}
                st.session_state["ocr_msg"] = msg
            # limpa os inputs do formulário para receberem os valores novos
            for chave, _, _ in _CAMPOS_FORM:
                st.session_state.pop(f"novo_{chave}", None)
            st.session_state.pop("novo_Observacoes", None)
            st.rerun()

        if st.session_state.get("ocr_msg"):
            st.warning(st.session_state["ocr_msg"])
        elif st.session_state.get("ocr_dados"):
            preenchidos = sum(1 for v in st.session_state["ocr_dados"].values() if v)
            st.success(f"Placa lida: {preenchidos} campos identificados. Confira abaixo antes de salvar.")
        else:
            st.info("Clique no botão para a IA ler a placa, ou preencha os campos manualmente.")

    valores = st.session_state.get("ocr_dados", {})

    st.subheader("Identificação")
    c1, c2 = st.columns([1, 2])
    tag = c1.text_input("TAG do equipamento *", placeholder="MOT-022", key="novo_TAG").strip().upper()
    if tag and not validar_tag(tag):
        c2.error("Formato: 3 letras, hífen, 3 dígitos (ex.: MOT-022).")
    elif tag:
        try:
            if EquipamentoRepository.tag_existe(tag):
                c2.warning(f"{tag} já existe. Use a aba *Editar / Foto* para alterar.")
        except MongoIndisponivelError:
            pass

    st.subheader("Dados da placa")
    placa = _campos_placa_form("novo", valores)

    st.subheader("Planta e criticidade")
    loc = _campos_localizacao_form("novo", {})
    pdf = _upload_pdf("novo", {})

    salvar_foto = st.checkbox("Salvar esta imagem como foto do equipamento", value=True)

    if st.button("✅ Confirmar e salvar no MongoDB", type="primary"):
        if not tag:
            st.error("Informe a TAG do equipamento.")
            return
        if not placa.get("Fabricante") and not placa.get("Modelo"):
            st.error("Informe ao menos Fabricante ou Modelo.")
            return
        extras = {**placa, **loc, **(pdf or {})}
        if salvar_foto:
            extras["foto"] = foto_b64
            extras["foto_mime"] = mime
            extras["foto_atualizada_em"] = datetime.utcnow()
        ok, msg = cadastrar_equipamento(
            tag=tag,
            modelo=placa.get("Modelo", ""),
            fabricante=placa.get("Fabricante", ""),
            potencia=placa.get("Potencia", ""),
            tensao=placa.get("Tensao", ""),
            extras=extras,
            usuario=nome_usuario_atual(),
        )
        if ok:
            st.success(f"{msg} ({tag} salvo no MongoDB Atlas por {nome_usuario_atual()})")
            for k in ("ocr_dados", "ocr_msg", "ocr_arquivo"):
                st.session_state.pop(k, None)
        else:
            st.error(msg)


# ---------------------------------------------------------------------------
# Aba 2 — Editar / Foto
# ---------------------------------------------------------------------------
def _aba_editar():
    try:
        tags = EquipamentoRepository.listar_tags()
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    if not tags:
        st.info("Nenhum equipamento com TAG cadastrado ainda.")
        return

    tag = st.selectbox("Equipamento", tags, key="edit_tag")
    doc = EquipamentoRepository.buscar_por_tag(tag) or {}

    col_foto, col_dados = st.columns([1, 1.6])
    with col_foto:
        st.markdown("**Foto do equipamento**")
        if doc.get("foto"):
            st.image(b64_para_bytes(doc["foto"]), use_container_width=True)
            atualizada = doc.get("foto_atualizada_em")
            if atualizada:
                st.caption(f"Atualizada em {atualizada:%d/%m/%Y %H:%M}" if hasattr(atualizada, "strftime") else str(atualizada))
            if st.button("Remover foto", key="btn_rm_foto"):
                EquipamentoRepository.remover_foto(tag, usuario=nome_usuario_atual())
                st.rerun()
        else:
            st.info("Sem foto cadastrada.")

        nova = st.file_uploader("Enviar / trocar foto", type=["jpg", "jpeg", "png"], key=f"edit_foto_{tag}")
        if nova is not None:
            b64, mime, tam = comprimir_para_b64(nova.getvalue())
            st.image(nova.getvalue(), caption=f"Prévia ({tamanho_legivel(tam)})", use_container_width=True)
            if st.button("Salvar foto", type="primary", key="btn_salvar_foto"):
                EquipamentoRepository.salvar_foto(tag, b64, mime, usuario=nome_usuario_atual())
                st.success("Foto salva no MongoDB.")
                st.rerun()

    with col_dados:
        st.markdown(f"**Dados de {tag}**")
        with st.form(f"form_edit_{tag}"):
            placa = _campos_placa_form(f"edit_{tag}", doc)
            st.markdown("**Planta e criticidade**")
            loc = _campos_localizacao_form(f"edit_{tag}", doc)
            salvar = st.form_submit_button("💾 Salvar alterações", type="primary")
        pdf = _upload_pdf(f"edit_{tag}", doc)
        if pdf and st.button("Salvar PDF", key=f"btn_pdf_{tag}"):
            EquipamentoRepository.atualizar(tag, pdf, usuario=nome_usuario_atual())
            st.success("PDF salvo.")
            st.rerun()
        if salvar:
            EquipamentoRepository.atualizar(tag, {**placa, **loc}, usuario=nome_usuario_atual())
            st.success("Cadastro atualizado.")
            st.rerun()

        meta = []
        if doc.get("cadastrado_por"):
            meta.append(f"cadastrado por {doc['cadastrado_por']}")
        if doc.get("atualizado_por"):
            meta.append(f"última alteração por {doc['atualizado_por']}")
        if meta:
            st.caption(" · ".join(meta))

        if eh_gerente():
            with st.expander("🗑️ Excluir equipamento (gerente)"):
                st.warning("Esta ação remove o cadastro. O histórico de telemetria e as manutenções não são apagados.")
                confirma = st.text_input("Digite a TAG para confirmar", key=f"del_{tag}")
                if st.button("Excluir definitivamente", key=f"btn_del_{tag}") and confirma.strip().upper() == tag:
                    EquipamentoRepository.excluir(tag)
                    st.success(f"{tag} excluído.")
                    st.rerun()


# ---------------------------------------------------------------------------
# Aba 3 — Galeria
# ---------------------------------------------------------------------------

    _bloco_exportar_inventario()


def _bloco_exportar_inventario():
    """Planilha CSV e relatório PDF com todos os motores e suas especificações."""
    from features.inventario import tabela_inventario, csv_inventario, pdf_inventario, nome_arquivo
    st.divider()
    st.subheader("📋 Exportar o inventário completo")
    st.caption("Todos os motores cadastrados com os dados de placa, o estado atual pela última "
               "leitura e a data da última manutenção. A planilha abre no Excel; o PDF já vem "
               "formatado para imprimir ou enviar.")
    try:
        df = tabela_inventario()
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    if df is None or df.empty:
        st.info("Nenhum equipamento cadastrado para exportar.")
        return

    c1, c2, c3 = st.columns([1.4, 1, 1])
    c1.markdown(f"**{len(df)}** máquina(s) · **{len(df.columns)}** campos por máquina")
    c2.download_button("⬇️ Planilha (CSV)", csv_inventario(df).encode("utf-8-sig"),
                       file_name=nome_arquivo("csv"), mime="text/csv",
                       use_container_width=True, key="inv_csv")
    if c3.button("📄 Gerar PDF", use_container_width=True, key="inv_pdf_gerar"):
        with st.spinner("Montando o relatório..."):
            st.session_state["inv_pdf"] = pdf_inventario(df)
    if st.session_state.get("inv_pdf"):
        st.download_button("⬇️ Baixar relatório (PDF)", st.session_state["inv_pdf"],
                           file_name=nome_arquivo("pdf"), mime="application/pdf",
                           use_container_width=True, key="inv_pdf_baixar")

    with st.expander("👁️ Prévia do inventário"):
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=min(60 + 36 * len(df), 420))


def _aba_placas():
    """Etiquetas com QR Code para colar nas máquinas."""
    from features.qrcodes import (url_configurada, link_maquina, placa_png,
                                  zip_placas, pdf_placas, nome_arquivo)
    st.markdown("**Placas com QR Code das máquinas**")
    st.caption("Cada máquina ganha uma etiqueta para imprimir e colar no motor. Ao ler o QR com a "
               "câmera do celular, o app abre direto na máquina — o técnico vê o painel e abre a OS "
               "sem procurar em lista nenhuma.")

    try:
        equipamentos = EquipamentoRepository.buscar_todos(incluir_foto=True)
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    equipamentos = [e for e in equipamentos if e.get("TAG")]
    if not equipamentos:
        st.info("Nenhum equipamento cadastrado.")
        return

    padrao = url_configurada()
    with st.container(border=True):
        st.markdown("**Endereço do app usado no QR Code**")
        base = st.text_input("Endereço", value=st.session_state.get("qr_base", padrao),
                             key="qr_base", label_visibility="collapsed",
                             placeholder="https://seu-app.streamlit.app")
        if "localhost" in (base or ""):
            st.warning("Este é o endereço local: o QR só vai funcionar no computador que roda o app. "
                       "Depois de publicar o sistema, cole aqui o endereço público e gere as placas "
                       "de novo antes de imprimir.")
        else:
            st.success(f"As placas vão apontar para {base}")
        st.caption("Para não precisar digitar toda vez, grave em `.streamlit/secrets.toml`: "
                   "`APP_URL = \"https://seu-app.streamlit.app\"`")

    c1, c2 = st.columns([2, 1])
    busca = c1.text_input("Buscar por TAG, fabricante ou modelo", key="pl_busca").lower()
    plantas = ["Todas"] + sorted({e.get("Planta") for e in equipamentos if e.get("Planta")})
    planta = c2.selectbox("Planta", plantas, key="pl_planta")

    filtrados = [
        e for e in equipamentos
        if (not busca or busca in " ".join(str(e.get(k, "")) for k in ("TAG", "Fabricante", "Modelo")).lower())
        and (planta == "Todas" or e.get("Planta") == planta)
    ]
    st.caption(f"{len(filtrados)} máquina(s) selecionada(s)")
    if not filtrados:
        return

    d1, d2 = st.columns(2)
    if d1.button("🖨️ Gerar folha de placas (PDF)", type="primary", use_container_width=True, key="pl_pdf"):
        with st.spinner("Montando as etiquetas..."):
            st.session_state["pl_pdf_dados"] = pdf_placas(filtrados, base)
    if d2.button("🗂️ Gerar imagens (ZIP)", use_container_width=True, key="pl_zip"):
        with st.spinner("Montando as imagens..."):
            st.session_state["pl_zip_dados"] = zip_placas(filtrados, base)

    e1, e2 = st.columns(2)
    if st.session_state.get("pl_pdf_dados"):
        e1.download_button("⬇️ Baixar folha de placas (PDF)", st.session_state["pl_pdf_dados"],
                           file_name=nome_arquivo("pdf"), mime="application/pdf",
                           use_container_width=True, key="pl_pdf_baixar")
    if st.session_state.get("pl_zip_dados"):
        e2.download_button("⬇️ Baixar imagens (ZIP)", st.session_state["pl_zip_dados"],
                           file_name=nome_arquivo("zip"), mime="application/zip",
                           use_container_width=True, key="pl_zip_baixar")

    st.divider()
    por_linha = 3
    for i in range(0, len(filtrados), por_linha):
        cols = st.columns(por_linha)
        for col, e in zip(cols, filtrados[i:i + por_linha]):
            with col:
                with st.container(border=True):
                    png = placa_png(e["TAG"], e, base)
                    st.image(png, use_container_width=True)
                    st.caption(link_maquina(e["TAG"], base))
                    st.download_button("⬇️ Placa individual", png,
                                       file_name=f"placa_{e['TAG']}.png", mime="image/png",
                                       key=f"pl_um_{e['TAG']}", use_container_width=True)


# ---------------------------------------------------------------------------
# Aba 4 — Dados legados (gerente)
# ---------------------------------------------------------------------------
def _aba_legado():
    """Migração de cadastros antigos e importação de inventário de outro sistema."""
    st.markdown("**Trazer equipamentos de outro inventário para o sistema**")
    st.caption("Duas formas: importar uma planilha do inventário atual da empresa, ou acertar "
               "documentos que já estão no banco mas em formato antigo.")

    st.markdown("#### 1. Importar planilha de inventário (CSV ou Excel)")
    st.write("Uma linha por máquina. O sistema reconhece os nomes de coluna mais comuns; a única "
             "coluna obrigatória é a que identifica a máquina.")
    with st.expander("📋 Colunas reconhecidas"):
        st.markdown(
            "| Campo no sistema | Nomes aceitos na planilha | Obrigatória |\n|---|---|---|\n"
            "| TAG | tag, maquina, motor, motor_id, equipamento, ativo | **sim** |\n"
            "| Fabricante | fabricante, marca, manufacturer | não |\n"
            "| Modelo | modelo, model | não |\n"
            "| Potencia | potencia, potencia_kw, kw, cv | não |\n"
            "| Tensao | tensao, tensão, volts, v | não |\n"
            "| Corrente | corrente, corrente_a, amperes | não |\n"
            "| RPM | rpm, rotacao, rotação | não |\n"
            "| NumeroSerie | serie, numero_serie, n_serie, serial | não |\n"
            "| Planta | planta, unidade, fabrica, site | não |\n"
            "| Localizacao | localizacao, local, setor, area | não |\n"
            "| Criticidade | criticidade, classe, prioridade | não |\n"
            "| AnoInstalacao | ano, ano_instalacao, instalado_em | não |\n"
            "| Observacoes | observacoes, obs, notas | não |\n\n"
            "TAGs numéricas (1, 2, 3...) viram MOT-001, MOT-002, MOT-003."
        )
    modelo = pd.DataFrame([{
        "TAG": "MOT-001", "Fabricante": "WEG", "Modelo": "W22 Premium", "Potencia": "7.5 kW",
        "Tensao": "380 V", "Corrente": "15 A", "RPM": "1770", "NumeroSerie": "1129176649",
        "Planta": "Planta Matriz - SP", "Localizacao": "Linha 1", "Criticidade": "A - Alta",
        "AnoInstalacao": 2021, "Observacoes": "",
    }])
    st.download_button("⬇️ Baixar planilha modelo",
                       modelo.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name="modelo_inventario.csv", mime="text/csv", key="leg_modelo")

    arquivo = st.file_uploader("Arquivo do inventário", type=["csv", "xlsx", "xls"], key="leg_arq")
    if arquivo is not None:
        from features.importar_inventario import ler_planilha, importar
        try:
            df, mapa, faltando = ler_planilha(arquivo)
        except Exception as e:
            st.error(f"Não foi possível ler o arquivo: {e}")
            return
        if faltando:
            st.error("A planilha precisa de uma coluna que identifique a máquina "
                     "(TAG, maquina, motor, motor_id, equipamento ou ativo).")
            st.dataframe(df.head(10), use_container_width=True)
            return
        st.success(f"{len(df)} linha(s) lida(s). Colunas reconhecidas: "
                   + ", ".join(f"{o} → {d}" for o, d in mapa.items()))
        st.dataframe(df.head(15), use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        sobrescrever = c1.checkbox("Sobrescrever campos já preenchidos", value=False, key="leg_sobre")
        if c2.button("▶️ Importar para o cadastro", type="primary", key="leg_importar"):
            try:
                criados, atualizados, ignorados = importar(df, mapa, sobrescrever,
                                                           usuario=nome_usuario_atual())
            except MongoIndisponivelError as e:
                st.error(str(e))
                return
            st.success(f"{criados} equipamento(s) criado(s), {atualizados} atualizado(s)"
                       + (f", {ignorados} linha(s) ignorada(s) por falta de identificação." if ignorados else "."))
            st.rerun()

    st.divider()
    st.markdown("#### 2. Acertar documentos antigos que já estão no banco")
    st.write(
        "Equipamentos importados de sistemas anteriores podem estar gravados com os campos "
        "`motor_id`, `fabricante`, `modelo`, `potencia_kw`, `ano_instalacao` e **sem TAG**. "
        "Como o app identifica as máquinas pela TAG, esses documentos não aparecem nas telas. "
        "A correção adiciona `TAG = MOT-0XX` e os campos no formato do app, **sem apagar** os "
        "campos originais. Pode ser executada mais de uma vez."
    )
    try:
        pendentes = EquipamentoRepository.contar_sem_tag()
    except MongoIndisponivelError as e:
        st.error(str(e))
        return
    st.metric("Documentos sem TAG", pendentes)
    if pendentes and st.button("▶️ Corrigir documentos sem TAG", type="primary", key="leg_migrar"):
        n = EquipamentoRepository.migrar_cadastro_legado()
        st.success(f"{n} equipamento(s) corrigido(s).")
        st.rerun()
    if not pendentes:
        st.success("Nenhum documento pendente — o cadastro já está no formato do app.")


def render_cadastro():
    st.write("Cadastro técnico simplificado: foto, dados essenciais da placa (OCR), observações para o técnico e documentos.")
    rotulos = ["➕ Novo equipamento", "📋 Inventário", "🏷️ Placas QR code"]
    if eh_gerente():
        rotulos.append("🗄️ Legado")
    aba = abas(rotulos, "aba_cadastro")
    if aba.startswith("➕"):
        _aba_novo()
    elif aba.startswith("📋"):
        _aba_editar()
    elif aba.startswith("🏷️"):
        _aba_placas()
    else:
        _aba_legado()
