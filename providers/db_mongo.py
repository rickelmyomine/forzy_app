import os
import random
from datetime import datetime, timedelta, timezone

import streamlit as st
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError


class MongoIndisponivelError(RuntimeError):
    """Erro lançado quando não é possível conectar ao MongoDB Atlas."""
    pass


def _obter_mongo_uri():
    """
    Busca a connection string do MongoDB Atlas, nessa ordem de prioridade:
    1. st.secrets["MONGODB_URI"]  (arquivo .streamlit/secrets.toml)
    2. Variável de ambiente MONGODB_URI

    Formato esperado (Atlas):
    mongodb+srv://usuario:senha@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
    """
    try:
        if "MONGODB_URI" in st.secrets:
            return st.secrets["MONGODB_URI"]
    except Exception:
        pass
    return os.environ.get("MONGODB_URI")


def _obter_db_name():
    try:
        if "MONGODB_DB_NAME" in st.secrets:
            return st.secrets["MONGODB_DB_NAME"]
    except Exception:
        pass
    return os.environ.get("MONGODB_DB_NAME", "forzy_challenge")


@st.cache_resource(show_spinner=False)
def _obter_client():
    """
    Cria (e mantém em cache entre reruns do Streamlit) a conexão com o
    MongoDB Atlas. Retorna None se a URI não estiver configurada ou se a
    conexão falhar.

    Modo de desenvolvimento: com a variável de ambiente FORZY_USE_MOCK_DB=1
    usa um MongoDB em memória (pacote `mongomock`) para testar o app sem
    acesso ao Atlas. Nunca use isso em produção — os dados somem ao fechar.
    """
    if os.environ.get("FORZY_USE_MOCK_DB") == "1":
        import mongomock
        from providers.mock_seed import popular
        client = mongomock.MongoClient()
        popular(client, _obter_db_name())
        return client

    uri = _obter_mongo_uri()
    if not uri:
        return None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")  # força o teste da conexão agora
        return client
    except PyMongoError:
        return None


def _obter_db():
    client = _obter_client()
    if client is None:
        return None
    return client[_obter_db_name()]


def _exigir_db(mensagem=None):
    db = _obter_db()
    if db is None:
        raise MongoIndisponivelError(
            mensagem
            or "Não foi possível conectar ao MongoDB Atlas. Configure a "
            "variável MONGODB_URI (ou o `.streamlit/secrets.toml`) com "
            "sua connection string."
        )
    return db


def testar_conexao():
    """Usado pela UI para exibir o status da conexão com o Atlas."""
    return _obter_db() is not None


