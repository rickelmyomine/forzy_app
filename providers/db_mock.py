import streamlit as st
import random

class EquipamentoRepository:
    """
    Classe responsável por simular a persistência de dados.
    No futuro, você só precisará alterar esta classe para conectar a um PostgreSQL, DynamoDB, etc.
    """
    
    @staticmethod
    def _iniciar_db():
        if 'equipamentos' not in st.session_state:
            st.session_state['equipamentos'] = []

    @classmethod
    def salvar(cls, equipamento_dict):
        cls._iniciar_db()
        st.session_state['equipamentos'].append(equipamento_dict)

    @classmethod
    def buscar_todos(cls):
        cls._iniciar_db()
        return st.session_state['equipamentos']

    @classmethod
    def tag_existe(cls, tag):
        cls._iniciar_db()
        return any(eq['TAG'] == tag for eq in st.session_state['equipamentos'])
class LocalizacaoRepository:
    """
    Classe responsável por simular os dados de localização (Plantas e Áreas).
    """
    @staticmethod
    def obter_plantas_e_areas():
        return {
            "Planta Matriz - SP": ["Área de Britagem", "Área de Moagem", "Fornos"],
            "Planta Filial - MG": ["Linha de Montagem A", "Estação de Bombeamento", "Compressão"]
        }
class TelemetriaRepository:
    """
    Classe responsável por simular a leitura de sensores em tempo real.
    """
    @staticmethod
    def obter_dados_atuais(tag):
        # Simulando dados baseados no equipamento
        temp = round(random.uniform(35.0, 85.0), 1)
        vib = round(random.uniform(0.5, 5.0), 2)
        corrente = round(random.uniform(10.0, 25.0), 1)
        
        # Lógica de Alertas e Status (Requisito 4)
        if temp < 60:
            status = "Normal"
            cor = "🟢"
        elif temp < 75:
            status = "Alerta"
            cor = "🟡"
        else:
            status = "Crítico"
            cor = "🔴"
            
        return {
            "TAG": tag,
            "Temperatura": temp,
            "Vibracao": vib,
            "Corrente": corrente,
            "Status": status,
            "Indicador": cor
        }