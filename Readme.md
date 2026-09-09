# Forzy — Monitoramento e Manutenção Preditiva de Motores Elétricos

Sistema web para **acompanhamento on-line** de motores elétricos industriais, com dashboards
atualizados, detecção de estados de falha, previsão de manutenção e um agente de IA que responde
sobre os dados da própria planta.

Os dados ficam no **MongoDB Atlas** (nuvem), então qualquer pessoa autorizada — em qualquer planta,
no computador ou no celular — enxerga a mesma informação, atualizada. A telemetria pode chegar de
três formas: histórico já gravado no banco, **importação de arquivo** (CSV/Excel) e **registro
manual** de leitura feita em campo com instrumento portátil. A coleta automática por
**Bluetooth/IoT** está prevista e tem a tela pronta, mas ainda não está implementada.

O **modelo preditivo é o coração do sistema**: um classificador treinado com a telemetria da planta
aponta, a cada leitura, o modo de falha em formação e o nível de risco de cada motor — antes de a
variável cruzar o limite. O resultado aparece na barra lateral, no topo das telas principais, na
ficha de cada máquina, na Análise de Riscos e na Visualização 3D.

Versão atual: **3.6** — veja `ATUALIZACOES.md` para o histórico completo.

---

## O que o sistema faz

| Tela | Para que serve |
|---|---|
| **Dados Brutos (Telemetria)** | Leituras de temperatura, vibração, corrente e rotação por dia e horário; gráficos (linha, colunas, barras, pizza, radar); painel de falhas; **comparação de 2 máquinas**; tabela com linhas amarelas (alerta) e vermelhas (crítico) |
| **Consulta de Equipamentos** | Visão geral da planta, ficha completa de cada motor (foto, placa, documentos), previsão do modelo e **comparação de 2 ou mais máquinas** |
| **Análise de Riscos (IA)** | Ranking das máquinas que mais dão trabalho, pontuação de saúde e recomendação de manter, revisar/atualizar ou substituir, com sugestão de consultar o fabricante |
| **Cadastro Técnico** | Novo equipamento (com OCR da placa), **Inventário** com exportação em CSV e PDF, **Placas QR code** para imprimir e colar nos motores, e **Legado** para importar o inventário de outro sistema |
| **Manutenções** | Registro de OS pelos técnicos, com fotos e a telemetria do momento; histórico e resumo mensal/anual |
| **Cadastro de Funcionários** | Quem recebe alertas (nome, cargo, e-mail, telefone, planta) — cadastro exclusivo do gerente; envio manual de alerta e histórico |
| **Coleta de Dados** | Importação por arquivo, registro manual de leitura, tela de Bluetooth/IoT (prevista) e resumo do dataset |
| **Visualização 3D** | Motor em 3D indicando por que está em alerta/crítico e a data prevista da próxima manutenção |
| **Chat IA (Análise)** | 55 dúvidas frequentes respondidas na hora com os dados, e perguntas livres respondidas pelo Gemini com varredura do sistema + busca na internet |

Em Dados Brutos, Consulta de Equipamentos e Comparação há um botão **Gerar dataset (CSV)** no fim da
página; o arquivo é nomeado por ano-mês-dia e fica guardado em **Coleta de Dados → Biblioteca**,
com pesquisa e download.

## Perfis de acesso

| Perfil | Usuário | Senha | Pode |
|---|---|---|---|
| Gerente de Manutenção | `gerente` | 1234 | tudo, inclusive cadastrar funcionários e excluir registros |
| Técnico de Manutenção | `tecnico1` | 1234 | registrar manutenções e fotos, cadastrar equipamentos, ver dashboards |
| Técnico de Manutenção | `tecnico2` | 1234 | idem |

Na tela de login também é informado o telefone (com DDD) de quem está entrando.
Gerente e técnicos podem usar o sistema **ao mesmo tempo**, cada um na sua sessão: o banco é o
mesmo, então a OS que o técnico registra aparece para o gerente assim que ele atualiza a tela.

## Escopo monitorado

- **20 motores** — `MOT-001` a `MOT-020`
- Duas plantas: **Planta Matriz – SP** (MOT-001 a MOT-010) e **Planta Filial – MG** (MOT-011 a MOT-020)
- **30 dias** de telemetria (leitura a cada 10 min nos 3 dias mais recentes, a cada 30 min nos demais)
- 4 variáveis: Temperatura (°C), Vibração (mm/s), Corrente (A), Rotação (RPM)
- 4 estados: Normal, Desbalanceamento, Superaquecimento, Falha mecânica

## Faixas de referência (conforme manual técnico)

| Variável | Normal | Alerta | Crítico |
|---|---|---|---|
| Temperatura | 50–80 °C | até 88 °C | acima de 88 °C |
| Vibração | 0–4,5 mm/s | até 6,0 mm/s | acima de 6,0 mm/s |
| Corrente | 9–15 A | 8–17 A | fora dessa faixa |
| Rotação | 1680–1880 RPM | 1600–1950 RPM | fora dessa faixa |

---

## Como rodar

Instruções completas em **`COMO_RODAR.md`**. Resumo:

