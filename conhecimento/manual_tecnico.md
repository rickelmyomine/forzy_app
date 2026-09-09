# Manual Técnico — Sistema de Monitoramento de Motores (IO-Link)

## 1. Visão Geral do Sistema

O sistema monitorado é composto por dois pontos de medição (Porta 1 e Porta 2) conectados a um Mestre IO-Link, cada um reportando três variáveis de processo: velocidade, aceleração e temperatura. A forte correlação observada entre os dois pontos (correlação de velocidade próxima de 1,0) indica que ambos monitoram um sistema mecanicamente acoplado, como um eixo de entrada e saída de um redutor ou duas polias da mesma linha de transmissão.

## 2. Especificação dos Sensores

Cada ponto de medição reporta três sinais via protocolo IO-Link (Process Data Input — PDI):

- **Velocidade**: sinal adimensional relacionado à rotação do eixo monitorado. Observa-se dois regimes estáveis na operação normal: próximo de zero (equipamento ocioso) e entre 6,3 e 7,7 (equipamento em operação plena).
- **Aceleração**: variação da velocidade no tempo. Em operação estável, tende a acompanhar de perto a velocidade; picos isolados de aceleração fora do padrão de rampa normal são indicativos de instabilidade mecânica.
- **Temperatura**: medida em graus Celsius. O Ponto de Medição 2 opera sistematicamente mais quente que o Ponto 1 (diferença média de 5 a 6°C), o que é uma característica normal de projeto, não uma anomalia.

## 3. Faixas Operacionais de Referência

| Sensor | Regime Ocioso | Regime Em Operação |
|---|---|---|
| Velocidade (ambos os pontos) | 0,03 – 0,06 | 6,3 – 7,7 |
| Temperatura Ponto 1 | ~33°C (média) | ~31°C (média) |
| Temperatura Ponto 2 | ~39°C (média) | ~36°C (média) |
| Aceleração (ambos os pontos) | próxima de 0 | 0,3 – 0,6 |

Leituras que se afastam significativamente dessas faixas — considerando o regime operacional correto — são candidatas a investigação, mas nem toda leitura fora da faixa típica representa falha confirmada; consulte sempre o histórico recente do equipamento antes de agir.

## 4. Troubleshooting — Superaquecimento (Anomalia Térmica)

Sintomas: temperatura do Ponto 1 ou Ponto 2 consistentemente acima da faixa de referência da Seção 3, especialmente se o desvio persistir por mais de um episódio de operação.

Procedimento recomendado:
1. Verificar se o sistema de ventilação/refrigeração do equipamento está funcionando corretamente e sem obstruções.
2. Confirmar se a carga aplicada ao equipamento está dentro da especificação de projeto — sobrecarga é uma causa comum de superaquecimento.
3. Verificar se a divergência de temperatura entre Ponto 1 e Ponto 2 se manteve dentro do padrão histórico (5–6°C); uma divergência maior pode indicar problema localizado em um dos pontos.
4. Caso a temperatura ultrapasse 45°C de forma sustentada, escalar para manutenção corretiva imediata.

## 5. Troubleshooting — Anomalia Mecânica (Vibração/Aceleração)

Sintomas: aceleração fora do padrão esperado para o regime operacional, especialmente quando acompanhada de divergência de velocidade entre os dois pontos de medição (`diff_velocidade` elevado).

Procedimento recomendado:
1. Verificar o acoplamento mecânico entre os dois pontos monitorados — folgas ou desalinhamentos tendem a se manifestar como divergência de velocidade entre os pontos.
2. Inspecionar visualmente rolamentos e elementos de transmissão em busca de desgaste.
3. Registrar se a anomalia ocorre predominantemente durante rampas de partida (comportamento transitório esperado) ou também em regime estabilizado (mais preocupante).
4. Se a divergência de velocidade ultrapassar 1,5 unidades de forma recorrente fora de rampas de partida, abrir ordem de serviço corretiva.

## 6. Interpretação de Divergência entre Pontos de Medição

Como os dois pontos monitoram um sistema mecanicamente acoplado, a diferença entre suas leituras de velocidade é normalmente pequena (mediana de 0,04 no histórico de referência). Divergências maiores concentram-se nos momentos de partida do equipamento (rampas), o que é esperado fisicamente. Divergência elevada fora de rampas de partida é o principal indicador precoce de folga, desgaste ou desalinhamento na transmissão entre os dois pontos.