def _agora():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Cadastro técnico de equipamentos
# ---------------------------------------------------------------------------
class EquipamentoRepository:
    """
    Persistência do cadastro técnico de equipamentos na coleção
    "cadastro_equipamentos" do MongoDB Atlas.

    Formato canônico de um documento (campos antigos são preservados):
        TAG, Modelo, Fabricante, Potencia, Tensao,
        Corrente, RPM, Carcaca, GrauProtecao, Isolacao, FatorServico,
        Frequencia, Peso, NumeroSerie, Planta, Area, Localizacao,
        AnoInstalacao, Criticidade, Observacoes,
        foto (base64 JPEG), foto_mime, foto_atualizada_em,
        cadastrado_por, cadastrado_em, atualizado_por, atualizado_em
    """
    COLECAO = "cadastro_equipamentos"

    # Campos grandes que não devem vir em listagens
    _PROJECAO_LISTA = {"_id": 0, "foto": 0}

    @classmethod
    def _colecao(cls):
        return _exigir_db()[cls.COLECAO]

    @classmethod
    def salvar(cls, equipamento_dict):
        cls._colecao().insert_one(dict(equipamento_dict))

    @classmethod
    def buscar_todos(cls, incluir_foto=False):
        # _id nunca é retornado: é um ObjectId do Mongo, não serializável
        # diretamente pelo st.dataframe / pela LLM.
        projecao = {"_id": 0} if incluir_foto else cls._PROJECAO_LISTA
        return list(cls._colecao().find({}, projecao).sort("TAG", 1))

    @classmethod
    def tag_existe(cls, tag):
        return cls._colecao().find_one({"TAG": tag}) is not None

    @classmethod
    def buscar_por_tag(cls, tag):
        return cls._colecao().find_one({"TAG": tag}, {"_id": 0})

    @classmethod
    def atualizar(cls, tag, campos, usuario=None):
        """Atualiza campos de um equipamento existente (merge, não substitui)."""
        campos = {k: v for k, v in dict(campos).items() if k not in ("_id", "TAG")}
        campos["atualizado_em"] = _agora()
        if usuario:
            campos["atualizado_por"] = usuario
        resultado = cls._colecao().update_one({"TAG": tag}, {"$set": campos})
        return resultado.matched_count > 0

    @classmethod
    def salvar_foto(cls, tag, foto_b64, mime="image/jpeg", usuario=None):
        return cls.atualizar(
            tag,
            {"foto": foto_b64, "foto_mime": mime, "foto_atualizada_em": _agora()},
            usuario=usuario,
        )

    @classmethod
    def remover_foto(cls, tag, usuario=None):
        cls._colecao().update_one(
            {"TAG": tag},
            {"$unset": {"foto": "", "foto_mime": "", "foto_atualizada_em": ""},
             "$set": {"atualizado_em": _agora(), "atualizado_por": usuario or ""}},
        )

    @classmethod
    def excluir(cls, tag):
        return cls._colecao().delete_one({"TAG": tag}).deleted_count > 0

    @classmethod
    def listar_tags(cls):
        return sorted(t for t in cls._colecao().distinct("TAG") if t)

    @classmethod
    def migrar_cadastro_legado(cls):
        """
        Os 20 motores importados do Motor.xlsx foram gravados com os campos
        `motor_id`, `fabricante`, `modelo`, `potencia_kw`, `ano_instalacao`
        e sem TAG — por isso o app não os enxergava. Esta migração é
        idempotente: adiciona TAG (MOT-0XX a partir do motor_id) e os campos
        no formato do app, preservando os campos originais.
        Retorna a quantidade de documentos migrados.
        """
        colecao = cls._colecao()
        migrados = 0
        for doc in colecao.find({"TAG": {"$exists": False}, "motor_id": {"$exists": True}}):
            try:
                tag = f"MOT-{int(doc['motor_id']):03d}"
            except (TypeError, ValueError):
                continue
            novos = {"TAG": tag, "migrado_em": _agora()}
            if "fabricante" in doc and "Fabricante" not in doc:
                novos["Fabricante"] = doc["fabricante"]
            if "modelo" in doc and "Modelo" not in doc:
                novos["Modelo"] = doc["modelo"]
            if "potencia_kw" in doc and "Potencia" not in doc:
                kw = doc["potencia_kw"]
                try:
                    novos["Potencia"] = f"{float(kw):g} kW"
                    novos["PotenciaKw"] = float(kw)
                except (TypeError, ValueError):
                    novos["Potencia"] = str(kw)
            if "ano_instalacao" in doc and "AnoInstalacao" not in doc:
                novos["AnoInstalacao"] = doc["ano_instalacao"]
            colecao.update_one({"_id": doc["_id"]}, {"$set": novos})
            migrados += 1
        return migrados

    @classmethod
    def contar_sem_tag(cls):
        return cls._colecao().count_documents({"TAG": {"$exists": False}})


class LocalizacaoRepository:
    """
    Estrutura de Plantas/Áreas. Mantida estática por enquanto (baixa
    frequência de mudança); se quiser editar via tela, dá pra migrar
    para uma coleção "localizacoes" no mesmo padrão do EquipamentoRepository.
    """
    @staticmethod
    def obter_plantas_e_areas():
        return {
            "Planta Matriz - SP": ["Área de Britagem", "Área de Moagem", "Fornos"],
            "Planta Filial - MG": ["Linha de Montagem A", "Estação de Bombeamento", "Compressão"]
        }


class TipoFalhaRepository:
    """
    Tabela de referência dos tipos de falha (importada de
    Dados_Tipos_de_Falha_.csv). Usada para traduzir o código numérico de
    falha em nome/descrição legível na tela e no contexto do Chat IA.
    """
    COLECAO = "tipos_falha"

    # Fallback caso a coleção ainda não tenha sido importada no Mongo
    _PADRAO = {
        0: {"nome": "Normal", "descricao": "Operação dentro dos parâmetros esperados."},
        1: {"nome": "Desbalanceamento", "descricao": "Vibração alta e rotação instável."},
        2: {"nome": "Superaquecimento", "descricao": "Temperatura e corrente elevadas."},
        3: {"nome": "Falha mecânica", "descricao": "Queda de rotação com vibração e corrente altas."},
    }

    @classmethod
    def obter_todos(cls):
        try:
            db = _obter_db()
            if db is not None:
                docs = list(db[cls.COLECAO].find({}, {"_id": 0}))
                if docs:
                    return {int(d["codigo"]): d for d in docs}
        except PyMongoError:
            pass
        return {
            cod: {"codigo": cod, **info} for cod, info in cls._PADRAO.items()
        }

    @classmethod
    def obter_nome(cls, codigo):
        tipos = cls.obter_todos()
        info = tipos.get(int(codigo))
        return info["nome"] if info else f"Código {codigo}"


