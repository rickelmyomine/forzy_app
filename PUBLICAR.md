# Publicar o sistema no Streamlit Community Cloud

Depois de publicado, o app ganha um endereço fixo (`https://algo.streamlit.app`) que abre no celular
de qualquer lugar — e é esse endereço que vai dentro dos QR Codes das máquinas.

---

## Antes de começar

**Troque a senha do MongoDB.** A senha atual já circulou por arquivos e conversas, e você vai colá-la
dentro do Streamlit Cloud. Melhor que já seja a nova.

Em `cloud.mongodb.com` → **Database Access** → no usuário, **Edit** → **Edit Password** →
**Autogenerate Secure Password** → copie → **Update User**. Depois troque a senha dentro da linha
`MONGODB_URI` do seu `.streamlit/secrets.toml` local e rode o app uma vez para confirmar.

**Confira o acesso de rede do Atlas.** Em **Network Access**, precisa existir a entrada
`0.0.0.0/0` — os servidores do Streamlit Cloud não têm IP fixo. Já está assim.

---

## Passo 1 — Repositório no GitHub

1. Em `github.com`, clique no **+** (canto superior direito) → **New repository**.
2. **Repository name:** `forzy`
3. Marque **Private**.
4. **Não** marque nada em "Initialize this repository".
5. **Create repository**.

## Passo 2 — Subir os arquivos

1. Descompacte o `forzy_github.zip`. O `app.py` tem que ficar na raiz da pasta.
2. Na página do repositório, clique em **uploading an existing file**.
3. Selecione tudo dentro da pasta (`Ctrl+A`) e **arraste** para o navegador. As subpastas sobem junto.
4. Em **Commit changes**, escreva `Forzy 3.6` e confirme.

**Confira antes de commitar:** o arquivo `.streamlit/secrets.toml` **não** pode aparecer na lista.
Só o `secrets.toml.example`. Se aparecer o outro, pare e avise.

## Passo 3 — Criar o app

1. Acesse `share.streamlit.io` → **Continue with GitHub** → autorize.
2. **Create app** → **Deploy a public app from a repository**.
3. Preencha:
   - **Repository:** `seu-usuario/forzy`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** escolha o nome, por exemplo `forzy-second` → o endereço fica
     `https://forzy-second.streamlit.app`

**Anote esse endereço.** É ele que vai nos QR Codes.

## Passo 4 — Credenciais (o passo que não pode falhar)

Ainda nessa tela, abra **Advanced settings**:

- **Python version:** `3.12`
- **Secrets:** abra o seu `.streamlit/secrets.toml` no VS Code, copie o conteúdo **inteiro** e cole
  nesse campo.

Depois de colar, **acrescente ao final** a linha com o endereço que você escolheu:

```toml
APP_URL = "https://forzy-second.streamlit.app"
```

É assim que as credenciais chegam ao app sem passar pelo GitHub. Esse campo é privado.

**Save** → **Deploy**.

## Passo 5 — Esperar e conferir

A primeira publicação leva de 3 a 8 minutos; a tela mostra o log da instalação.

Quando abrir, teste:

- login com `gerente` / `1234` e telefone com DDD;
- a barra verde da lateral chega em "Atualização concluída";
- Dados Brutos mostra os gráficos;
- Chat IA responde uma pergunta livre (aqui você confirma se a chave do Gemini está válida);
- Cadastro Técnico → Inventário gera o PDF.

Se algo falhar, o log fica visível em **Manage app** (canto inferior direito).

## Passo 6 — Imprimir as placas de QR Code

Agora sim, com o endereço definitivo:

1. **Cadastro Técnico → Placas QR code**.
2. No campo do topo, confirme que aparece o endereço `https://...streamlit.app` (e não `localhost`).
   Se você colocou `APP_URL` nos secrets, ele já vem preenchido.
3. **Gerar folha de placas (PDF)** → **Baixar** → imprimir → recortar nas linhas tracejadas.
4. Cole cada etiqueta no motor correspondente.

Teste com o celular antes de imprimir tudo: aponte a câmera para uma placa na tela do computador.
Deve abrir o app já na máquina, pedindo login na primeira vez.

---

## Depois de publicado

**Para atualizar o sistema:** suba os arquivos alterados no GitHub. O Streamlit Cloud republica
sozinho em alguns minutos.

**Para mudar uma credencial:** *Manage app* → **Settings** → **Secrets**. Não precisa mexer no
GitHub.

**O app hiberna** depois de alguns dias sem uso; a primeira visita depois disso demora um pouco mais
e volta ao normal.

**O monitor de alertas 24 h** (`monitor_alertas.bat`) continua rodando no seu computador — ele é um
processo separado do app publicado. O disparo automático dentro do app funciona enquanto alguém
estiver com a tela aberta.

## Se der erro no deploy

| Mensagem no log | O que fazer |
|---|---|
| `ModuleNotFoundError` | Falta a biblioteca no `requirements.txt` |
| `Não foi possível conectar ao MongoDB` | Secrets não colados, senha errada, ou falta `0.0.0.0/0` no Network Access |
| `FileNotFoundError: .streamlit/secrets.toml` | Cole o conteúdo em Advanced settings → Secrets |
| App reinicia sozinho | Memória excedida — reduza o período em Análise de Riscos e reabra |
