@echo off
cd /d "%~dp0"
call venv\Scripts\activate
rem As credenciais (MongoDB, Gmail) sao lidas de .streamlit\secrets.toml.
rem Nao coloque usuario nem senha neste arquivo — ele vai para o Git.
rem Quem recebe os alertas: por padrao os funcionarios cadastrados no app que
rem marcaram "receber alertas". Para forcar um destinatario fixo, descomente:
rem set EMAIL_ALERT_TO=destinatario@empresa.com
python scripts\monitor_alertas.py
pause