class AlertaRepository:
    """
    Controla quais leituras críticas/de alerta já geraram uma notificação
    (e-mail), para o monitor em segundo plano (scripts/monitor_alertas.py)
    não enviar o mesmo alerta repetidamente a cada ciclo de verificação.
    """
    COLECAO = "alertas_enviados"

    @classmethod
    def _colecao(cls):
        db = _exigir_db("Não foi possível conectar ao MongoDB Atlas para registrar alertas.")
        colecao = db[cls.COLECAO]
        # Índice único: garante que a mesma leitura (TAG + timestamp) nunca
        # seja notificada duas vezes, mesmo se dois processos rodarem juntos.
        colecao.create_index([("TAG", 1), ("timestamp", 1)], unique=True)
        return colecao

    @classmethod
    def ja_notificado(cls, tag, timestamp):
        return cls._colecao().find_one({"TAG": tag, "timestamp": timestamp}) is not None

    @classmethod
    def marcar_notificado(cls, tag, timestamp, detalhes=None):
        """
        Tenta registrar o alerta como enviado. Retorna True se esse
        processo "ganhou a corrida" (deve mandar a notificação), False se
        outro processo já notificou essa mesma leitura antes.
        """
        try:
            registro = {"TAG": tag, "timestamp": timestamp}
            if detalhes:
                registro["detalhes"] = detalhes
            cls._colecao().insert_one(registro)
            return True
        except PyMongoError:
            # Violação do índice único = já tinha sido notificado antes
            return False

    @classmethod
    def listar_recentes(cls, limite=50):
        db = _obter_db()
        if db is None:
            return []
        return list(
            db[cls.COLECAO].find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limite)
        )


