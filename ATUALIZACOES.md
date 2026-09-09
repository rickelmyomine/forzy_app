# Forzy — Registro de atualizações do app

## Versão 3.6 — Inventário, placas QR Code e calibração do alerta
- **Cadastro Técnico com abas renomeadas**: *Novo equipamento* · **Inventário** (antiga Editar/Foto)
  · **Placas QR code** (antiga Galeria) · **Legado** (antiga Dados de exemplo/legados).
- **Inventário → exportação**: botão de **planilha CSV** (abre no Excel) e de **relatório PDF** com
  todos os motores, dados de placa, estado atual pela última leitura e data da última manutenção.
  No PDF, linhas em vermelho/amarelo/verde conforme o estado.
- **Placas QR code**: gera a etiqueta de cada máquina com TAG, dados de placa e QR Code — para
  imprimir e colar no motor. Saída em **folha A4 (PDF)** com marcas de corte, em **ZIP** de imagens
  ou uma a uma. O endereço do app usado no QR é configurável na tela (ou em `APP_URL` no
  `secrets.toml`), e a tela avisa quando ainda está apontando para o localhost.
- **Leitura do QR abre a máquina**: `.../?tag=MOT-007` leva direto à Consulta de Equipamentos já na
  máquina lida, com a mesma TAG pré-selecionada na Visualização 3D e na abertura de OS.
- **Aba Legado**: saíram os dados de exemplo. Agora ela serve para **trazer inventário de outro
  sistema** — importação de planilha CSV/Excel com reconhecimento flexível de colunas, planilha
  modelo para baixar, prévia antes de gravar e opção de não sobrescrever o que já existe. Continua
  disponível a correção de documentos antigos gravados sem TAG.
- **Calibração do alerta automático**: controle de **10 minutos a 1 hora** na aba *Alerta automático*
  para definir quanto tempo de estado crítico contínuo dispara o e-mail ao Gerente de Manutenção.
  O valor fica gravado no banco (coleção `configuracoes`), vale para todos e não exige reiniciar o
  app. Ajuste restrito ao gerente.

## Versão 3.5.1 — Ajustes de visualização
- Retirado o painel *Modelo preditivo* da barra lateral e a faixa *Previsão de falhas (IA)* do topo
  das telas — a previsão continua onde já aparecia: ficha da máquina, Análise de Riscos e Motor 3D.
- **Manutenções → Resumo**: gráficos refeitos em Plotly com **legenda**, rótulos de eixo, valores nas
  barras, meses em formato brasileiro (08/2026) e um texto explicando como ler cada um. A pizza dos
  tipos de manutenção ganhou legenda nomeada.
- **Coleta de Dados → Biblioteca**: botão que gera (ou atualiza) o **dataset dos últimos 5 dias de
  toda a planta**, e filtro por **calendário** (período de geração) ao lado da busca por texto.
- **Motor 3D**: o botão *Analisar com a IA* agora ocupa a largura da tela, com 68 px de altura.

## Versão 3.5 — Datasets, alerta automático e destaque preditivo
- **Comparação com todos os tipos de gráfico**: Linha, Colunas, Barras, Pizza e Radar, iguais aos de
  Dados Brutos, tanto na comparação de 2 máquinas quanto na de 2 ou mais em Consulta.
  A pizza agora mostra uma rosca por máquina (Normal / Alerta / Crítico).
- **Gerar dataset (CSV)** no fim das telas de Dados Brutos, Consulta de Equipamentos e Comparação.
  O nome do arquivo começa por **ano-mês-dia** (ex.: `2026-09-08_telemetria_MOT-007.csv`).
- **Biblioteca de datasets** (Coleta de Dados → 📚 Biblioteca): todos os arquivos já gerados ficam
  guardados no MongoDB, com **pesquisa** por nome, máquina, tela de origem ou autor, prévia das
  primeiras linhas, download e exclusão. Nova coleção `datasets`.
- **Alerta automático para o Gerente de Manutenção**: se a máquina ficar em estado crítico por
  **30 minutos seguidos** (medido pelo horário das leituras), o relatório de falha sai sozinho por
  e-mail e WhatsApp para quem tem cargo de gerente. O mesmo episódio nunca é enviado duas vezes.
  Nova aba *🚨 Alerta automático* mostra, em tempo real, há quantos minutos cada máquina está
  crítica e quanto falta para disparar; o envio manual continua igual. Limite configurável em
  `ALERTA_MINUTOS_CRITICOS` e desligável em `ALERTA_AUTOMATICO`. A verificação roda a cada 5 min com
  o app aberto e continuamente pelo `monitor_alertas.bat`.
