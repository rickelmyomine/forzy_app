# Corpus Estruturado — Base de Conhecimento do Agente de IA

Corpus de referência usado pelo agente de IA para responder perguntas sobre operação, diagnóstico e
manutenção dos motores. Cada bloco é uma unidade recuperável: o sistema localiza os blocos mais
relevantes para a pergunta (TF-IDF + similaridade de cosseno) e os entrega ao modelo junto com os
dados reais da planta.

**Estrutura de cada bloco:** título (`##`), categoria, sintomas, causas prováveis, diagnóstico,
ação recomendada e referência.

---

## Superaquecimento por sobrecarga mecânica

**Categoria:** superaquecimento
**Sintomas:** temperatura acima de 88 °C sustentada; corrente acima de 15 A; rotação levemente
abaixo do nominal; vibração dentro do normal.
**Causas prováveis:** carga acoplada acima da capacidade do motor; acionamento de máquina travada
ou com atrito excessivo; correia excessivamente tensionada; processo operando fora do ponto de
projeto.
**Diagnóstico:** comparar a corrente atual com a corrente nominal da placa. Se a corrente subiu
junto com a temperatura e a rotação caiu, a origem é mecânica, não elétrica. Verificar a máquina
acionada antes do motor.
**Ação recomendada:** reduzir ou redistribuir a carga; inspecionar o equipamento acionado;
verificar tensionamento de correias e alinhamento do acoplamento. Se a carga estiver correta,
avaliar se o motor está subdimensionado para a aplicação.
**Referência:** faixa normal de temperatura 50–80 °C; corrente 9–15 A.

## Superaquecimento por ventilação deficiente

**Categoria:** superaquecimento
**Sintomas:** temperatura subindo lentamente ao longo de dias; corrente normal; vibração normal;
rotação normal.
**Causas prováveis:** aletas da carcaça obstruídas por poeira ou resíduo; ventoinha danificada ou
solta; motor instalado em local sem circulação de ar; temperatura ambiente elevada.
**Diagnóstico:** o dado que distingue este caso do anterior é a **corrente normal**. Temperatura
subindo sem aumento de corrente significa que o motor não está trabalhando mais — está dissipando
menos. Inspeção visual resolve na maioria dos casos.
**Ação recomendada:** limpeza das aletas e da tampa defletora; verificação da ventoinha; revisão da
instalação quanto a espaço livre para circulação de ar.
**Referência:** temperatura acima de 88 °C é crítica; entre 80 e 88 °C é alerta.

## Superaquecimento de origem elétrica

**Categoria:** superaquecimento
**Sintomas:** temperatura alta; corrente desequilibrada entre fases; possível ruído elétrico;
partida difícil.
**Causas prováveis:** desequilíbrio de tensão na alimentação; falta de fase; conexão frouxa ou
oxidada no terminal; curto entre espiras do enrolamento.
**Diagnóstico:** medir tensão e corrente nas três fases. Desequilíbrio acima de 2 % na tensão
provoca aquecimento desproporcional. Medir a resistência de isolamento do enrolamento.
**Ação recomendada:** corrigir a alimentação antes de qualquer intervenção no motor; reapertar e
limpar terminais. Isolamento comprometido exige rebobinamento ou substituição.
**Referência:** este é o modo com maior risco de perda total do motor.

## Desbalanceamento do rotor

**Categoria:** desbalanceamento
**Sintomas:** vibração entre 4,5 e 6,0 mm/s (alerta) ou acima de 6,0 mm/s (crítico); temperatura
normal; corrente normal; rotação estável.
**Causas prováveis:** massa irregular no rotor; acúmulo de material na parte girante; perda de
contrapeso; empenamento do eixo; pá de ventilador quebrada.
**Diagnóstico:** vibração isolada, sem alteração de temperatura ou corrente, aponta para
desbalanceamento e não para desgaste. A amplitude é constante e proporcional à rotação.
**Ação recomendada:** limpeza do rotor e do conjunto girante; balanceamento dinâmico; verificação
de empenamento do eixo. Se persistir após balanceamento, investigar o conjunto acoplado.
**Referência:** vibração normal até 4,5 mm/s.

## Desalinhamento do acoplamento