## 7. Procedimento de Manutenção Preventiva

Periodicidade recomendada: mensal (inspeção rápida) e trimestral (revisão completa).

Checklist mensal:
- Verificar fixação física dos sensores IO-Link em ambos os pontos de medição.
- Limpar os pontos de medição e conexões, removendo poeira e resíduos.
- Conferir se a comunicação com o Mestre IO-Link está estável, sem lacunas de leitura anormalmente longas (acima de 60 segundos).

Checklist trimestral:
- Lubrificação dos mancais e elementos de transmissão.
- Revisão do cabeamento IO-Link e testes de continuidade.
- Recalibração dos sensores conforme especificação do fabricante.
- Análise da tendência de temperatura e vibração dos últimos 3 meses para identificar degradação gradual.

## 8. Procedimento de Manutenção Corretiva

Quando um alerta crítico é confirmado por inspeção física:
1. Isolar o equipamento com segurança antes de qualquer intervenção.
2. Registrar as leituras de sensor no momento da parada (temperatura, velocidade, aceleração de ambos os pontos) para rastreabilidade.
3. Executar o reparo (substituição de peça, correção de folga, desobstrução de ventilação, conforme o caso).
4. Após o reparo, monitorar o equipamento por pelo menos um ciclo completo de operação antes de considerar o caso encerrado.
5. Atualizar o histórico de manutenção do ativo com a causa raiz identificada.

## 9. Limitações do Sistema de Monitoramento Atual

O baseline operacional atual foi calibrado sobre uma única janela de aproximadamente 4 horas de operação. Isso significa que variações sazonais, de carga ou de temperatura ambiente ao longo de dias/semanas ainda não estão refletidas nos limiares de referência. Além disso, a base de dados não possui rótulo de falha confirmado — os alertas gerados são sinais estatísticos de desvio, não diagnósticos definitivos, e devem sempre ser confirmados por inspeção humana antes de uma decisão de parada de equipamento.

## 10. Glossário Rápido de Severidade

- **Leve**: desvio estatístico pequeno, sem ação imediata necessária, manter monitoramento de rotina.
- **Moderado**: desvio perceptível, recomenda-se acompanhamento nas próximas horas e registro em checklist.
- **Crítico**: desvio significativo, recomenda-se inspeção física prioritária e verificação imediata das condições de operação.


## 11. Especificação do Motor (Fabricante — WEG)

Diferente das seções anteriores (calibradas a partir da distribuição estatística do `History_3.csv`), esta seção reproduz uma **folha de dados real** do fabricante, para o motor monitorado por este sistema (Linha W22 Monofásico, código do produto 13887610, carcaça 100L).

- **Potência nominal**: 2,2 kW (3 CV), 60 Hz.
- **Tensão nominal**: 110–127 / 220–254 V.
- **Rotação nominal**: 3.525 rpm (motor de 2 polos).
- **Corrente nominal**: 25,0–21,7 / 12,5–10,8 A.
- **Classe de isolamento**: F, com elevação de temperatura nominal de 105 K sobre a temperatura ambiente de referência (até 40°C).
- **Grau de proteção**: IP55. Forma construtiva B3D. Método de partida direta.
- **Mancais**: 6206 ZZ (dianteiro e traseiro), vedação V'Ring.
- **Massa aproximada**: 38,6 kg.
- **Rendimento**: 72,7% a 50% de carga, 79,2% a 75%, 81,8% a 100% da carga nominal.

**Nota de compatibilidade de unidades:** os valores acima são especificações de projeto do motor, em unidades de engenharia (rpm, kW, °C, A). Já as leituras do `History_3.csv` vêm do sensor IO-Link acoplado ao equipamento, em escala própria do sensor (ex.: "velocidade" entre 0,03 e 7,7, sem unidade de rpm declarada). Por não termos a folha de dados do próprio sensor IO-Link, não é possível converter diretamente entre as duas escalas — por isso, os limiares operacionais usados nas Seções 3 a 8 deste manual continuam sendo os calibrados estatisticamente sobre os dados reais de sensor, e não os valores nominais desta folha de dados. Esta seção serve como referência factual sobre o motor (potência, classe de isolamento, proteção, etc.), não como fonte de limiares de alerta.