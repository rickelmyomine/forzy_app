import pandas as pd
import numpy as np

def converter_sinal_4_20ma(sinal_ma, valor_min, valor_max):
    """
    Converte um sinal bruto de 4-20mA para uma escala física definida (ex: 0 a 3600 RPM).
    Fórmula: Valor = ((Sinal - 4) / (20 - 4)) * (Max - Min) + Min
    """
    # Garante que o sinal fique nos limites de 4 a 20 para evitar distorções irreais
    sinal_ma = np.clip(sinal_ma, 4, 20)
    return ((sinal_ma - 4) / 16) * (valor_max - valor_min) + valor_min

def obter_dados_telemetria(qtd_amostras=50):
    """
    Simula a leitura de sensores industriais e aplica o pipeline de conversão.
    """
    # 1. Geração de Dados Brutos (Simulando o hardware)
    sinal_bruto_rotacao = np.random.normal(loc=14, scale=1.5, size=qtd_amostras) # Média 14mA
    sinal_bruto_vibracao = np.random.normal(loc=6, scale=0.8, size=qtd_amostras) # Média 6mA

    df = pd.DataFrame({
        'Tempo (s)': range(1, qtd_amostras + 1),
        'Corrente_Rotacao (mA)': sinal_bruto_rotacao.round(2),
        'Corrente_Vibracao (mA)': sinal_bruto_vibracao.round(2)
    })

    # 2. Aplicação do Pipeline de Transformação
    # Motor de 0 a 3600 RPM
    df['RPM_Convertido'] = converter_sinal_4_20ma(df['Corrente_Rotacao (mA)'], 0, 3600).astype(int)
    
    # Sensor de vibração de 0 a 25 mm/s
    df['Vibracao (mm/s)'] = converter_sinal_4_20ma(df['Corrente_Vibracao (mA)'], 0, 25).round(2)

    return df