# ---------------------------------------------------------------------------
# Telemetria
# ---------------------------------------------------------------------------
class TelemetriaRepository:
    """
    Continua simulando a leitura de sensores em tempo real (não há
    hardware real conectado), mas agora cada leitura também é registrada
    na coleção "telemetria_historico" do Mongo, permitindo consultar
    tendências ao longo do tempo (usado pelo Chat IA).
    """
    COLECAO_HISTORICO = "telemetria_historico"

    @staticmethod
    def obter_dados_atuais(tag, persistir=False):
        """Leitura simulada (usada só quando a TAG não tem histórico)."""
        from features.limites import classificar_status
        temp = round(random.uniform(55.0, 85.0), 1)
        vib = round(random.uniform(1.0, 6.0), 2)
        corrente = round(random.uniform(10.0, 16.0), 1)
        rpm = round(random.uniform(1700.0, 1850.0), 0)
        status, cor = classificar_status(temp, vib, corrente, rpm, 0)

        leitura = {
            "TAG": tag,
            "Temperatura": temp,
            "Vibracao": vib,
            "Corrente": corrente,
            "RPM": rpm,
            "Status": status,
            "Indicador": cor,
        }

        if persistir:
            try:
                db = _obter_db()
                if db is not None:
                    registro = dict(leitura)
                    registro["timestamp"] = _agora()
                    db[TelemetriaRepository.COLECAO_HISTORICO].insert_one(registro)
            except PyMongoError:
                # Não derruba o dashboard se o log do histórico falhar
                pass

        return leitura

    @classmethod
    def obter_tags_disponiveis(cls):
        """
        Lista as TAGs que já têm leituras no histórico (ex: importadas via
        scripts/importar_dados_historicos.py). Cai para uma lista padrão se
        o Mongo estiver indisponível ou vazio.
        """
        db = _obter_db()
        if db is None:
            return ["MOT-001", "MOT-012", "MOT-015"]
        tags = db[cls.COLECAO_HISTORICO].distinct("TAG")
        return sorted(tags) if tags else ["MOT-001", "MOT-012", "MOT-015"]

    @classmethod
    def obter_historico(cls, tag, limite=50):
        db = _obter_db()
        if db is None:
            return []
        cursor = (
            db[cls.COLECAO_HISTORICO]
            .find({"TAG": tag}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limite)
        )
        return list(cursor)

    @classmethod
    def obter_ultima_leitura(cls, tag):
        """
        Retorna a leitura mais recente já registrada no histórico (real,
        vinda da importação) para essa TAG, ou None se não houver nenhuma.
        """
        db = _obter_db()
        if db is None:
            return None
        doc = (
            db[cls.COLECAO_HISTORICO]
            .find({"TAG": tag}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(1)
        )
        docs = list(doc)
        return docs[0] if docs else None

    @classmethod
    def obter_distribuicao_falhas(cls, tag):
        """
        Conta quantas leituras existem de cada código de falha, para essa
        TAG, considerando TODO o histórico (não só a janela exibida no
        gráfico). Usa agregação do Mongo, então é leve mesmo com muitos
        documentos.
        """
        db = _obter_db()
        if db is None:
            return {}
        pipeline = [
            {"$match": {"TAG": tag}},
            {"$group": {"_id": "$FalhaCodigo", "total": {"$sum": 1}}},
        ]
        resultado = db[cls.COLECAO_HISTORICO].aggregate(pipeline)
        return {doc["_id"]: doc["total"] for doc in resultado if doc["_id"] is not None}

    @classmethod
    def obter_intervalo(cls, inicio, fim, tags=None, campos=None, limite=200000):
        """
        Leituras entre `inicio` e `fim` (datetimes), opcionalmente filtradas por
        TAGs. Retorna lista de dicts ordenada por timestamp.
        """
        db = _obter_db()
        if db is None:
            return []
        filtro = {"timestamp": {"$gte": inicio, "$lte": fim}}
        if tags:
            filtro["TAG"] = {"$in": list(tags)}
        projecao = {"_id": 0}
        if campos:
            projecao.update({c: 1 for c in campos})
        cursor = db[cls.COLECAO_HISTORICO].find(filtro, projecao).sort("timestamp", 1).limit(limite)
        return list(cursor)

    @classmethod
    def obter_falhas_intervalo(cls, inicio, fim, tags=None):
        """Somente leituras com FalhaCodigo != 0 no intervalo."""
        db = _obter_db()
        if db is None:
            return []
        filtro = {"timestamp": {"$gte": inicio, "$lte": fim}, "FalhaCodigo": {"$nin": [0, None]}}
        if tags:
            filtro["TAG"] = {"$in": list(tags)}
        return list(db[cls.COLECAO_HISTORICO].find(filtro, {"_id": 0}).sort("timestamp", 1))

    @classmethod
    def obter_ultimas_n(cls, tag, n=5):
        """Últimas n leituras (mais antiga primeiro) — entrada do modelo de previsão."""
        docs = cls.obter_historico(tag, limite=n)
        return list(reversed(docs))

    @classmethod
    def resumo_intervalo(cls, inicio, fim, tags=None):
        """
        Estatísticas por TAG no intervalo (média/máx/mín de cada variável,
        contagem de leituras por código de falha) via agregação no Mongo.
        Retorna dict {TAG: {...}}.
        """
        db = _obter_db()
        if db is None:
            return {}
        match = {"timestamp": {"$gte": inicio, "$lte": fim}}
        if tags:
            match["TAG"] = {"$in": list(tags)}
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": "$TAG", "n": {"$sum": 1},
                "temp_med": {"$avg": "$Temperatura"}, "temp_max": {"$max": "$Temperatura"}, "temp_min": {"$min": "$Temperatura"},
                "vib_med": {"$avg": "$Vibracao"}, "vib_max": {"$max": "$Vibracao"},
                "cor_med": {"$avg": "$Corrente"}, "cor_max": {"$max": "$Corrente"},
                "rpm_med": {"$avg": "$RPM"}, "rpm_min": {"$min": "$RPM"},
                "falhas": {"$sum": {"$cond": [{"$gt": ["$FalhaCodigo", 0]}, 1, 0]}},
                "alertas": {"$sum": {"$cond": [{"$eq": ["$Status", "Alerta"]}, 1, 0]}},
                "criticos": {"$sum": {"$cond": [{"$eq": ["$Status", "Crítico"]}, 1, 0]}},
                "falhas_1": {"$sum": {"$cond": [{"$eq": ["$FalhaCodigo", 1]}, 1, 0]}},
                "falhas_2": {"$sum": {"$cond": [{"$eq": ["$FalhaCodigo", 2]}, 1, 0]}},
                "falhas_3": {"$sum": {"$cond": [{"$eq": ["$FalhaCodigo", 3]}, 1, 0]}},
                "ultima_falha": {"$max": {"$cond": [{"$gt": ["$FalhaCodigo", 0]}, "$timestamp", None]}},
            }},
        ]
        return {d["_id"]: d for d in db[cls.COLECAO_HISTORICO].aggregate(pipeline) if d["_id"]}

    @classmethod
    def falhas_por_dia(cls, inicio, fim, tags=None):
        """
        Contagem de leituras em falha por TAG e por dia, numa só agregação.
        Permite montar os rankings (dia/semana/mês/ano) sem repetir consultas.
        Retorna lista de {"TAG":..., "dia": "AAAA-MM-DD", "falhas": n}.
        """
        db = _obter_db()
        if db is None:
            return []
        match = {"timestamp": {"$gte": inicio, "$lte": fim}, "FalhaCodigo": {"$gt": 0}}
        if tags:
            match["TAG"] = {"$in": list(tags)}
        pipeline = [
            {"$match": match},
            {"$group": {"_id": {"t": "$TAG", "d": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}},
                        "falhas": {"$sum": 1}}},
        ]
        try:
            docs = list(db[cls.COLECAO_HISTORICO].aggregate(pipeline))
        except Exception:
            return []
        return [{"TAG": d["_id"]["t"], "dia": d["_id"]["d"], "falhas": d["falhas"]} for d in docs if d["_id"].get("t")]

    @classmethod
    def ultimas_leituras(cls, tags=None):
        """
        Última leitura de CADA máquina em uma só consulta (agregação).
        Substitui 20 chamadas a obter_ultima_leitura.
        """
        db = _obter_db()
        if db is None:
            return {}
        janela = datetime.now(timezone.utc) - timedelta(days=2)
        match = {"timestamp": {"$gte": janela}}
        if tags:
            match["TAG"] = {"$in": list(tags)}
        pipeline = [
            {"$match": match},
            {"$sort": {"TAG": 1, "timestamp": -1}},
            {"$group": {"_id": "$TAG", "doc": {"$first": "$$ROOT"}}},
        ]
        saida = {}
        for d in db[cls.COLECAO_HISTORICO].aggregate(pipeline):
            doc = d["doc"]
            doc.pop("_id", None)
            saida[d["_id"]] = doc
        # Máquinas sem leitura na janela: busca individual (raro)
        for t in (tags or []):
            if t not in saida:
                ult = cls.obter_ultima_leitura(t)
                if ult:
                    saida[t] = ult
        return saida

    @classmethod
    def ultimas_n_por_tag(cls, tags, n=5):
        """Últimas n leituras de cada máquina (mais antiga primeiro) em uma só consulta."""
        db = _obter_db()
        if db is None:
            return {}
        janela = datetime.now(timezone.utc) - timedelta(days=2)
        pipeline = [
            {"$match": {"TAG": {"$in": list(tags)}, "timestamp": {"$gte": janela}}},
            {"$sort": {"TAG": 1, "timestamp": -1}},
            {"$group": {"_id": "$TAG", "docs": {"$push": {
                "Temperatura": "$Temperatura", "Vibracao": "$Vibracao", "Corrente": "$Corrente",
                "RPM": "$RPM", "FalhaCodigo": "$FalhaCodigo", "Status": "$Status", "timestamp": "$timestamp"}}}},
            {"$project": {"docs": {"$slice": ["$docs", n]}}},
        ]
        saida = {d["_id"]: list(reversed(d["docs"])) for d in db[cls.COLECAO_HISTORICO].aggregate(pipeline)}
        for t in tags:
            if t not in saida:
                saida[t] = cls.obter_ultimas_n(t, n)
        return saida

    @classmethod
    def periodo_disponivel(cls):
        """(timestamp mínimo, máximo) presentes no histórico."""
        db = _obter_db()
        if db is None:
            return None, None
        col = db[cls.COLECAO_HISTORICO]
        primeiro = col.find_one({}, {"timestamp": 1}, sort=[("timestamp", 1)])
        ultimo = col.find_one({}, {"timestamp": 1}, sort=[("timestamp", -1)])
        return (primeiro or {}).get("timestamp"), (ultimo or {}).get("timestamp")

    @classmethod
    def apagar_sinteticos(cls, origem="sintetico_30d"):
        col = _exigir_db()[cls.COLECAO_HISTORICO]
        return col.delete_many({"origem": origem}).deleted_count

    @classmethod
    def inserir_lote(cls, registros, lote=5000):
        """Insere registros em lotes grandes e desordenados (mais rápido no Atlas)."""
        col = _exigir_db()[cls.COLECAO_HISTORICO]
        for i in range(0, len(registros), lote):
            col.insert_many(registros[i:i + lote], ordered=False)
        return len(registros)

    @classmethod
    def garantir_indices(cls):
        col = _exigir_db()[cls.COLECAO_HISTORICO]
        try:
            col.create_index([("TAG", 1), ("timestamp", -1)])
            col.create_index([("timestamp", 1)])
            col.create_index([("origem", 1)])
            col.create_index([("FalhaCodigo", 1), ("timestamp", 1)])
        except PyMongoError:
            pass

    @classmethod
    def substituir_sinteticos(cls, registros, origem="sintetico_30d", lote=2000):
        """Apaga os documentos de uma origem sintética e insere os novos (em lotes)."""
        col = _exigir_db()[cls.COLECAO_HISTORICO]
        col.delete_many({"origem": origem})
        for i in range(0, len(registros), lote):
            col.insert_many(registros[i:i + lote])
        try:
            col.create_index([("TAG", 1), ("timestamp", -1)])
            col.create_index([("timestamp", 1)])
        except PyMongoError:
            pass
        return len(registros)

    @classmethod
    def obter_resumo_tendencia(cls, tag, limite=50):
        """
        Resumo estatístico simples do histórico recente de um ativo,
        usado como contexto para o Chat IA analisar tendências.
        """
        historico = cls.obter_historico(tag, limite=limite)
        if not historico:
            return f"{tag}: sem histórico registrado ainda no MongoDB."

        temps = [h["Temperatura"] for h in historico]
        vibs = [h["Vibracao"] for h in historico]
        return (
            f"{tag}: {len(historico)} leituras registradas | "
            f"Temp méd {sum(temps)/len(temps):.1f}°C (min {min(temps)} / max {max(temps)}) | "
            f"Vibração méd {sum(vibs)/len(vibs):.2f} mm/s (min {min(vibs)} / max {max(vibs)})"
        )


