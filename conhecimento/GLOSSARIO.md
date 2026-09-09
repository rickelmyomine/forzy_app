# Glossário

Termos usados no sistema de monitoramento e manutenção preditiva de motores elétricos.

---

## Manutenção

**Manutenção preditiva**
Estratégia que acompanha o comportamento da máquina em operação (temperatura, vibração, corrente,
rotação) para intervir **antes** da quebra, no momento em que os dados indicam que a falha está se
formando. É o que este sistema faz.

**Manutenção preventiva**
Intervenção feita em intervalos fixos (por tempo ou por horas de operação), independentemente do
estado da máquina. Simples de programar, mas troca peças que ainda serviriam e não protege contra
falhas fora do calendário.

**Manutenção corretiva**
Intervenção depois que a falha já aconteceu. É a mais cara: soma o custo do reparo ao custo da
parada não programada da produção.

**OS — Ordem de Serviço**
Registro de uma manutenção executada: máquina, data, tipo, técnico responsável, descrição do
serviço, peças trocadas, tempo de parada e fotos. Fica gravada na coleção `manutencoes`.

**Tempo de parada**
Horas em que a máquina ficou indisponível por causa da manutenção. Entra no cálculo da pontuação de
saúde da máquina.

**Retrofit**
Modernização de um equipamento existente — troca de componentes por versões atuais, sem substituir a
máquina inteira. É a recomendação intermediária entre "manter" e "substituir".

---

## Grandezas monitoradas

**Temperatura (°C)**
Temperatura da carcaça ou do enrolamento do motor. Faixa normal de referência: **50 a 80 °C**;
alerta até 88 °C; acima disso, crítico. Temperatura alta sustentada degrada o isolamento do
enrolamento e encurta a vida do motor.

**Vibração (mm/s)**
Velocidade de vibração medida na carcaça. Faixa normal: **0 a 4,5 mm/s**; alerta até 6,0 mm/s.
É o indicador mais sensível a problemas mecânicos — desalinhamento, desbalanceamento, folga e
desgaste de rolamento aparecem primeiro na vibração.

**Corrente (A)**
Corrente elétrica consumida pelo motor. Faixa normal: **9 a 15 A**; alerta de 8 a 17 A. Corrente
acima do normal indica sobrecarga mecânica ou problema elétrico; corrente muito abaixo pode indicar
que a máquina está trabalhando em vazio ou perdeu acoplamento.

**Rotação (RPM)**
Velocidade de giro do eixo. Faixa normal: **1.680 a 1.880 RPM**; alerta de 1.600 a 1.950 RPM.
Queda de rotação com corrente subindo é sinal clássico de sobrecarga.

**Telemetria**
O conjunto das leituras dessas grandezas ao longo do tempo. Uma "leitura" é um registro com as
quatro grandezas em um instante, associado a uma máquina.

---

## Estados e classificação

**Normal 🟢**
Todas as variáveis dentro da faixa ideal e nenhuma falha classificada. Máquina operando como
esperado.

**Alerta 🟡**
Ao menos uma variável fora da faixa ideal, mas ainda dentro da faixa tolerada. Não exige parada;
exige acompanhamento.

**Crítico 🔴**
Ao menos uma variável fora da faixa tolerada, ou falha classificada pelo modelo. Exige inspeção.

**Crítico sustentado**
Três leituras críticas consecutivas (cerca de 30 minutos). É a condição que dispara alerta por
e-mail e WhatsApp — picos isolados não disparam.

---

## Modos de falha

**Normal (código 0)**
Sem falha caracterizada.

**Desbalanceamento (código 1)**
Distribuição irregular de massa no rotor ou no conjunto acoplado. Sintoma típico: vibração elevada
em rotação constante, com temperatura e corrente próximas do normal. Correção: balanceamento e
verificação de alinhamento.

**Superaquecimento (código 2)**
Temperatura acima do tolerado, geralmente acompanhada de corrente elevada. Causas comuns:
sobrecarga, ventilação obstruída, ambiente quente, problema no enrolamento. É o modo mais frequente
nesta planta e o de maior risco para o isolamento.

**Falha mecânica (código 3)**
Degradação de componentes mecânicos — rolamento, mancal, acoplamento. Sintoma típico: vibração alta
combinada com queda de rotação e ruído. Costuma evoluir rápido depois que aparece.

---

## Análise e modelo

**Dataset**
Conjunto organizado das leituras usado para treinar e avaliar o modelo. Neste sistema, 30 dias de
telemetria das 20 máquinas.

**Feature (variável de entrada)**
Cada informação que o modelo recebe para decidir. Aqui são 12: os 4 valores instantâneos, mais a
média móvel e o desvio-padrão móvel de cada um.

**Janela móvel**
Trecho das últimas N leituras (aqui, N = 5) usado para calcular média e desvio-padrão. É o que
permite ao modelo enxergar **tendência** — uma temperatura de 82 °C subindo há uma hora é diferente
de 82 °C estável.

**Média móvel**
Média das últimas 5 leituras de uma variável. Suaviza ruído e revela para onde o valor está indo.