- **Motor 3D**: o diagnóstico saiu da linha de texto e virou um **quadro próprio, grande**, com o
  estado em destaque, o que está causando e a previsão de manutenção. Botão *Analisar com a IA*
  ampliado.
- **Modelo preditivo em destaque**: painel *🔮 Modelo preditivo* na barra lateral (máquinas por nível
  de risco, acurácia do modelo e atalho para as de risco alto) e faixa *Previsão de falhas (IA)* no
  topo de Dados Brutos, Consulta e Análise de Riscos.

## Versão 3.4.1 — Documentação
- Nova documentação na pasta `conhecimento/`, também indexada pelo **Chat IA** (o agente passa a
  citá-la como fonte): `RELATORIO_OPERACIONAL.md`, `REQUISITOS.md`, `GLOSSARIO.md` e
  `CORPUS_ESTRUTURADO.md`.
- `Readme.md` reescrito: escopo, telas, perfis, faixas de referência, estrutura de pastas,
  tecnologia e alertas.
- **Segurança**: usuário e senha do MongoDB e a senha de app do Gmail saíram de dentro dos arquivos
  `.bat` — agora são lidos de `.streamlit/secrets.toml`. O monitor de alertas descobre sozinho os
  destinatários a partir dos funcionários cadastrados.
- Pasta separada pronta para publicar no GitHub, sem credenciais, com a documentação também em `docs/`.

## Versão 3.4
- **MOT-021 removido de tudo**: a análise passa a ter exatamente **20 máquinas** (MOT-001 a MOT-020).
  Na abertura o app apaga automaticamente qualquer máquina fora dessa faixa do cadastro, da
  telemetria, das manutenções, das previsões, dos alertas e das notificações
  (`remover_maquinas_fora_do_escopo`, também disponível em `scripts/limpar_maquinas.py`).
- **Dados Brutos → aba "⚖️ Comparar"**: compara **2 máquinas** no mesmo dia/horário — Máquina A,
  Máquina B e o tipo de visualização (linhas sobrepostas, barras do máximo/média ou radar), com
  tabela de média/máximo/mínimo das 4 variáveis, contagem de leituras em falha e uma frase dizendo
  qual está mais quente, qual vibra mais, etc.
- **Consulta de Equipamentos → aba "⚖️ Comparar máquinas"**: compara **2 ou mais máquinas** no
  período escolhido — fichas lado a lado (foto, dados e previsão do modelo), tabela comparativa,
  gráficos e o botão *Pedir à IA para comparar estas máquinas*.
- **Desempenho (app bem mais rápido)**:
  - as abas passaram a ser **preguiçosas**: só a aba aberta é calculada (antes o Streamlit executava
    o conteúdo de *todas* as abas a cada clique);
  - a **Consulta** deixou de carregar as 20 fotos (base64) a cada recarregamento — a foto vem só da
    máquina aberta;
  - os **rankings de falhas** (dia/semana/mês/ano) saíram de 4 consultas, a maior varrendo um ano,
    para **uma única agregação** por máquina e por dia;
  - as agregações de última leitura usam uma **janela de 2 dias**; os gráficos de linha fazem
    **downsampling** para 500 pontos; novo índice por `FalhaCodigo`;
  - logo após o login o app **aquece os dados em segundo plano**, então as telas pesadas já abrem
    prontas.

  Tempos medidos (mesma máquina, cache frio antes / regime normal depois):
  Dados Brutos 32 s → **1,1 s**; Consulta de Equipamentos 19,6 s → **4,4 s**;
  Análise de Riscos 17,8 s → **1,4 s**; Coleta de Dados 7,7 s → **1,1 s**;
  demais telas ≈ 1 s.

## Versão 3.3
- **Coleta de Dados** (novo item no menu): importação de leituras por arquivo CSV/Excel (com modelo
  para baixar), registro manual de leitura pontual, tela de coleta por **Bluetooth/IoT** (prevista,
  ainda não implementada) e resumo do dataset acumulado por origem, com download.
- **Login**: saiu o plantão; entrou o campo **Telefone (DDD)** de quem acessa; a aba *Perfis de
  acesso* já abre expandida.
- **Barra lateral**: painel **Conexões do sistema** abaixo do MongoDB — MongoDB Atlas, IA Gemini,
  E-mail (Gmail) e WhatsApp, cada um com bolinha verde/amarela/cinza; logo da Second Corporation
  deslocada para baixo da barra de download.