# ---------------------------------------------------------------------------
# Manutenções (registradas pelos técnicos no app)
# ---------------------------------------------------------------------------
class ManutencaoRepository:
    """
    Coleção "manutencoes": uma ordem de serviço por documento.

    Documento:
        TAG, tipo (Preventiva|Corretiva|Preditiva|Inspeção),
        data (datetime), status (Aberta|Em andamento|Concluída),
        titulo, descricao_problema, servico_executado, pecas_trocadas,
        tempo_parada_horas, custo_estimado, categoria (classificação
        automática do texto), telemetria_no_momento {Temperatura, Vibracao,
        Corrente, RPM, Status, timestamp}, fotos [{b64, mime, legenda,
        momento (Antes|Depois|Durante), enviado_por, enviado_em}],
        tecnico, tecnico_perfil, criado_em, atualizado_em, atualizado_por
    """
    COLECAO = "manutencoes"
    TIPOS = ["Preventiva", "Corretiva", "Preditiva", "Inspeção"]
    STATUS = ["Aberta", "Em andamento", "Concluída"]
    MOMENTOS_FOTO = ["Antes", "Durante", "Depois"]

    @classmethod
    def _colecao(cls):
        colecao = _exigir_db()[cls.COLECAO]
        try:
            colecao.create_index([("TAG", 1), ("data", -1)])
        except PyMongoError:
            pass
        return colecao

    @classmethod
    def criar(cls, registro):
        registro = dict(registro)
        registro.setdefault("criado_em", _agora())
        registro.setdefault("fotos", [])
        registro["os_id"] = cls._proximo_os_id()
        cls._colecao().insert_one(registro)
        return registro["os_id"]

    @classmethod
    def _proximo_os_id(cls):
        ultimo = cls._colecao().find_one(sort=[("os_id", DESCENDING)])
        if not ultimo or not ultimo.get("os_id"):
            return 1
        return int(ultimo["os_id"]) + 1

    @classmethod
    def listar(cls, tag=None, status=None, limite=200, incluir_fotos=False):
        filtro = {}
        if tag:
            filtro["TAG"] = tag
        if status:
            filtro["status"] = status
        projecao = {"_id": 0}
        if not incluir_fotos:
            projecao["fotos.b64"] = 0
        return list(
            cls._colecao().find(filtro, projecao).sort("data", DESCENDING).limit(limite)
        )

    @classmethod
    def buscar(cls, os_id):
        return cls._colecao().find_one({"os_id": int(os_id)}, {"_id": 0})

    @classmethod
    def atualizar(cls, os_id, campos, usuario=None):
        campos = {k: v for k, v in dict(campos).items() if k not in ("_id", "os_id")}
        campos["atualizado_em"] = _agora()
        if usuario:
            campos["atualizado_por"] = usuario
        return cls._colecao().update_one({"os_id": int(os_id)}, {"$set": campos}).matched_count > 0

    @classmethod
    def adicionar_foto(cls, os_id, foto):
        return cls._colecao().update_one(
            {"os_id": int(os_id)}, {"$push": {"fotos": dict(foto)}}
        ).matched_count > 0

    @classmethod
    def excluir(cls, os_id):
        return cls._colecao().delete_one({"os_id": int(os_id)}).deleted_count > 0

    @classmethod
    def resumo_por_tag(cls, tag, limite=5):
        """Texto curto com as últimas manutenções — usado no contexto do Chat IA."""
        docs = cls.listar(tag=tag, limite=limite)
        if not docs:
            return f"{tag}: nenhuma manutenção registrada."
        linhas = []
        for d in docs:
            data = d.get("data")
            data_txt = data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else str(data)
            linhas.append(
                f"OS #{d.get('os_id')} {data_txt} [{d.get('tipo')}/{d.get('status')}] "
                f"{d.get('titulo', '')}: {d.get('servico_executado') or d.get('descricao_problema', '')}"
                f" (téc. {d.get('tecnico', '-')})"
            )
        return f"{tag}:\n  " + "\n  ".join(linhas)

    @classmethod
    def ultimas_por_tag(cls, tags=None):
        """Última OS de cada máquina em uma só consulta."""
        db = _obter_db()
        if db is None:
            return {}
        match = {"TAG": {"$in": list(tags)}} if tags else {}
        pipeline = [
            {"$match": match},
            {"$sort": {"TAG": 1, "data": -1}},
            {"$group": {"_id": "$TAG", "doc": {"$first": {"os_id": "$os_id", "data": "$data", "tipo": "$tipo",
                                                          "status": "$status", "tecnico": "$tecnico"}},
                        "total": {"$sum": 1}}},
        ]
        return {d["_id"]: {**d["doc"], "total": d["total"]} for d in db[cls.COLECAO].aggregate(pipeline)}

    @classmethod
    def estatisticas(cls):
        """Contagens por tipo e status para o dashboard."""
        db = _obter_db()
        if db is None:
            return {"por_tipo": {}, "por_status": {}, "total": 0}
        col = db[cls.COLECAO]
        por_tipo = {d["_id"]: d["n"] for d in col.aggregate(
            [{"$group": {"_id": "$tipo", "n": {"$sum": 1}}}]) if d["_id"]}
        por_status = {d["_id"]: d["n"] for d in col.aggregate(
            [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]) if d["_id"]}
        return {"por_tipo": por_tipo, "por_status": por_status,
                "total": col.count_documents({})}


