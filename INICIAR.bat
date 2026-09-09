@echo off
title Forzy - Sistema de Manutencao Preditiva
cd /d "%~dp0"

echo ============================================
echo   FORZY - iniciando o sistema
echo   Pasta: %CD%
echo ============================================
echo.

if not exist "app.py" (
  echo ERRO: este arquivo nao esta na pasta do projeto.
  echo Coloque o INICIAR.bat na mesma pasta do app.py e tente de novo.
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo [1/3] Criando o ambiente virtual... aguarde, nao feche a janela.
  python -m venv venv
  if errorlevel 1 (
    echo.
    echo ERRO ao criar o ambiente virtual. Verifique se o Python esta instalado
    echo e marcado como "Add Python to PATH".
    pause
    exit /b 1
  )
) else (
  echo [1/3] Ambiente virtual ja existe.
)

echo [2/3] Instalando as bibliotecas... pode levar alguns minutos.
call "venv\Scripts\python.exe" -m pip install --upgrade pip -q
call "venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo.
  echo ERRO ao instalar as bibliotecas. Veja a mensagem acima.
  pause
  exit /b 1
)

echo [3/3] Abrindo o sistema no navegador...
echo.
echo   Endereco: http://localhost:8501
echo   Login: gerente / 1234   (ou tecnico1 / 1234, tecnico2 / 1234)
echo.
echo   Para encerrar, feche esta janela.
echo.
call "venv\Scripts\python.exe" -m streamlit run app.py
pause
