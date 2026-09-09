# Como rodar o Forzy

## Jeito fácil (recomendado)

1. Descompacte o `forzy_app.zip`. Você vai ter uma pasta com o `app.py` **dentro dela** —
   confira: abrindo a pasta, você tem que ver `app.py`, `INICIAR.bat`, `requirements.txt`,
   `ui`, `features`, `providers`. Se aparecer **outra pasta** em vez desses arquivos,
   entre nela: é ali que o projeto está.
2. Dê **duplo clique em `INICIAR.bat`**.
3. Espere. Na primeira vez ele cria o ambiente e instala as bibliotecas (2–4 minutos).
   Não feche a janela preta.
4. O navegador abre sozinho em `http://localhost:8501`.

Para encerrar, feche a janela preta.

## Acessos

| Perfil                  | Usuário    | Senha |
|-------------------------|------------|-------|
| Gerente de Manutenção   | `gerente`  | 1234  |
| Técnico 1               | `tecnico1` | 1234  |
| Técnico 2               | `tecnico2` | 1234  |

Telefone na tela de login: qualquer número com DDD, ex. `(11) 912345678`.

## Jeito manual (pelo terminal do VS Code)

Digite **um comando por vez** e espere o prompt `PS ...>` voltar antes do próximo.

```powershell
cd C:\caminho\ate\a\pasta\do\projeto
dir                                    # tem que listar app.py e requirements.txt
python -m venv venv                    # espere terminar, nao aperte nada
.\venv\Scripts\Activate.ps1            # o prompt passa a comecar com (venv)
pip install -r requirements.txt
streamlit run app.py
```

Se aparecer `Could not open requirements file`, o terminal está na pasta errada:
rode `dir` e use `cd` até enxergar o `app.py`.

Se aparecer erro de "execução de scripts desabilitada" no `Activate.ps1`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Primeira abertura

Depois do login passa o vídeo de apresentação (dá para pular) e, na barra lateral,
uma barra verde mostra o carregamento dos dados até **"✅ Atualização concluída"**.
A partir daí as telas abrem em cerca de 1 segundo.

## Banco de dados

O app usa o MongoDB Atlas, configurado em `.streamlit/secrets.toml`.
Para testar sem internet/Atlas, use o banco em memória:

```powershell
$env:FORZY_USE_MOCK_DB=1
streamlit run app.py
```

## Scripts auxiliares

| Arquivo                | Para que serve                                        |
|------------------------|-------------------------------------------------------|
| `INICIAR.bat`          | Instala tudo e abre o sistema                          |
| `monitor_alertas.bat`  | Monitor de alertas 24 h (e-mail/WhatsApp), outro terminal |
| `importar_dados.bat`   | Importa leituras de arquivo para o MongoDB             |
| `testar_alerta.bat`    | Dispara um alerta de teste                             |