1. Descompacte o projeto (o `app.py` tem que ficar na raiz da pasta).
2. Duplo clique em **`INICIAR.bat`** (Windows) — cria o ambiente, instala tudo e abre o navegador.

Manualmente:

```powershell
cd caminho\da\pasta
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

O app abre em `http://localhost:8501`.

### Configuração (`.streamlit/secrets.toml`)

```toml
MONGODB_URI      = "mongodb+srv://usuario:senha@cluster.mongodb.net/..."
MONGODB_DB_NAME  = "forzy_challenge"
GEMINI_API_KEY   = "sua-chave"
GMAIL_USER       = "conta@gmail.com"
GMAIL_APP_PASSWORD = "senha-de-app"
ALERTA_TELEFONE  = "(DD) 123456789"
```

Use `.streamlit/secrets.toml.example` como modelo. **Esse arquivo tem credenciais reais e não deve
ir para o GitHub** — ele já está no `.gitignore`.

Para testar sem Atlas, use o banco em memória: `$env:FORZY_USE_MOCK_DB=1` antes do `streamlit run`.

---

## Estrutura das pastas

```
app.py                  ponto de entrada (login → vídeo → menu → telas)
INICIAR.bat             instala e abre o sistema
requirements.txt

auth/                   login e perfis de acesso
ui/                     uma tela por arquivo (view_*.py) + barra lateral e navegação
features/               regras de negócio: limites, gráficos, comparação, alertas,
                        previsão, prognóstico, análise de riscos, RAG do chat,
                        preparação automática dos dados
providers/              acesso ao MongoDB (repositórios) e banco em memória para testes
modelos/                modelo de classificação de falhas treinado (.joblib + metadados)
conhecimento/           base de conhecimento do Chat IA e documentação do sistema
scripts/                treino do modelo, geração de dataset, limpeza, monitor de alertas
assets/                 logos e vídeo de apresentação
```

## Documentação

Na pasta **`conhecimento/`** (também usada pelo Chat IA como fonte de consulta):

| Documento | Conteúdo |
|---|---|
| `RELATORIO_OPERACIONAL.md` | Estado da planta, indicadores, máquinas críticas e ações recomendadas |
| `REQUISITOS.md` | Requisitos funcionais, não funcionais e de dados, com status de cada um |
| `GLOSSARIO.md` | Termos técnicos, de manutenção e do sistema |
| `CORPUS_ESTRUTURADO.md` | Corpus de perguntas e respostas que alimenta o agente de IA |
| `guia_motores_planta.md` | Limiares, estados de falha e plano de manutenção |
| `manual_tecnico.md` | Manual do sistema de monitoramento e folha de dados dos motores |

---

## Tecnologia

- **Streamlit** — interface web
- **MongoDB Atlas** (`pymongo`) — banco na nuvem; coleções `cadastro_equipamentos`,
  `telemetria_historico`, `manutencoes`, `previsoes`, `funcionarios`, `notificacoes`,
  `alertas_enviados`, `tipos_falha`, `datasets`, `configuracoes`
- **scikit-learn** — `HistGradientBoostingClassifier` para classificação dos estados de falha
  (acurácia 97,97 %, F1-macro 0,916)
- **Plotly** — gráficos interativos
- **Google Gemini** (`google-genai`) — agente de IA, com busca na internet (Google Search grounding)
  e OCR da placa do motor
- **Gmail SMTP / Twilio WhatsApp** — envio de alertas
- **reportlab / qrcode / Pillow** — relatório PDF do inventário e placas de QR Code

## Placas QR Code

Cada máquina tem uma etiqueta com TAG, dados de placa e QR Code, gerada em *Cadastro Técnico →
Placas QR code* (folha A4 em PDF, ZIP de imagens ou uma a uma). Ao ler o QR, o app abre em
`.../?tag=MOT-007`, direto na máquina.

O endereço gravado no QR vem do campo da própria tela ou de `APP_URL` no `secrets.toml`. Enquanto o
app roda apenas no computador local o endereço é `localhost` e o QR só funciona ali — **publique o
sistema primeiro e só então imprima as etiquetas**.

## Alertas

Disparam apenas em **estado crítico sustentado**. Há duas formas, que convivem:

- **Automática:** quando a máquina fica em estado crítico por **30 minutos seguidos**, o relatório de
  falha sai sozinho para quem tem cargo de gerente. O mesmo episódio nunca é enviado duas vezes.
  O limite é configurável (`ALERTA_MINUTOS_CRITICOS`) e pode ser desligado (`ALERTA_AUTOMATICO = 0`).
- **Manual:** em *Cadastro de Funcionários → Enviar alerta*, com o texto editável antes do envio.

Picos isolados não geram alerta. As mensagens vão por e-mail e WhatsApp para os funcionários
cadastrados que marcaram "receber alertas", no formato:

```
🔧 *RELATÓRIO DE FALHA DO MOTOR*
*Motor:* MOT-001
*Descrição:* Estado crítico — Superaquecimento detectado por telemetria.
*Temperatura:* 92.5°C
*Vibração:* 4.8 mm/s
*Corrente:* 22.3A
*Ação Recomendada:* Inspeção e manutenção imediatas.
```

O monitoramento contínuo (24 h) roda em outro terminal: `monitor_alertas.bat`.