# ---------------------------------------------------------------------------
# Previsões do modelo de falhas
# ---------------------------------------------------------------------------
class PrevisaoRepository:
    """Última previsão do classificador por TAG (coleção "previsoes")."""
    COLECAO = "previsoes"

    @classmethod
    def salvar(cls, tag, previsao):
        db = _obter_db()
        if db is None:
            return False
        doc = dict(previsao)
        doc["TAG"] = tag
        doc["gerado_em"] = _agora()
        db[cls.COLECAO].update_one({"TAG": tag}, {"$set": doc}, upsert=True)
        return True

    @classmethod
    def obter(cls, tag):
        db = _obter_db()
        if db is None:
            return None
        return db[cls.COLECAO].find_one({"TAG": tag}, {"_id": 0})

    @classmethod
    def obter_todas(cls):
        db = _obter_db()
        if db is None:
            return {}
        return {d["TAG"]: d for d in db[cls.COLECAO].find({}, {"_id": 0})}


# ---------------------------------------------------------------------------
# Funcionários (destinatários dos alertas) — cadastrados pelo gerente
# ---------------------------------------------------------------------------
class FuncionarioRepository:
    """
    Coleção "funcionarios": nome, cargo, email, telefone, planta,
    receber_alertas (bool), criado_por, criado_em.
    """
    COLECAO = "funcionarios"
    CARGOS = ["Gerente de Manutenção", "Técnico de Manutenção", "Operador", "Engenheiro", "Supervisor"]

    @classmethod
    def _colecao(cls):
        col = _exigir_db()[cls.COLECAO]
        try:
            col.create_index([("email", 1)], unique=True, sparse=True)
        except PyMongoError:
            pass
        return col

    @classmethod
    def listar(cls, planta=None, apenas_alertas=False):
        filtro = {}
        if planta and planta != "Todas as plantas":
            filtro["planta"] = planta
        if apenas_alertas:
            filtro["receber_alertas"] = True
        return list(cls._colecao().find(filtro, {"_id": 0}).sort("nome", 1))

    @classmethod
    def criar(cls, dados):
        doc = dict(dados)
        doc["criado_em"] = _agora()
        doc["func_id"] = cls._proximo_id()
        cls._colecao().insert_one(doc)
        return doc["func_id"]

    @classmethod
    def _proximo_id(cls):
        ultimo = cls._colecao().find_one(sort=[("func_id", DESCENDING)])
        return int(ultimo["func_id"]) + 1 if ultimo and ultimo.get("func_id") else 1

    @classmethod
    def atualizar(cls, func_id, campos):
        campos = {k: v for k, v in dict(campos).items() if k not in ("_id", "func_id")}
        campos["atualizado_em"] = _agora()
        return cls._colecao().update_one({"func_id": int(func_id)}, {"$set": campos}).matched_count > 0

    @classmethod
    def excluir(cls, func_id):
        return cls._colecao().delete_one({"func_id": int(func_id)}).deleted_count > 0

    @classmethod
    def buscar(cls, func_id):
        return cls._colecao().find_one({"func_id": int(func_id)}, {"_id": 0})

    @classmethod
    def gerentes(cls):
        return [f for f in cls.listar() if "gerente" in (f.get("cargo") or "").lower()]

    @classmethod
    def contar(cls):
        db = _obter_db()
        return db[cls.COLECAO].count_documents({}) if db is not None else 0


