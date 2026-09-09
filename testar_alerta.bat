@echo off
cd /d "%~dp0"
call venv\Scripts\activate
rem As credenciais (MongoDB, Gmail) sao lidas de .streamlit\secrets.toml.
rem Nao coloque usuario nem senha neste arquivo — ele vai para o Git.
python scripts\testar_alerta.py
pause
