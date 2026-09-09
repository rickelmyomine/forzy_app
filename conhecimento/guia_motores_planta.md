# Guia de Telemetria e Falhas dos Motores da Planta (Forzy)

> Consolida os limiares operacionais usados no dashboard, os quatro estados de falha do
> dataset de telemetria e as ações de manutenção associadas.

## 1. Variáveis monitoradas e faixas de referência

Cada motor (MOT-001 a MOT-020) reporta quatro variáveis a cada 10 minutos: temperatura (°C),
vibração (mm/s), corrente (A) e rotação (RPM). Faixas de referência calibradas no histórico:

| Variável | Normal | Alerta | Crítico |
|---|---|---|---|
| Temperatura | 50 a 80 °C | 80 a 88 °C | acima de 88 °C |
| Vibração | até 4,5 mm/s | 4,5 a 6,0 mm/s | acima de 6,0 mm/s |
| Corrente | 9 a 15 A | 15 a 17 A | acima de 17 A |
| Rotação | 1680 a 1880 RPM | 1600 a 1680 RPM | abaixo de 1600 RPM |

Uma leitura com código de falha rotulado (1, 2 ou 3) é sempre Crítico. Sem falha rotulada,
o status é o pior entre as quatro variáveis.

## 2. Estado 0 — Normal

Operação dentro dos parâmetros esperados: temperatura média 68 °C, vibração média 2,7 mm/s,
corrente média 12,3 A, rotação média 1776 RPM. Nenhuma ação além do plano preventivo.

## 3. Estado 1 — Desbalanceamento

Vibração alta (média 7,3 mm/s, picos acima de 11 mm/s) com rotação instável. Temperatura e
corrente pouco alteradas. Causas típicas: desbalanceamento do rotor ou da carga acoplada,
desalinhamento, fixação frouxa, desgaste de rolamento. Ação: inspeção de vibração, verificar
alinhamento e fixação; vibração sustentada acima de 6 mm/s exige OS corretiva.

## 4. Estado 2 — Superaquecimento

Temperatura elevada (média 84 °C, picos acima de 100 °C) com corrente elevada (média 14,6 A).
Vibração e rotação próximas do normal. Causas típicas: sobrecarga, ventilação obstruída,
aletas sujas, tensão desbalanceada, problema de isolação. Ação: verificar ventilação e carga,
medir corrente por fase; temperatura sustentada acima de 88 °C exige parada e manutenção corretiva.

## 5. Estado 3 — Falha mecânica

Queda de rotação (média 1570 RPM) com vibração (média 6,1 mm/s) e corrente (média 14 A) altas.
Causas típicas: rolamento travando, acoplamento danificado, transmissão com folga, carga travada.
Ação: isolar o equipamento com segurança, inspecionar acoplamento, rolamentos e transmissão;
registrar as leituras no momento da parada para rastreabilidade.

## 6. Modelo de previsão de falhas

Classificador de gradient boosting treinado no histórico rotulado (30.000 leituras de 20 motores),
com as 4 variáveis e média/desvio móvel das últimas 5 leituras. Acurácia em teste cronológico
~98 % e F1-macro ~0,92. O modelo devolve a probabilidade de cada estado; o risco é 1 menos a
probabilidade de Normal: baixo (< 20 %), moderado (20–50 %) e alto (> 50 %). O erro mais comum
do modelo é no início da rampa de deterioro, quando os sinais ainda são próximos do normal.
Uma previsão é um sinal para priorizar inspeção, não um diagnóstico confirmado.

## 7. Plano de manutenção preventiva dos motores

Mensal: inspeção visual, limpeza das aletas e da ventilação, verificação de fixação e ruído.
Trimestral: lubrificação dos mancais (graxa indicada na placa, ex.: Mobil Polyrex EM), reaperto,
medição de corrente por fase e análise de tendência de temperatura e vibração.
Anual: verificação de isolação (megger), alinhamento e balanceamento.

## 8. Registro de manutenção no app

Toda intervenção é registrada em Manutenções (tipo, data, problema, serviço, peças, tempo de
parada, fotos antes/durante/depois). O app captura automaticamente a última telemetria da
máquina no momento do registro e classifica o evento em anomalia elétrica, anomalia mecânica,
manutenção preventiva, manutenção corretiva ou operação normal.