class NotificacaoRepository:
    """Histórico de alertas enviados manualmente / automaticamente pelo app."""
    COLECAO = "notificacoes"

    @classmethod
    def registrar(cls, doc):
        db = _obter_db()
        if db is None:
            return False
        registro = dict(doc)
        registro["enviado_em"] = _agora()
        db[cls.COLECAO].insert_one(registro)
        return True

    @classmethod
    def listar(cls, limite=50):
        db = _obter_db()
        if db is None:
            return []
        return list(db[cls.COLECAO].find({}, {"_id": 0}).sort("enviado_em", DESCENDING).limit(limite))


class DatasetRepository:
    """
    Biblioteca de datasets gerados pelo app.

    Guarda o arquivo CSV compactado (gzip + base64) junto com os metadados,
    para que qualquer usuário possa reencontrar e baixar de novo um dataset
    que já foi gerado, sem refazer a consulta.
    """
    COLECAO = "datasets"
    LIMITE_BYTES = 8 * 1024 * 1024      # teto por documento (limite do Mongo é 16 MB)

    @classmethod
    def registrar(cls, nome, csv_texto, meta=None):
        """Grava o CSV compactado. Retorna o documento salvo (sem o conteúdo)."""
        import base64
        import gzip
        db = _obter_db()
        if db is None:
            return None
        bruto = csv_texto.encode("utf-8")
        comprimido = gzip.compress(bruto)
        doc = {
            "nome": nome,
            "gerado_em": _agora(),
            "linhas": max(0, csv_texto.count("\n") - 1),
            "bytes": len(bruto),
            "bytes_comprimido": len(comprimido),
        }
        doc.update(meta or {})
        if len(comprimido) <= cls.LIMITE_BYTES:
            doc["conteudo_gz"] = base64.b64encode(comprimido).decode("ascii")
        else:
            doc["conteudo_gz"] = None
            doc["aviso"] = "Arquivo grande demais para guardar; só os metadados foram registrados."
        try:
            db[cls.COLECAO].update_one({"nome": nome}, {"$set": doc}, upsert=True)
        except PyMongoError:
            return None
        doc.pop("conteudo_gz", None)
        return doc

    @classmethod
    def listar(cls, busca=None, limite=200):
        """Metadados dos datasets (sem o conteúdo), do mais recente ao mais antigo."""
        db = _obter_db()
        if db is None:
            return []
        filtro = {}
        if busca:
            import re as _re
            padrao = _re.escape(str(busca).strip())
            filtro = {"$or": [{"nome": {"$regex": padrao, "$options": "i"}},
                              {"origem_tela": {"$regex": padrao, "$options": "i"}},
                              {"maquinas": {"$regex": padrao, "$options": "i"}},
                              {"gerado_por": {"$regex": padrao, "$options": "i"}}]}
        return list(db[cls.COLECAO].find(filtro, {"_id": 0, "conteudo_gz": 0})
                    .sort("gerado_em", DESCENDING).limit(limite))

    @classmethod
    def obter_csv(cls, nome):
        """Devolve o CSV descompactado (str) ou None."""
        import base64
        import gzip
        db = _obter_db()
        if db is None:
            return None
        doc = db[cls.COLECAO].find_one({"nome": nome}, {"_id": 0, "conteudo_gz": 1})
        if not doc or not doc.get("conteudo_gz"):
            return None
        try:
            return gzip.decompress(base64.b64decode(doc["conteudo_gz"])).decode("utf-8")
        except Exception:
            return None

    @classmethod
    def excluir(cls, nome):
        db = _obter_db()
        if db is None:
            return False
        return db[cls.COLECAO].delete_one({"nome": nome}).deleted_count > 0


