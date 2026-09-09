# Requisitos do Sistema

Sistema de monitoramento on-line e manutenção preditiva de motores elétricos industriais.

**Legenda de status:** ✅ implementado e em operação · 🟡 implementado com dependência externa ·
🚧 previsto, não implementado

---

## 1. Objetivo

Acompanhar continuamente o estado de 20 motores elétricos, identificar a formação de falhas antes da
quebra, priorizar as intervenções e apoiar a decisão de manter, revisar ou substituir cada ativo.

O sistema deve funcionar **on-line**, com dados compartilhados entre plantas e usuários, e aceitar
telemetria tanto de histórico e arquivos quanto de **coleta feita pessoalmente na máquina**.

---

## 2. Requisitos funcionais

### 2.1 Acesso e usuários

| ID | Requisito | Status |
|---|---|---|
| RF-01 | Acesso protegido por usuário e senha | ✅ |
| RF-02 | Três perfis: Gerente de Manutenção e dois Técnicos | ✅ |
| RF-03 | O gerente tem acesso total; o técnico registra manutenções, fotos e cadastros | ✅ |
| RF-04 | Somente o gerente cadastra, edita e exclui funcionários | ✅ |
| RF-05 | Registro do telefone (com DDD) do usuário no login | ✅ |
| RF-06 | Uso simultâneo por vários usuários, em sessões independentes, sobre o mesmo banco | ✅ |
| RF-07 | Vídeo institucional de apresentação após o login, em tela cheia, com opção de pular | ✅ |

### 2.2 Telemetria e dashboards

| ID | Requisito | Status |
|---|---|---|
| RF-10 | Leitura das 4 variáveis: temperatura, vibração, corrente e rotação | ✅ |
| RF-11 | Seleção do dia e da faixa de horário dentro dos 30 dias disponíveis | ✅ |
| RF-12 | Seleção de uma máquina individual ou de um grupo | ✅ |
| RF-13 | Tipos de gráfico: linha, colunas, barras, pizza e radar | ✅ |
| RF-14 | Texto explicativo sob cada gráfico e tabela, com a faixa ideal conforme manual técnico | ✅ |
| RF-15 | Tabela com linhas em amarelo (alerta) e vermelho (crítico) | ✅ |
| RF-16 | Painel dos 4 estados de falha, com verde para operação normal | ✅ |
| RF-17 | Seleção de motor individual no painel de falhas | ✅ |
| RF-18 | Ranking da máquina com mais falhas por dia, semana, mês e ano | ✅ |
| RF-19 | Atalho de filtro para exibir apenas as máquinas críticas | ✅ |
| RF-20 | Barra de progresso verde do carregamento dos dados, até "Atualização concluída" | ✅ |
| RF-21 | **Comparação de 2 máquinas** em Dados Brutos, com gráficos e tabela lado a lado | ✅ |

### 2.3 Cadastro e consulta de equipamentos

| ID | Requisito | Status |
|---|---|---|
| RF-30 | Cadastro do motor com foto e dados de placa | ✅ |
| RF-31 | Leitura automática da placa por OCR a partir da foto | 🟡 exige chave Gemini |
| RF-32 | Ficha completa: dados técnicos, foto, folha de dados e links do fabricante | ✅ |
| RF-33 | Visão geral da planta com estado atual e previsão de cada máquina | ✅ |
| RF-34 | Pré-cadastro das 20 máquinas, com fotos reais dos três motores de referência | ✅ |
| RF-35 | **Comparação de 2 ou mais máquinas** em Consulta de Equipamentos | ✅ |
| RF-36 | Visualização 3D indicando a causa do alerta e a data prevista de manutenção | ✅ |
| RF-37 | Escopo restrito a 20 máquinas (MOT-001 a MOT-020), com limpeza automática de itens fora da faixa | ✅ |

### 2.4 Manutenção

| ID | Requisito | Status |
|---|---|---|
| RF-40 | Registro de OS pelo técnico, com fotos e a telemetria do momento | ✅ |
| RF-41 | OS sem campo de título e sem custo estimado | ✅ |
| RF-42 | Histórico de manutenções por máquina | ✅ |
| RF-43 | Resumo mensal e anual das manutenções | ✅ |
| RF-44 | Visualização on-line pelo gerente assim que o técnico registra | ✅ |
| RF-45 | Aviso ao gerente por e-mail e WhatsApp ao registrar uma OS | 🟡 exige Gmail/Twilio |