- **Alertas**: só disparam em estado **crítico sustentado** (3 leituras seguidas, ~30 min) — picos
  isolados não geram alerta; a mensagem informa a duração. Telefone padrão passou a `(DD) 123456789`
  e o cadastro de funcionários valida DDD + número.
- **Chat IA**: "cardápio" virou **Dúvidas frequentes**, agora com **55 perguntas** (eram 20) e campo
  de busca — todas respondidas na hora com os dados do sistema.

## Versão 3.2 — Funcionários, alertas e identidade Second Corporation
- **Cadastro de Funcionários** (novo item abaixo de Manutenções, cadastro só pelo gerente):
  nome, cargo, e-mail, telefone e planta; marcação de quem recebe alertas. Coleção `funcionarios`.
- **Alertas**: aba *Enviar alerta* monta o RELATÓRIO DE FALHA DO MOTOR no formato padrão e envia
  por e-mail (Gmail) e WhatsApp (Twilio quando configurado, ou link wa.me de 1 clique) para os
  cadastrados; aba *Histórico* (coleção `notificacoes`) e aba *Como funciona*.
- **Manutenção registrada** avisa o gerente automaticamente por e-mail e WhatsApp.
- **Tela de login**: logo da Second Corporation (a da Forzy saiu) e telefone de plantão
  (`ALERTA_TELEFONE` no secrets.toml).
- **Vídeo de apresentação** em tela cheia (ocupa toda a janela; botão "⛶ Tela cheia" para o
  fullscreen do navegador).
- **Menu**: espaços reduzidos, fontes maiores na navegação e nos seletores, logo do grupo visível.

## Versão 3.1
- Menu "Análise de Frota" renomeado para **Análise de Riscos (IA)**.
- Dados Brutos: seletor **Máquina** (uma máquina ou todas) ao lado do dia/horário; o grupo de
  máquinas ficou em um expansor opcional (resolve o "No results" do multiselect).
- Barra lateral: logo da **Second Corporation** abaixo da barra de carregamento.
- Vídeo de apresentação da Second Corporation (10 s, com botão Pular) logo após o login; a
  preparação dos dados já começa em segundo plano durante o vídeo.

## Versão 3 — Dashboards completos, análise de frota e chat com cardápio

- **Barra lateral**: barra verde de carregamento (0–100 %) abaixo do status do MongoDB, com
  "✅ Atualização concluída" ao terminar. Preparação roda em segundo plano.
- **Análise de Riscos (IA)** (novo item abaixo de Consulta): ranking de máquinas por manutenções,
  leituras críticas e alertas; pontuação de saúde; recomendação manter / revisar-atualizar /
  substituir (compra de nova) com link para o site do fabricante; botão que leva a análise à IA.
- **Dados Brutos**: seletor de tipo de gráfico (linha, colunas, barras, pizza, radar); texto
  explicativo abaixo de cada gráfico/tabela com a faixa ideal (manual técnico + histórico);
  linhas em amarelo (alerta) e vermelho (crítico) em todas as tabelas; atalho "Ver só as
  críticas"; aba Falhas com seleção de motor, verde para operação normal, mais gráficos
  (proporção, falhas por horário) e ranking da máquina com mais falhas no dia/semana/mês/ano.
- **Consulta de Equipamentos**: tipos de gráfico, textos explicativos, tabelas coloridas,
  prognóstico de data de manutenção e 2 manutenções de exemplo por máquina.
- **Visualização 3D**: motivo do alerta/crítico (quais variáveis e quanto fora da faixa) e data
  prevista de manutenção se continuar operando assim (tendência + modelo).
- **Chat IA**: cardápio de 20 perguntas prontas respondidas na hora só com os dados; perguntas
  livres varrem todo o sistema e a internet (Google Search) citando fontes; textos sem
  referências a trabalho acadêmico.
- Gerador de telemetria recalibrado (~8–10 % do tempo em falha, distribuído ao longo do dia).

## Fase 2 — Dashboards, previsão e Chat IA com os dados da planta

### Preparação automática
Na primeira execução (após o login) o app grava sozinho no MongoDB, **em segundo plano**, o cadastro das
20 máquinas, confere o modelo e gera a telemetria dos últimos 30 dias do dia mais recente para trás
(10 min nos últimos 3 dias, 30 min nos demais — ~35 mil leituras). A barra lateral mostra o progresso e
o app pode ser usado enquanto isso (`features/preparacao.py`). Basta `python -m streamlit run app.py`.