**Desvio-padrão móvel**
Quanto a variável oscilou nas últimas 5 leituras. Oscilação alta costuma preceder falha mecânica.

**HistGradientBoostingClassifier**
Algoritmo de classificação do scikit-learn baseado em árvores de decisão construídas em sequência,
cada uma corrigindo os erros das anteriores. Escolhido por lidar bem com dados tabulares, classes
desbalanceadas e valores faltantes.

**Divisão cronológica**
Separação treino/teste pela ordem do tempo (80 % mais antigos para treinar, 20 % mais recentes para
testar), feita por motor. Evita que o modelo "veja o futuro" durante o treino, o que inflaria
artificialmente o resultado.

**Acurácia**
Percentual de leituras classificadas corretamente. Aqui: **97,97 %**. Sozinha ela engana quando as
classes são desbalanceadas — por isso também se usa o F1.

**F1-score**
Média harmônica entre precisão e recall, de 0 a 1. **F1-macro** é a média do F1 de todas as classes
tratadas com o mesmo peso, o que revela se o modelo está indo mal nas falhas raras. Aqui: **0,916**.

**Precisão**
Das leituras que o modelo apontou como uma falha, quantas realmente eram. Precisão baixa = muitos
alarmes falsos.

**Recall (sensibilidade)**
Das falhas que realmente ocorreram, quantas o modelo detectou. Recall baixo = falhas passando
despercebidas. Em manutenção preditiva, recall alto vale mais que precisão alta.

**Class weight balanced**
Ajuste que dá mais peso às classes raras durante o treino, para o modelo não aprender a "chutar
Normal sempre" — o que daria boa acurácia e nenhuma utilidade.

**Pontuação de saúde**
Nota de 0 a 100 por máquina, combinando leituras críticas e em alerta, manutenções, horas paradas e
risco previsto. Acima de 60: manter. De 40 a 59: revisar/atualizar. Abaixo de 40: avaliar
substituição.

---

## Sistema e tecnologia

**MongoDB Atlas**
Banco de dados na nuvem onde ficam todos os dados. Por estar na nuvem, várias pessoas em plantas
diferentes veem a mesma informação atualizada.

**Coleção**
Equivalente a uma tabela. As principais: `cadastro_equipamentos`, `telemetria_historico`,
`manutencoes`, `previsoes`, `funcionarios`, `notificacoes`, `alertas_enviados`, `tipos_falha`.

**TAG**
Identificador único da máquina no sistema, no formato `MOT-001` a `MOT-020`.

**Agregação**
Consulta que resume muitos documentos de uma vez no próprio banco (somas, médias, contagens),
em vez de trazer tudo para o app. É o que mantém as telas rápidas.

**Índice**
Estrutura que acelera a busca no banco. Aqui existem índices por TAG + data, por data, por origem e
por código de falha.

**Streamlit**
Biblioteca Python que transforma o código em uma aplicação web. Cada interação recarrega o script,
por isso o uso de cache é essencial para o desempenho.

**Cache**
Guarda o resultado de uma consulta cara para reaproveitar por alguns minutos, em vez de refazê-la a
cada clique.

**Origem da leitura**
Campo que registra de onde veio cada leitura: histórico, arquivo importado, coleta manual ou
Bluetooth. Permite auditar e separar os dados por procedência.

---

## Agente de IA

**Gemini**
Modelo de linguagem do Google usado pelo agente. Recebe o contexto montado com os dados da planta e
responde em português.

**Grounding (ancoragem)**
Prática de dar ao modelo os dados reais antes da pergunta, para que ele responda com base neles em
vez de inventar. Aqui o contexto inclui cadastro, telemetria, falhas, previsões e manutenções.

**RAG (Retrieval-Augmented Generation)**
Técnica que busca, na documentação do sistema, os trechos mais relevantes para a pergunta e os
entrega ao modelo junto com ela. Neste sistema a busca usa TF-IDF com similaridade de cosseno sobre
os documentos da pasta `conhecimento/`.

**TF-IDF**
Forma de medir a importância de uma palavra em um documento comparada ao conjunto de documentos.
Palavras comuns pesam pouco; palavras específicas pesam muito.

**Similaridade de cosseno**
Medida de quão parecidos são dois textos representados como vetores. Usada para escolher os trechos
da documentação que mais combinam com a pergunta.

**Dúvidas frequentes**
As 55 perguntas prontas do Chat IA. São respondidas **sem** chamar a IA externa: o app calcula a
resposta diretamente dos dados do MongoDB. Por isso são instantâneas e sempre exatas.

**Pergunta livre**
Qualquer pergunta digitada pelo usuário. Vai para o Gemini com todo o contexto do sistema, e o
modelo pode ainda buscar na internet (manuais, normas, catálogos de fabricante) e citar as fontes.

**Busca na internet (Google Search grounding)**
Recurso que permite ao agente consultar a web durante a resposta, usado para informações que não
estão nos dados da planta — norma técnica, especificação de fabricante, prática de mercado.

**OCR (reconhecimento óptico de caracteres)**
Leitura automática do texto da placa de identificação do motor a partir de uma foto, usada no
cadastro técnico para preencher fabricante, modelo, potência e tensão.