### 2.5 Análise de riscos

| ID | Requisito | Status |
|---|---|---|
| RF-50 | Identificação das máquinas com mais manutenções e mais leituras críticas | ✅ |
| RF-51 | Pontuação de saúde por máquina | ✅ |
| RF-52 | Recomendação de manter, revisar/atualizar ou substituir | ✅ |
| RF-53 | Sugestão de consultar o site do fabricante para reposição ou upgrade | ✅ |
| RF-54 | Previsão da data da próxima manutenção por tendência | ✅ |

### 2.6 Coleta de dados

| ID | Requisito | Status |
|---|---|---|
| RF-60 | Importação de leituras por arquivo CSV ou Excel, com reconhecimento flexível de colunas | ✅ |
| RF-61 | **Registro manual** de leitura pontual medida em campo | ✅ |
| RF-62 | Coleta automática por Bluetooth ou sensor IoT | 🚧 tela pronta, integração pendente |
| RF-63 | Registro da origem de cada leitura (histórico, arquivo, manual, Bluetooth) | ✅ |
| RF-64 | Resumo do dataset acumulado por origem, com download | ✅ |

### 2.7 Alertas

| ID | Requisito | Status |
|---|---|---|
| RF-70 | Alerta apenas em estado crítico sustentado (3 leituras consecutivas) | ✅ |
| RF-71 | Envio por e-mail para os funcionários cadastrados | 🟡 exige Gmail |
| RF-72 | Envio por WhatsApp automático | 🟡 exige Twilio; sem ele, link de 1 clique | 
| RF-73 | Mensagem no formato "RELATÓRIO DE FALHA DO MOTOR" definido pela operação | ✅ |
| RF-74 | Envio manual de alerta pela tela, com edição do texto | ✅ |
| RF-75 | Histórico dos alertas enviados | ✅ |
| RF-76 | Monitoramento contínuo em segundo plano, 24 h | ✅ script `monitor_alertas.bat` |

### 2.8 Agente de IA

| ID | Requisito | Status |
|---|---|---|
| RF-80 | 50 ou mais dúvidas frequentes com resposta imediata | ✅ 55 perguntas |
| RF-81 | Respostas das dúvidas frequentes calculadas dos dados, sem IA externa | ✅ |
| RF-82 | Campo de busca entre as perguntas | ✅ |
| RF-83 | **Perguntas livres** respondidas com varredura de todo o sistema | 🟡 exige chave Gemini |
| RF-84 | Busca na internet para o que não está nos dados, com citação das fontes | 🟡 exige chave Gemini |
| RF-85 | Botão "Perguntar à IA" em todas as telas, levando ao chat com a máquina em foco | ✅ |
| RF-86 | Escolha do modelo de IA e do foco da análise | ✅ |

---

## 3. Requisitos não funcionais

| ID | Requisito | Meta | Situação |
|---|---|---|---|
| RNF-01 | Tempo de abertura das telas | até 5 s | ✅ 1,1 a 4,5 s medidos |
| RNF-02 | Dados compartilhados entre usuários e plantas | banco na nuvem | ✅ MongoDB Atlas |
| RNF-03 | Interface em português | — | ✅ |
| RNF-04 | Interface legível em celular | responsiva | ✅ |
| RNF-05 | Nenhuma referência a trabalho acadêmico nos textos | — | ✅ |
| RNF-06 | Identidade visual Second Corporation no login e no menu | — | ✅ |
| RNF-07 | Fontes ampliadas na navegação e nos seletores | — | ✅ |
| RNF-08 | Painel de status das conexões (banco, IA, e-mail, WhatsApp) | — | ✅ |
| RNF-09 | Credenciais fora do código, em arquivo não versionado | — | ✅ `.streamlit/secrets.toml` |
| RNF-10 | Preparação dos dados sem travar a interface | segundo plano | ✅ |
| RNF-11 | Instalação e execução em um clique no Windows | — | ✅ `INICIAR.bat` |
| RNF-12 | Operação sem internet para demonstração | banco em memória | ✅ `FORZY_USE_MOCK_DB=1` |

### Desempenho medido