### Telas
- **Dados Brutos (Telemetria)** — agora é a tela principal (primeiro item do menu e tela inicial após o login).
  Filtros: dia, faixa de horário 00:00–23:59, máquinas (todas as 20 por padrão) e variável.
  Abas: *Telemetria* (4 gráficos unificados — Temperatura, Vibração, Corrente, Rotação — ou 1 variável
  com resumo por máquina e gráfico individual), *Falhas* (só aparece conteúdo se houver falhas no período:
  contadores por tipo, linha do tempo dia/horário por máquina, barras por máquina, tabela de episódios)
  e *Tabela* (dados brutos + download CSV).
- **Consulta de Equipamentos** — visão geral (status atual, previsão e risco de cada máquina) e ficha
  completa: foto, folha de dados simplificada, documentos (PDF do fabricante, site, manual), previsão
  de manutenção do modelo com recomendação e tendência, telemetria individual com dia/horário e
  últimas manutenções. Botão "Analisar esta máquina com a IA".
- **Cadastro Técnico** — simplificado: Fabricante, Modelo, Potência, Tensão, Corrente, RPM, Nº de série,
  Observações (para o técnico), Planta, Criticidade, Ano, site/manual e PDF da folha de dados.
  O OCR continua lendo a placa; dados extras (carcaça, IP, isolação, FS, peso…) vão para Observações.
  Gerente: aba "Dados de exemplo / legados" grava as 20 máquinas prontas (MOT-001/002/003 com as fotos
  e dados reais das placas; motores WEG com o PDF WEG W22).
- **Manutenções** — sem título e sem custo. Histórico por máquina cadastrada. Resumo separado por mês,
  com filtro de ano. Botão de análise com a IA.
- **Visualização 3D** — botão de análise com a IA.
- **Chat IA** — respostas baseadas nos dados do MongoDB (cadastro, estado atual, resumo de 24 h e 7 dias
  por máquina, falhas por tipo, previsões, manutenções) e na documentação do projeto (RAG: guia de
  telemetria/falhas, manual técnico + folha WEG, corpus da Sprint 3, QA20), com fontes citadas.
  Seletor "Foco da análise" (toda a planta ou uma máquina) e sugestões de perguntas.
- **Barra lateral** — "Gestão da Planta", usuário logado, menu com Dados Brutos primeiro, filtro de
  Planta (sem Área), status do Mongo.

### Dados e modelo
- `features/limites.py` — faixas Normal/Alerta/Crítico por variável (coerentes com o dataset; a versão
  antiga marcava temperatura ≥ 60 °C como alerta, o que classificava quase tudo como alerta).
- `scripts/gerar_dataset_30dias.py` — telemetria dos últimos 30 dias, 20 máquinas, a cada 10 min
  (~86 mil leituras) com episódios de falha realistas. Marca `origem="sintetico_30d"`; pode ser
  regenerado sem apagar as leituras do CSV.
- `scripts/treinar_modelo.py` + `modelos/modelo_falhas.joblib` — classificador de falhas (pipeline da
  Sprint 2: janela móvel de 5 leituras, divisão cronológica; HistGradientBoosting do scikit-learn).
  Acurácia 98 % / F1-macro 0,92 em teste. Previsões salvas na coleção `previsoes`.
- `scripts/popular_cadastro.py` — cadastro pré-pronto das 20 máquinas (também pelo app).
- `conhecimento/` — documentos usados pelo Chat IA.

### Coleções no MongoDB (`forzy_iot_db`)
| Coleção | Situação | Uso |
|---|---|---|
| cadastro_equipamentos | existente | + campos da placa, foto, PDF, site/manual, criticidade |
| telemetria_historico | existente | + leituras dos últimos 30 dias (`origem="sintetico_30d"`) |
| tipos_falha, alertas_enviados | existentes | sem mudança |
| manutencoes | Fase 1 | ordens de serviço com fotos e telemetria do momento |
| previsoes | **nova** | última previsão do modelo por máquina |

### Logins (app de teste — senha 1234 para todos)
| Usuário | Senha | Perfil |
|---|---|---|
| gerente | 1234 | gerente |
| tecnico1 | 1234 | tecnico |
| tecnico2 | 1234 | tecnico |

## Fase 1 — Login, cadastro com foto e manutenções
- Login por perfil (`auth/auth.py`), usuários no `secrets.toml`.
- Cadastro com foto (base64 no Mongo) e OCR da placa com Gemini (`features/placa_ocr.py`).
- Manutenções com fotos antes/durante/depois, telemetria capturada no registro e classificação do
  evento nas 5 categorias da Sprint 3 (`features/classificador_texto.py`).
- Migração dos 20 motores do Motor.xlsx sem TAG (`scripts/migrar_cadastro.py`).