**Categoria:** desbalanceamento
**Sintomas:** vibração elevada; leve aumento de temperatura; corrente pouco acima do normal;
desgaste visível no acoplamento.
**Causas prováveis:** base desnivelada ou com pé solto; alinhamento não refeito após intervenção
anterior; dilatação térmica da tubulação ou da estrutura; fundação deteriorada.
**Diagnóstico:** verificar o aperto e o calçamento dos quatro pés antes de qualquer alinhamento —
pé solto simula desalinhamento e volta logo depois de corrigido.
**Ação recomendada:** alinhamento a laser com o conjunto na temperatura de operação; correção da
base; substituição do elemento elástico do acoplamento.
**Referência:** desalinhamento não corrigido é a principal causa de falha prematura de rolamento.

## Degradação de rolamento

**Categoria:** falha mecânica
**Sintomas:** vibração crescente ao longo de dias; ruído agudo ou intermitente; temperatura
localizada no mancal; rotação começando a oscilar.
**Causas prováveis:** fim de vida útil; lubrificação insuficiente ou em excesso; contaminação da
graxa; carga radial acima do previsto; passagem de corrente pelo rolamento (comum em motor
acionado por inversor sem aterramento adequado).
**Diagnóstico:** a assinatura é a **tendência**: o desvio-padrão móvel da vibração cresce antes de a
média cruzar o limite. Por isso o modelo usa janela móvel, e não só o valor instantâneo.
**Ação recomendada:** análise de vibração com espectro; relubrificação conforme o plano; se já
houver ruído audível, programar a troca do rolamento — a evolução a partir daí é rápida.
**Referência:** vibração crítica acima de 6,0 mm/s.

## Queda de rotação com aumento de corrente

**Categoria:** falha mecânica
**Sintomas:** rotação abaixo de 1.680 RPM; corrente acima de 15 A; temperatura subindo.
**Causas prováveis:** sobrecarga mecânica progressiva; travamento parcial da máquina acionada;
rolamento em estágio avançado de desgaste; queda de tensão na alimentação.
**Diagnóstico:** rotação caindo enquanto a corrente sobe indica que o motor está lutando contra uma
resistência crescente. É a combinação mais urgente do sistema, porque tende a evoluir para parada.
**Ação recomendada:** parada programada para inspeção do conjunto mecânico; não aguardar o próximo
ciclo de manutenção preventiva.
**Referência:** rotação normal 1.680–1.880 RPM.

## Leitura crítica isolada sem alerta enviado

**Categoria:** operação do sistema
**Sintomas:** o painel mostra uma leitura crítica, mas nenhum alerta chegou por e-mail ou WhatsApp.
**Causas prováveis:** comportamento esperado — o sistema exige **três leituras críticas
consecutivas** (cerca de 30 minutos) antes de notificar.
**Diagnóstico:** conferir na tela Dados Brutos se as leituras seguintes voltaram ao normal. Se
voltaram, foi um pico transitório (partida, variação momentânea de carga).
**Ação recomendada:** nenhuma ação imediata para pico isolado. Se picos se repetirem no mesmo
horário todos os dias, investigar o regime de operação.
**Referência:** regra de crítico sustentado, 3 leituras.

## Máquina sem leitura recente

**Categoria:** operação do sistema
**Sintomas:** máquina aparece sem estado atual ou com dado antigo nas telas.
**Causas prováveis:** coleta interrompida; máquina parada para manutenção; falha de comunicação do
sensor ou do gateway.
**Diagnóstico:** verificar a data da última leitura na Consulta de Equipamentos e conferir se há OS
aberta para a máquina no período.
**Ação recomendada:** se a máquina está operando, tratar como falha de coleta; enquanto isso,
registrar leitura manual na tela Coleta de Dados para não deixar buraco no histórico.
**Referência:** toda leitura carrega o campo `origem`, que permite identificar coletas manuais.

## Priorização quando várias máquinas estão críticas