| Tela | Antes | Depois |
|---|---|---|
| Dados Brutos | 32,0 s | 1,1 s |
| Consulta de Equipamentos | 19,6 s | 4,4 s |
| Análise de Riscos | 17,8 s | 1,4 s |
| Coleta de Dados | 7,7 s | 1,1 s |
| Demais telas | — | ~1 s |

Técnicas aplicadas: cálculo apenas da aba visível, carregamento das fotos sob demanda, agregações no
banco em vez de laços no app, índices por TAG/data/falha, redução de pontos nos gráficos e
pré-aquecimento dos dados em segundo plano.

---

## 4. Requisitos de dados

| ID | Requisito | Status |
|---|---|---|
| RD-01 | 20 motores, MOT-001 a MOT-020 | ✅ |
| RD-02 | 30 dias de histórico | ✅ |
| RD-03 | Amostragem de 10 min nos 3 dias recentes e 30 min nos demais | ✅ |
| RD-04 | 4 estados: normal, desbalanceamento, superaquecimento, falha mecânica | ✅ |
| RD-05 | Faixas de referência conforme manual técnico, exibidas ao usuário | ✅ |
| RD-06 | Coleções separadas por domínio no MongoDB | ✅ |
| RD-07 | Índices para consulta rápida | ✅ TAG+data, data, origem, falha |

### Coleções

| Coleção | Conteúdo |
|---|---|
| `cadastro_equipamentos` | Ficha técnica, foto e documentos de cada motor |
| `telemetria_historico` | Todas as leituras, com origem e estado |
| `manutencoes` | Ordens de serviço registradas |
| `previsoes` | Saída do modelo por máquina |
| `funcionarios` | Quem recebe alertas |
| `notificacoes` | Alertas enviados |
| `alertas_enviados` | Controle de repetição do monitor |
| `tipos_falha` | Descrição dos 4 estados |

---

## 5. Requisitos do modelo preditivo

| ID | Requisito | Meta | Resultado |
|---|---|---|---|
| RM-01 | Classificar os 4 estados de falha | — | ✅ |
| RM-02 | Acurácia mínima | 90 % | ✅ 97,97 % |
| RM-03 | F1-macro mínimo | 0,80 | ✅ 0,916 |
| RM-04 | Recall alto nas falhas | priorizar detecção | ✅ recall macro 0,952 |
| RM-05 | Considerar tendência, não só valor instantâneo | janela móvel | ✅ janela de 5 leituras |
| RM-06 | Divisão treino/teste sem vazamento temporal | cronológica por motor | ✅ 80/20 |
| RM-07 | Tratamento de classes desbalanceadas | — | ✅ pesos por classe |
| RM-08 | Retreino reproduzível por script | — | ✅ `scripts/treinar_modelo.py` |

**Configuração:** `HistGradientBoostingClassifier` (scikit-learn), 12 features (4 valores
instantâneos + média móvel e desvio-padrão móvel de cada um, janela 5), 24.000 amostras de treino e
6.000 de teste.

---

## 6. Requisitos de segurança

| ID | Requisito | Status |
|---|---|---|
| RS-01 | Autenticação obrigatória em todas as telas | ✅ |
| RS-02 | Restrição de ações por perfil | ✅ |
| RS-03 | Credenciais fora do código-fonte | ✅ |
| RS-04 | `secrets.toml` no `.gitignore` | ✅ |
| RS-05 | Rastreabilidade: autor e data em cadastros, OS e alertas | ✅ |
| RS-06 | Acesso ao banco restrito por lista de IPs no Atlas | ⚠️ atualmente aberto (0.0.0.0/0) para os testes — restringir em produção |

---

## 7. Pendências e evolução

| Item | Descrição |
|---|---|
| Coleta Bluetooth/IoT | Integrar coletor BLE (`bleak`) ou gateway MQTT (`paho-mqtt`) |
| Publicação em servidor | Necessária para acesso pelo celular em campo |
| Restrição de IP no Atlas | Trocar 0.0.0.0/0 pelos IPs da operação |
| Rotação de credenciais | Trocar senha do Atlas e a senha de app do Gmail após os testes |
| Retreino periódico | Reexecutar o treino a cada mês de dados novos |
| Relatório em PDF | Exportação do relatório operacional direto do app |
