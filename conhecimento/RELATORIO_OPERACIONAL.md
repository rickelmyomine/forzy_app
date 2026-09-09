# Relatório Operacional — Monitoramento de Motores Elétricos

**Sistema:** Forzy — Monitoramento e Manutenção Preditiva
**Escopo:** 20 motores elétricos (MOT-001 a MOT-020), duas plantas
**Período de referência:** últimos 30 dias
**Emitido por:** Gerência de Manutenção

> Este documento descreve o estado operacional da planta e a forma como o sistema o apura.
> Os números abaixo são os do período de referência; o app recalcula todos eles em tempo real
> nas telas **Dados Brutos**, **Consulta de Equipamentos** e **Análise de Riscos**.

---

## 1. Resumo executivo

A planta opera com **20 motores monitorados continuamente**, com leitura de temperatura, vibração,
corrente e rotação. No período de referência foram processadas **33.140 leituras**.

- **88,0 %** das leituras em estado Normal
- **3,4 %** em Alerta (fora da faixa ideal, sem falha caracterizada)
- **8,6 %** em estado Crítico
- **2.843 leituras** apresentaram falha classificada pelo modelo

Nenhuma parada não programada foi registrada no período em decorrência de falha não detectada:
todos os eventos críticos foram sinalizados pelo sistema antes de evoluírem.

**Conclusão:** a planta está operacional, com **três motores exigindo atenção prioritária**
(MOT-020, MOT-004 e MOT-013) e um grupo secundário sob observação.

---

## 2. Indicadores do período

### 2.1 Volume e qualidade dos dados

| Indicador | Valor |
|---|---|
| Leituras processadas | 33.140 |
| Máquinas monitoradas | 20 |
| Janela de amostragem (3 dias mais recentes) | 1 leitura a cada 10 min |
| Janela de amostragem (dias 4 a 30) | 1 leitura a cada 30 min |
| Cobertura | 100 % das máquinas com leitura nas últimas 24 h |

### 2.2 Distribuição por estado

| Estado | Leituras | % |
|---|---|---|
| 🟢 Normal | 29.159 | 88,0 % |
| 🟡 Alerta | 1.136 | 3,4 % |
| 🔴 Crítico | 2.845 | 8,6 % |

### 2.3 Distribuição por tipo de falha

| Código | Tipo de falha | Leituras | % do total |
|---|---|---|---|
| 0 | Normal | 30.297 | 91,4 % |
| 2 | Superaquecimento | 1.337 | 4,0 % |
| 3 | Falha mecânica | 796 | 2,4 % |
| 1 | Desbalanceamento | 710 | 2,1 % |

O **superaquecimento é o modo de falha dominante**, respondendo por 47 % das falhas
classificadas — coerente com carga elevada e ventilação/limpeza deficiente, e é o modo com maior
potencial de dano ao isolamento do enrolamento.

### 2.4 Comportamento das variáveis

| Variável | Média | Máximo | Mínimo | Faixa normal |
|---|---|---|---|---|
| Temperatura | 69,0 °C | 103,0 °C | 49,5 °C | 50–80 °C |
| Vibração | 2,9 mm/s | 11,0 mm/s | 0,3 mm/s | 0–4,5 mm/s |
| Corrente | 12,4 A | 18,2 A | 8,3 A | 9–15 A |
| Rotação | 1.771,6 RPM | 1.950,5 RPM | 1.377,9 RPM | 1.680–1.880 RPM |

As médias estão dentro da faixa normal em todas as variáveis. Os valores extremos concentram-se nos
motores listados no item 3 e correspondem aos episódios de falha, não ao regime habitual da planta.

---

## 3. Máquinas que exigem atenção

Ordenadas por quantidade de leituras em estado crítico no período.

| Prioridade | Máquina | Leituras críticas | Em alerta | Modo predominante | Ação recomendada |
|---|---|---|---|---|---|
| 1 | **MOT-020** | 245 | 45 | Superaquecimento | Inspeção térmica e limpeza do sistema de ventilação; verificar carga aplicada |
| 2 | **MOT-004** | 210 | 42 | Superaquecimento | Termografia do enrolamento; medição de corrente por fase |
| 3 | **MOT-013** | 209 | 55 | Falha mecânica | Análise de vibração e inspeção de rolamentos/mancais |
| 4 | MOT-008 | 183 | 66 | Desbalanceamento | Verificar alinhamento e balanceamento do conjunto |
| 5 | MOT-001 | 175 | 50 | Superaquecimento | Acompanhar; reavaliar em 7 dias |
| 6 | MOT-010 | 160 | 48 | Misto | Acompanhar; reavaliar em 7 dias |

As demais 14 máquinas apresentaram comportamento dentro do esperado e permanecem em regime de
manutenção preventiva programada.

---

## 4. Como o sistema apura estes números

### 4.1 Classificação de estado por leitura

Cada leitura é comparada às faixas de referência do manual técnico:

| Variável | Normal | Alerta | Crítico |
|---|---|---|---|
| Temperatura | 50–80 °C | até 88 °C | acima de 88 °C |
| Vibração | 0–4,5 mm/s | até 6,0 mm/s | acima de 6,0 mm/s |
| Corrente | 9–15 A | 8–17 A | fora dessa faixa |
| Rotação | 1.680–1.880 RPM | 1.600–1.950 RPM | fora dessa faixa |