**Categoria:** gestão da manutenção
**Sintomas:** mais de uma máquina em estado crítico ao mesmo tempo.
**Causas prováveis:** condição comum de operação em planta com muitos ativos.
**Diagnóstico:** ordenar por criticidade cadastrada (A alta, B média, C baixa), depois por
quantidade de leituras críticas no período, depois por modo de falha — falha mecânica com queda de
rotação evolui mais rápido que superaquecimento estável.
**Ação recomendada:** usar a tela Análise de Riscos, que já combina esses fatores em uma pontuação
de saúde, e o atalho "Ver só as críticas" em Dados Brutos.
**Referência:** pontuação abaixo de 40 indica avaliar substituição.

## Decidir entre reparar, atualizar ou substituir

**Categoria:** gestão da manutenção
**Sintomas:** máquina com histórico repetido de manutenções corretivas e pontuação de saúde baixa.
**Causas prováveis:** equipamento em fim de vida útil; aplicação inadequada; falta de correção da
causa raiz nas intervenções anteriores.
**Diagnóstico:** comparar o custo acumulado de corretivas e as horas paradas com o custo de um
motor novo. Verificar o ano de instalação e a disponibilidade de peças junto ao fabricante.
**Ação recomendada:** pontuação acima de 60, manter o plano preventivo; entre 40 e 59, avaliar
retrofit dos componentes críticos; abaixo de 40, cotar substituição e consultar o fabricante sobre
modelo equivalente de maior eficiência.
**Referência:** tela Análise de Riscos.

## Interpretar a previsão do modelo

**Categoria:** modelo preditivo
**Sintomas:** o app indica um modo de falha e um nível de risco (baixo, moderado, alto) para uma
máquina que aparentemente opera normal.
**Causas prováveis:** o modelo usa média e desvio-padrão das últimas 5 leituras, então enxerga
tendência antes de o valor instantâneo cruzar o limite.
**Diagnóstico:** risco moderado ou alto com valores ainda dentro da faixa é justamente o cenário
que a manutenção preditiva busca — a hora de agir com a máquina ainda operando.
**Ação recomendada:** risco alto, programar inspeção em até 7 dias; risco moderado, acompanhar e
reavaliar no ciclo seguinte.
**Referência:** acurácia do modelo 97,97 %, F1-macro 0,916.

## Por que o modelo às vezes marca superaquecimento a mais

**Categoria:** modelo preditivo
**Sintomas:** inspeção não confirma o superaquecimento apontado pelo modelo.
**Causas prováveis:** a classe superaquecimento foi treinada com recall alto (0,934) e precisão
menor (0,75) — o modelo prefere sinalizar a mais.
**Diagnóstico:** comportamento intencional. Em manutenção preditiva o custo de deixar passar uma
falha real é muito maior que o de uma inspeção desnecessária.
**Ação recomendada:** tratar o aviso como pedido de verificação, não como diagnóstico fechado.
Confirmar com termografia antes de intervir.
**Referência:** relatório de classificação em `modelos/modelo_falhas_meta.json`.

## Registrar coleta feita em campo

**Categoria:** operação do sistema
**Sintomas:** técnico mediu a máquina com instrumento portátil e precisa lançar o valor.
**Causas prováveis:** máquina sem sensor instalado, ou verificação pontual de conferência.
**Diagnóstico:** o sistema aceita a entrada por duas vias, ambas em operação.
**Ação recomendada:** para uma medição, usar Coleta de Dados → Manual (escolhe a máquina, data,
hora e os quatro valores). Para várias, usar Coleta de Dados → Arquivo, com CSV ou Excel — os nomes
de coluna são reconhecidos de forma flexível.
**Referência:** leituras manuais recebem `origem = coleta_manual` e passam a alimentar gráficos,
modelo e agente de IA como qualquer outra.

## Acompanhar a planta pelo celular

**Categoria:** operação do sistema
**Sintomas:** necessidade de consultar o estado das máquinas fora do computador.
**Causas prováveis:** técnico em campo, gerente fora da planta.
**Diagnóstico:** os dados estão no MongoDB Atlas, na nuvem, e são os mesmos para todos os usuários.
O acesso pelo celular depende de onde o app está publicado: rodando localmente, ele responde apenas
no computador que o executa; publicado em servidor, responde de qualquer lugar.
**Ação recomendada:** para uso em campo, publicar o app em um servidor acessível pela rede ou pela
internet. A interface já é responsiva.
**Referência:** gerente e técnicos podem usar simultaneamente, em sessões independentes.