class ConfiguracaoRepository:
    """Configurações do sistema ajustáveis pela tela (valem para todos os usuários)."""
    COLECAO = "configuracoes"

    @classmethod
    def obter(cls, chave, padrao=None):
        db = _obter_db()
        if db is None:
            return padrao
        try:
            doc = db[cls.COLECAO].find_one({"_id": chave})
        except PyMongoError:
            return padrao
        return doc.get("valor") if doc else padrao

    @classmethod
    def definir(cls, chave, valor, usuario=None):
        db = _obter_db()
        if db is None:
            return False
        try:
            db[cls.COLECAO].update_one(
                {"_id": chave},
                {"$set": {"valor": valor, "alterado_em": _agora(), "alterado_por": usuario or "-"}},
                upsert=True)
            return True
        except PyMongoError:
            return False


# ---------------------------------------------------------------------------
# Manutenção do banco
# ---------------------------------------------------------------------------
MAQUINAS_VALIDAS = [f"MOT-{i:03d}" for i in range(1, 21)]


def remover_maquinas_fora_do_escopo(validas=None):
    """
    Apaga de TODAS as coleções qualquer máquina que não esteja na lista de
    máquinas do projeto (MOT-001 a MOT-020) — por exemplo a MOT-021, criada
    em testes. Retorna dict {coleção: removidos}.
    """
    validas = list(validas or MAQUINAS_VALIDAS)
    db = _obter_db()
    if db is None:
        return {}
    filtro = {"$or": [{"TAG": {"$nin": validas}}, {"TAG": {"$exists": False}}]}
    removidos = {}
    for colecao in ("cadastro_equipamentos", "telemetria_historico", "manutencoes",
                    "previsoes", "alertas_enviados", "notificacoes"):
        try:
            if colecao == "cadastro_equipamentos":
                # também remove documentos legados sem TAG
                r = db[colecao].delete_many(filtro)
            else:
                r = db[colecao].delete_many({"TAG": {"$nin": validas + [None]}})
            if r.deleted_count:
                removidos[colecao] = r.deleted_count
        except PyMongoError:
            pass
    return removidos