O estado da leitura é o **pior** entre as quatro variáveis. Uma leitura com falha classificada
(código diferente de 0) é sempre tratada como crítica.

### 4.2 Classificação do modo de falha

Modelo `HistGradientBoostingClassifier` (scikit-learn) treinado sobre a série histórica.

- **Entradas (12):** os 4 valores instantâneos + média móvel e desvio-padrão móvel de cada um
  (janela de 5 leituras)
- **Saídas (4):** Normal, Desbalanceamento, Superaquecimento, Falha mecânica
- **Divisão:** cronológica, 80 % treino / 20 % teste, por motor (24.000 / 6.000 amostras)
- **Balanceamento:** pesos por classe, para não ignorar as falhas raras

Desempenho no conjunto de teste:

| Métrica | Valor |
|---|---|
| Acurácia | 97,97 % |
| F1-macro | 0,916 |
| F1 — Normal | 0,989 |
| F1 — Desbalanceamento | 0,924 |
| F1 — Falha mecânica | 0,919 |
| F1 — Superaquecimento | 0,832 |

O F1 mais baixo é o de superaquecimento, com **recall de 0,934 e precisão de 0,75**: o modelo
prefere sinalizar a mais do que deixar passar — comportamento adequado para manutenção preditiva,
onde o custo de um falso negativo (motor queimado) é muito maior que o de um falso positivo
(inspeção desnecessária).

### 4.3 Pontuação de saúde e recomendação

A tela **Análise de Riscos** combina, por máquina: leituras críticas e em alerta, quantidade e tipo
de manutenções no período, horas paradas e o risco previsto pelo modelo, resultando em uma
pontuação de 0 a 100:

| Pontuação | Recomendação |
|---|---|
| 60 a 100 | Manter em operação, seguir o plano preventivo |
| 40 a 59 | Revisar / atualizar — inspeção detalhada e avaliação de retrofit |
| abaixo de 40 | Avaliar substituição — consultar o fabricante sobre reposição ou upgrade |

---

## 5. Alertas

Alertas são disparados apenas em **estado crítico sustentado**: três leituras críticas consecutivas
(aproximadamente 30 minutos). Picos isolados não geram notificação, o que evita o desgaste de
alarmes falsos.

Canais: e-mail (Gmail SMTP) e WhatsApp (Twilio quando configurado; caso contrário, link `wa.me`
com a mensagem pronta). Os destinatários são os funcionários cadastrados que marcaram
"receber alertas", filtráveis por planta.

Formato da mensagem:

```
🔧 *RELATÓRIO DE FALHA DO MOTOR*
*Motor:* MOT-001
*Descrição:* Estado crítico — Superaquecimento detectado por telemetria.
*Temperatura:* 92.5°C
*Vibração:* 4.8 mm/s
*Corrente:* 22.3A
*Ação Recomendada:* Inspeção e manutenção imediatas.
```

Todo alerta enviado fica registrado na coleção `notificacoes`, com data, destinatários, canal e
resultado do envio — o histórico é consultável na tela **Cadastro de Funcionários → Histórico**.

---

## 6. Origem dos dados

| Origem | Situação | Descrição |
|---|---|---|
| Histórico no MongoDB Atlas | **Em operação** | Série de 30 dias das 20 máquinas |
| Importação de arquivo (CSV/Excel) | **Em operação** | Coletas de campo e exportações de outros sistemas |
| Registro manual de leitura | **Em operação** | Medição pontual com instrumento portátil, digitada no app |
| Coleta por Bluetooth / IoT | **Prevista** | Tela pronta; exige integração com coletor BLE ou gateway MQTT |

Toda leitura gravada carrega o campo `origem`, o que permite separar, em qualquer análise, o que veio
do histórico, de arquivo, de digitação manual ou de sensor.

---

## 7. Ações recomendadas

**Imediatas (até 7 dias)**

1. Inspeção térmica de **MOT-020** e **MOT-004** — limpeza de ventilação, verificação de carga e
   medição de corrente por fase.
2. Análise de vibração de **MOT-013** com inspeção de rolamentos e mancais.

**Curto prazo (até 30 dias)**

3. Verificação de alinhamento e balanceamento de **MOT-008**.
4. Reavaliação de MOT-001 e MOT-010 após novo ciclo de 7 dias de telemetria.

**Melhoria contínua**

5. Ativar a coleta automática por Bluetooth/IoT, eliminando a digitação manual em campo.
6. Manter o monitor de alertas (`monitor_alertas.bat`) em execução contínua.
7. Retreinar o modelo de classificação a cada novo mês de dados acumulados.

---

## 8. Limitações declaradas

- O modelo classifica o **modo de falha** a partir da leitura e da sua tendência recente; ele não
  substitui ensaio de laboratório nem análise espectral de vibração.
- A previsão da data de manutenção é uma **estimativa por tendência**, e perde precisão em máquinas
  com poucas leituras ou com regime de operação muito variável.
- Alertas por WhatsApp automático dependem de conta Twilio configurada; sem ela, o envio é por link
  de um clique.
- A coleta por Bluetooth/IoT ainda não está implementada.
